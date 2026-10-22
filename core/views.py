import json
import re
import base64
from io import BytesIO
import threading
import urllib.error
import urllib.request
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.db import close_old_connections, transaction
from django.db.models import Q
from django.core import signing
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from .models import Category, CompletionMedia, ExtraWork, PushSubscription, ServiceRequest, SubCategory, WithdrawalRequest, Work


master_required = user_passes_test(lambda user: user.is_active and user.is_staff, login_url='/masters/login/')


def _vapid_keys():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    key_path = getattr(settings, 'MASTER_VAPID_KEY_PATH', settings.BASE_DIR / 'data' / 'vapid_private.pem')
    key_path.parent.mkdir(parents=True, exist_ok=True)
    if key_path.exists():
        private_key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
    else:
        private_key = ec.generate_private_key(ec.SECP256R1())
        key_path.write_bytes(
            private_key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
    public_bytes = private_key.public_key().public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )
    return str(key_path), base64.urlsafe_b64encode(public_bytes).rstrip(b'=').decode('ascii')


def _request_price(service_request):
    return int(service_request.approved_total if service_request.approved_total is not None else service_request.total_price)


def _request_payload(service_request):
    works = [
        {'name': work.name, 'description': work.description, 'price': int(work.price)}
        for work in service_request.works.all()
    ]
    services = [
        {'name': service.name, 'category': service.category.name, 'price': int(service.approximate_price)}
        for service in service_request.subcategories.all()
    ]
    return {
        'id': service_request.id,
        'full_name': service_request.full_name or 'Клиент',
        'phone': service_request.phone,
        'issue': service_request.issue,
        'address': service_request.address,
        'preferred_time': service_request.preferred_time,
        'created_at': timezone.localtime(service_request.created_at).strftime('%d.%m.%Y, %H:%M'),
        'price': _request_price(service_request),
        'master_payout': int(service_request.master_payout),
        'approved_total': int(service_request.approved_total) if service_request.approved_total is not None else None,
        'approved_payout': int(service_request.approved_payout) if service_request.approved_payout is not None else None,
        'payment_method': service_request.payment_method,
        'cash_status': service_request.cash_status,
        'cash_due_at': timezone.localtime(service_request.cash_due_at).strftime('%d.%m.%Y, %H:%M') if service_request.cash_due_at else '',
        'cash_due': int((service_request.approved_total or 0) - (service_request.approved_payout or 0)) if service_request.payment_method == ServiceRequest.PaymentMethod.CASH and service_request.payment_confirmed_at else 0,
        'works': works,
        'extra_works': [
            {'id': item.id, 'name': item.name, 'price': int(item.price)}
            for item in service_request.extra_works.all()
        ],
        'services': services,
        'is_processed': service_request.is_processed,
        'completion_status': service_request.completion_status,
        'completion_photo': service_request.completion_photo.url if service_request.completion_photo else '',
        'completion_comment': service_request.completion_comment,
        'completion_media': [
            {'kind': media.kind, 'url': media.file.url}
            for media in service_request.completion_media.all()
        ],
        'assigned_to': service_request.assigned_to_id,
        'work_started_at': timezone.localtime(service_request.work_started_at).strftime('%d.%m.%Y, %H:%M') if service_request.work_started_at else '',
        'payment_confirmed_at': timezone.localtime(service_request.payment_confirmed_at).strftime('%d.%m.%Y, %H:%M') if service_request.payment_confirmed_at else '',
        'assigned_name': service_request.assigned_to.get_full_name() or service_request.assigned_to.username if service_request.assigned_to else '',
    }


def _send_new_request_push(request_id):
    close_old_connections()
    try:
        from pywebpush import WebPushException, webpush

        private_key, _ = _vapid_keys()
        service_request = ServiceRequest.objects.prefetch_related('works', 'subcategories').get(pk=request_id)
        data = json.dumps({
            'title': 'Новая заявка',
            'body': f'Заявка №{request_id} · {_request_price(service_request):,} ₽'.replace(',', ' '),
            'url': '/masters/',
            'tag': f'request-{request_id}',
        }, ensure_ascii=False)
        for subscription in PushSubscription.objects.select_related('user').filter(user__is_active=True, user__is_staff=True):
            try:
                webpush(
                    subscription_info={
                        'endpoint': subscription.endpoint,
                        'keys': {'p256dh': subscription.p256dh, 'auth': subscription.auth},
                    },
                    data=data,
                    vapid_private_key=private_key,
                    vapid_claims={'sub': getattr(settings, 'MASTER_VAPID_SUBJECT', 'mailto:admin@santehgo.ru')},
                    timeout=5,
                )
            except WebPushException as error:
                if getattr(error.response, 'status_code', None) in (404, 410):
                    subscription.delete()
    finally:
        close_old_connections()


def _categories_payload():
    categories = (
        Category.objects.filter(is_active=True)
        .prefetch_related('subcategories__works')
        .order_by('sort_order', 'name')
    )
    payload = []
    for category in categories:
        subs = [
            {
                'id': sub.id,
                'name': sub.name,
                'description': sub.description,
                'image_url': sub.image.url if sub.image else '',
                'price': int(sub.approximate_price),
                'works': [
                    {
                        'id': work.id,
                        'name': work.name,
                        'description': work.description,
                        'price': int(work.price),
                    }
                    for work in sub.works.all()
                    if work.is_active
                ],
            }
            for sub in category.subcategories.all()
            if sub.is_active
        ]
        if not subs:
            continue
        payload.append(
            {
                'id': category.id,
                'name': category.name,
                'slug': category.slug,
                'description': category.description,
                'subcategories': subs,
            }
        )
    return payload


@ensure_csrf_cookie
def home(request):
    categories = _categories_payload()
    return render(
        request,
        'core/home.html',
        {
            'categories': categories,
        },
    )


@require_GET
def categories_api(request):
    return JsonResponse({'categories': _categories_payload()})


@require_GET
def address_suggestions(request):
    query = str(request.GET.get('q', '')).strip()
    if len(query) < 2:
        return JsonResponse({'suggestions': []})

    if not settings.DADATA_API_TOKEN:
        return JsonResponse(
            {'suggestions': [], 'error': 'Подсказки адресов временно недоступны'},
            status=503,
        )

    payload = json.dumps(
        {
            'query': query,
            'count': 8,
            'locations': [{'city': 'Челябинск'}],
            'restrict_value': True,
        },
        ensure_ascii=False,
    ).encode('utf-8')
    upstream_request = urllib.request.Request(
        'https://suggestions.dadata.ru/suggestions/api/4_1/rs/suggest/address',
        data=payload,
        headers={
            'Authorization': f'Token {settings.DADATA_API_TOKEN}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        },
        method='POST',
    )

    try:
        with urllib.request.urlopen(upstream_request, timeout=4) as response:
            upstream = json.loads(response.read().decode('utf-8'))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return JsonResponse(
            {'suggestions': [], 'error': 'Не удалось загрузить подсказки'},
            status=502,
        )

    suggestions = []
    seen = set()
    for item in upstream.get('suggestions', []):
        data = item.get('data') or {}
        if data.get('city') != 'Челябинск':
            continue
        house = str(data.get('house') or '').strip()
        street = data.get('street_with_type') or data.get('settlement_with_type') or ''
        title = ', '.join(part for part in (street, f'д {house}' if house else '') if part)
        subtitle = data.get('city_district_with_type') or 'Челябинск'
        dedupe_key = re.sub(r'\s+', ' ', f'{title}|{subtitle}').strip().lower()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        suggestions.append(
            {
                'value': item.get('value', ''),
                'title': title or item.get('value', ''),
                'subtitle': subtitle,
            }
        )
    return JsonResponse({'suggestions': suggestions})


@require_GET
def request_success(request):
    return render(request, 'core/request_success.html')


def master_login(request):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('master_dashboard')
    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.get_user()
        if not user.is_staff:
            form.add_error(None, 'Доступ разрешён только мастерам')
        else:
            login(request, user)
            return redirect('master_dashboard')
    return render(request, 'core/masters/login.html', {'form': form})


@require_POST
@master_required
def master_logout(request):
    logout(request)
    return redirect('master_login')


@master_required
def master_dashboard(request):
    return render(request, 'core/masters/dashboard.html')


@require_GET
def master_manifest(request):
    return JsonResponse(
        {
            'name': 'САНТЕХГО — кабинет мастера',
            'short_name': 'САНТЕХГО',
            'description': 'Заявки мастеров САНТЕХГО',
            'start_url': '/masters/',
            'id': '/masters/',
            'scope': '/masters/',
            'display': 'standalone',
            'background_color': '#062f52',
            'theme_color': '#073c66',
            'lang': 'ru',
            'icons': [
                {
                    'src': '/static/core/img/pwa-icon-192.png?v=3',
                    'sizes': '192x192',
                    'type': 'image/png',
                    'purpose': 'any',
                },
                {
                    'src': '/static/core/img/pwa-icon-512.png?v=3',
                    'sizes': '512x512',
                    'type': 'image/png',
                    'purpose': 'any maskable',
                }
            ],
        },
        content_type='application/manifest+json',
    )


@require_GET
def master_service_worker(request):
    response = render(request, 'core/masters/sw.js', content_type='application/javascript')
    response['Service-Worker-Allowed'] = '/masters/'
    response['Cache-Control'] = 'no-cache'
    return response


@require_GET
@master_required
def master_requests_api(request):
    queryset = ServiceRequest.objects.select_related('assigned_to').prefetch_related(
        'works', 'subcategories__category', 'extra_works', 'completion_media'
    )
    available = queryset.filter(is_processed=False, assigned_to__isnull=True)
    mine = queryset.filter(assigned_to=request.user)
    approved_income = sum(
        int(item.master_payout)
        for item in mine
        if item.completion_status == ServiceRequest.CompletionStatus.APPROVED
    )
    latest_id = ServiceRequest.objects.order_by('-id').values_list('id', flat=True).first() or 0
    return JsonResponse({
        'available': [_request_payload(item) for item in available],
        'mine': [_request_payload(item) for item in mine],
        'approved_income': approved_income,
        'latest_id': latest_id,
        'master': {
            'username': request.user.username,
            'name': request.user.get_full_name() or request.user.username,
        },
    })


def _earnings_data(user):
    today = timezone.localdate()
    mine = list(ServiceRequest.objects.filter(assigned_to=user).prefetch_related('works', 'subcategories', 'extra_works'))
    approved = [item for item in mine if item.completion_status == ServiceRequest.CompletionStatus.APPROVED]
    def reviewed_date(item):
        return timezone.localtime(item.completion_reviewed_at or item.created_at).date()
    this_month = [item for item in approved if (reviewed_date(item).year, reviewed_date(item).month) == (today.year, today.month)]
    today_items = [item for item in approved if reviewed_date(item) == today]
    withdrawals = list(WithdrawalRequest.objects.filter(master=user).select_related('reviewed_by'))
    qr_earned = sum(int(item.master_payout) for item in approved if item.payment_method == ServiceRequest.PaymentMethod.QR and item.payment_confirmed_at)
    reserved = sum(int(item.amount) for item in withdrawals if item.status != WithdrawalRequest.Status.REJECTED)
    cash = [item for item in approved if item.payment_method == ServiceRequest.PaymentMethod.CASH and item.payment_confirmed_at]
    cash_due = sum(int((item.approved_total or 0) - (item.approved_payout or 0)) for item in cash if item.cash_status != ServiceRequest.CashStatus.CONFIRMED)
    cash_overdue = sum(item.cash_due_at is not None and item.cash_due_at < timezone.now() and item.cash_status != ServiceRequest.CashStatus.CONFIRMED for item in cash)
    days = []
    for offset in range(13, -1, -1):
        date = today - timedelta(days=offset)
        items = [item for item in approved if reviewed_date(item) == date]
        days.append({'date': date.strftime('%d.%m'), 'amount': sum(int(item.master_payout) for item in items), 'count': len(items)})
    return {
        'today': {'earned': sum(int(item.master_payout) for item in today_items), 'count': len(today_items), 'turnover': sum(int(item.approved_total or item.total_price) for item in today_items)},
        'month': {'earned': sum(int(item.master_payout) for item in this_month), 'count': len(this_month), 'turnover': sum(int(item.approved_total or item.total_price) for item in this_month)},
        'all_time': {'earned': sum(int(item.master_payout) for item in approved), 'count': len(approved)},
        'in_progress': sum(item.work_started_at is not None and item.completion_status in (ServiceRequest.CompletionStatus.NONE, ServiceRequest.CompletionStatus.REJECTED) for item in mine),
        'pending': sum(item.completion_status == ServiceRequest.CompletionStatus.PENDING for item in mine),
        'average_payout': round(sum(int(item.master_payout) for item in approved) / len(approved)) if approved else 0,
        'approval_rate': round(100 * len(approved) / (len(approved) + sum(item.completion_status == ServiceRequest.CompletionStatus.REJECTED for item in mine))) if approved or any(item.completion_status == ServiceRequest.CompletionStatus.REJECTED for item in mine) else 0,
        'cash_due': cash_due,
        'cash_count': sum(item.cash_status == ServiceRequest.CashStatus.DUE for item in cash),
        'cash_overdue': cash_overdue,
        'available': max(0, qr_earned - reserved),
        'is_monday': today.weekday() == 0,
        'days': days,
        'withdrawals': [{'id': item.id, 'amount': int(item.amount), 'status': item.status, 'created_at': timezone.localtime(item.created_at).strftime('%d.%m.%Y')} for item in withdrawals[:10]],
        'recent': [{'id': item.id, 'date': reviewed_date(item).strftime('%d.%m.%Y'), 'total': int(item.approved_total or item.total_price), 'payout': int(item.master_payout), 'payment_method': item.payment_method} for item in sorted(approved, key=lambda item: item.completion_reviewed_at or item.created_at, reverse=True)[:12]],
    }


@require_GET
@master_required
def master_earnings_api(request):
    return JsonResponse(_earnings_data(request.user))


@require_POST
@master_required
def master_request_withdrawal(request):
    if timezone.localdate().weekday() != 0:
        return JsonResponse({'ok': False, 'error': 'Заявку на вывод можно подать только в понедельник'}, status=403)
    with transaction.atomic():
        # Lock the master row so simultaneous requests cannot reserve the same balance twice.
        get_user_model().objects.select_for_update().get(pk=request.user.pk)
        available = _earnings_data(request.user)['available']
        if available <= 0:
            return JsonResponse({'ok': False, 'error': 'Нет доступной суммы для вывода: нужны подтверждённые QR-заявки'}, status=409)
        withdrawal = WithdrawalRequest.objects.create(master=request.user, amount=available)
    return JsonResponse({'ok': True, 'id': withdrawal.pk, 'amount': available})


@require_POST
@master_required
def master_choose_payment(request, request_id):
    try:
        method = json.loads(request.body).get('method')
    except (ValueError, AttributeError):
        method = None
    # Future payment integration: verify the provider transaction before posting
    # any real balance. BANK deliberately stays disabled until then.
    if method not in (ServiceRequest.PaymentMethod.QR, ServiceRequest.PaymentMethod.CASH):
        return JsonResponse({'ok': False, 'error': 'Выберите QR или наличные; безнал пока не подключён'}, status=400)
    with transaction.atomic():
        item = get_object_or_404(ServiceRequest.objects.select_for_update(), pk=request_id, assigned_to=request.user)
        if item.completion_status != ServiceRequest.CompletionStatus.APPROVED:
            return JsonResponse({'ok': False, 'error': 'Сначала модератор должен принять работу'}, status=409)
        if item.payment_method != ServiceRequest.PaymentMethod.UNSET:
            return JsonResponse({'ok': False, 'error': 'Способ оплаты уже выбран; для исправления обратитесь к модератору'}, status=409)
        item.payment_method = method
        item.save(update_fields=('payment_method',))
    return JsonResponse({'ok': True})


@require_POST
@master_required
def master_confirm_payment(request, request_id):
    with transaction.atomic():
        item = get_object_or_404(ServiceRequest.objects.select_for_update(), pk=request_id, assigned_to=request.user)
        if item.completion_status != ServiceRequest.CompletionStatus.APPROVED or item.payment_method not in (
            ServiceRequest.PaymentMethod.QR, ServiceRequest.PaymentMethod.CASH,
        ):
            return JsonResponse({'ok': False, 'error': 'Сначала выберите способ оплаты принятой заявки'}, status=409)
        if item.payment_confirmed_at:
            return JsonResponse({'ok': False, 'error': 'Оплата уже отмечена'}, status=409)
        item.payment_confirmed_at = timezone.now()
        if item.payment_method == ServiceRequest.PaymentMethod.CASH:
            item.cash_status = ServiceRequest.CashStatus.DUE
            item.cash_due_at = timezone.localtime().replace(hour=23, minute=59, second=59, microsecond=0)
        item.save(update_fields=('payment_confirmed_at', 'cash_status', 'cash_due_at'))
    return JsonResponse({'ok': True})


@require_GET
@master_required
def master_demo_qr(request, request_id):
    import qrcode

    item = get_object_or_404(ServiceRequest, pk=request_id, assigned_to=request.user,
                             completion_status=ServiceRequest.CompletionStatus.APPROVED,
                             payment_method=ServiceRequest.PaymentMethod.QR)
    token = signing.dumps({'id': item.pk, 'amount': int(item.approved_total)}, salt='demo-payment')
    url = request.build_absolute_uri(reverse('master_demo_payment', args=[token]))
    output = BytesIO()
    qrcode.make(url, box_size=8, border=3).save(output, format='PNG')
    response = HttpResponse(output.getvalue(), content_type='image/png')
    response['Cache-Control'] = 'no-store'
    return response


@require_GET
def master_demo_payment(request, token):
    try:
        payment = signing.loads(token, salt='demo-payment', max_age=7 * 24 * 3600)
    except signing.BadSignature:
        return HttpResponse('Недействительный тестовый QR', status=404)
    return render(request, 'core/masters/demo_payment.html', payment)


@require_POST
@master_required
def master_report_cash(request, request_id):
    with transaction.atomic():
        item = get_object_or_404(ServiceRequest.objects.select_for_update(), pk=request_id, assigned_to=request.user)
        if item.payment_method != ServiceRequest.PaymentMethod.CASH or item.cash_status != ServiceRequest.CashStatus.DUE:
            return JsonResponse({'ok': False, 'error': 'Нет ожидающей сдачи наличных'}, status=409)
        item.cash_status = ServiceRequest.CashStatus.REPORTED
        item.cash_reported_at = timezone.now()
        item.save(update_fields=('cash_status', 'cash_reported_at'))
    return JsonResponse({'ok': True})


@require_POST
@master_required
def master_claim_request(request, request_id):
    with transaction.atomic():
        service_request = get_object_or_404(ServiceRequest.objects.select_for_update(), pk=request_id)
        if service_request.is_processed:
            return JsonResponse({'ok': False, 'error': 'Заявка уже завершена'}, status=409)
        if service_request.assigned_to_id:
            return JsonResponse({'ok': False, 'error': 'Заявку уже взял другой мастер'}, status=409)
        service_request.assigned_to = request.user
        service_request.assigned_at = timezone.now()
        service_request.save(update_fields=('assigned_to', 'assigned_at'))
    return JsonResponse({'ok': True})


@require_POST
@master_required
def master_start_request(request, request_id):
    with transaction.atomic():
        item = get_object_or_404(ServiceRequest.objects.select_for_update(), pk=request_id, assigned_to=request.user)
        if item.is_processed or item.completion_status != ServiceRequest.CompletionStatus.NONE or item.work_started_at:
            return JsonResponse({'ok': False, 'error': 'Нельзя начать работу с заявкой на этом этапе'}, status=409)
        item.work_started_at = timezone.now()
        item.save(update_fields=('work_started_at',))
    return JsonResponse({'ok': True})


@require_GET
@master_required
def master_work_search(request):
    query = request.GET.get('q', '').strip()[:100]
    if len(query) < 2:
        return JsonResponse({'works': []})
    works = Work.objects.filter(is_active=True, service__is_active=True, service__category__is_active=True).filter(
        Q(name__icontains=query) | Q(service__name__icontains=query)
    ).select_related('service').order_by('service__name', 'name')[:30]
    return JsonResponse({'works': [
        {'id': work.id, 'name': work.name, 'service': work.service.name, 'price': int(work.price)}
        for work in works
    ]})


@require_POST
@master_required
def master_add_extra_work(request, request_id):
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict):
            raise ValueError
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'ok': False, 'error': 'Некорректные данные работы'}, status=400)
    work_id = data.get('work_id')
    if work_id is not None:
        if isinstance(work_id, bool) or not str(work_id).isdigit():
            return JsonResponse({'ok': False, 'error': 'Выберите работу из каталога'}, status=400)
        work = Work.objects.filter(pk=work_id, is_active=True, service__is_active=True, service__category__is_active=True).first()
        if not work:
            return JsonResponse({'ok': False, 'error': 'Работа больше не доступна в каталоге'}, status=400)
        name, price = work.name, work.price
    else:
        name = data.get('name')
        price = data.get('price')
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 180:
            return JsonResponse({'ok': False, 'error': 'Укажите название работы (до 180 символов)'}, status=400)
        if isinstance(price, bool) or not str(price).isdigit() or not 0 < int(price) <= 9999999999:
            return JsonResponse({'ok': False, 'error': 'Укажите стоимость в целых рублях больше нуля'}, status=400)
        name, price = name.strip(), int(price)
    with transaction.atomic():
        service_request = get_object_or_404(ServiceRequest.objects.select_for_update(), pk=request_id, assigned_to=request.user)
        if not service_request.work_started_at or service_request.is_processed or service_request.completion_status in (
            ServiceRequest.CompletionStatus.PENDING, ServiceRequest.CompletionStatus.APPROVED,
        ):
            return JsonResponse({'ok': False, 'error': 'Состав завершённой заявки изменить нельзя'}, status=409)
        extra = ExtraWork.objects.create(service_request=service_request, added_by=request.user, name=name, price=price)
    return JsonResponse({'ok': True, 'id': extra.id, 'price': _request_price(service_request)})


@require_POST
@master_required
def master_complete_request(request, request_id):
    from PIL import Image, UnidentifiedImageError

    photos = request.FILES.getlist('photos') or ([request.FILES['photo']] if 'photo' in request.FILES else [])
    videos = request.FILES.getlist('videos')
    comment = request.POST.get('comment', '').strip()
    if not photos or len(photos) > 6 or len(videos) > 2:
        return JsonResponse({'ok': False, 'error': 'Добавьте от 1 до 6 фото и не более 2 видео'}, status=400)
    if len(comment) > 2000:
        return JsonResponse({'ok': False, 'error': 'Комментарий не должен превышать 2000 символов'}, status=400)
    if sum(file.size for file in photos + videos) > 120 * 1024 * 1024:
        return JsonResponse({'ok': False, 'error': 'Общий размер файлов не должен превышать 120 МБ'}, status=400)
    for photo in photos:
        if photo.size > 10 * 1024 * 1024:
            return JsonResponse({'ok': False, 'error': 'Каждое фото должно быть меньше 10 МБ'}, status=400)
        try:
            image = Image.open(photo)
            image.verify()
            if image.format not in ('JPEG', 'PNG', 'WEBP') or not photo.name.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                raise ValueError
            photo.seek(0)
        except (UnidentifiedImageError, OSError, ValueError):
            return JsonResponse({'ok': False, 'error': 'Допустимы только фото JPEG, PNG или WebP'}, status=400)
    for video in videos:
        if video.size > 50 * 1024 * 1024:
            return JsonResponse({'ok': False, 'error': 'Каждое видео должно быть меньше 50 МБ'}, status=400)
        header = video.read(12)
        video.seek(0)
        if not ((header[4:8] == b'ftyp' and video.name.lower().endswith('.mp4')) or (header.startswith(b'\x1a\x45\xdf\xa3') and video.name.lower().endswith('.webm'))):
            return JsonResponse({'ok': False, 'error': 'Допустимы только видео MP4 или WebM'}, status=400)
    with transaction.atomic():
        service_request = get_object_or_404(ServiceRequest.objects.select_for_update(), pk=request_id, assigned_to=request.user)
        if not service_request.work_started_at:
            return JsonResponse({'ok': False, 'error': 'Сначала начните работу с заявкой'}, status=409)
        if service_request.completion_status in (ServiceRequest.CompletionStatus.PENDING, ServiceRequest.CompletionStatus.APPROVED):
            return JsonResponse({'ok': False, 'error': 'Заявка уже отправлена на рассмотрение или завершена'}, status=409)
        service_request.completion_photo = photos[0]
        service_request.completion_comment = comment
        service_request.completion_status = ServiceRequest.CompletionStatus.PENDING
        service_request.completion_requested_at = timezone.now()
        service_request.completion_reviewed_at = None
        service_request.completion_reviewed_by = None
        service_request.is_processed = False
        service_request.save(update_fields=(
            'completion_photo', 'completion_comment', 'completion_status', 'completion_requested_at',
            'completion_reviewed_at', 'completion_reviewed_by', 'is_processed',
        ))
        service_request.completion_media.all().delete()
        for file in photos[1:]:
            CompletionMedia.objects.create(service_request=service_request, file=file, kind='photo')
        for file in videos:
            CompletionMedia.objects.create(service_request=service_request, file=file, kind='video')
    return JsonResponse({'ok': True, 'status': service_request.completion_status})


@require_GET
@master_required
def master_push_public_key(request):
    _, public_key = _vapid_keys()
    return JsonResponse({'public_key': public_key})


@require_POST
@master_required
def master_push_subscribe(request):
    try:
        data = json.loads(request.body.decode('utf-8'))
        endpoint = str(data['endpoint'])
        keys = data['keys']
        p256dh = str(keys['p256dh'])
        auth = str(keys['auth'])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'ok': False, 'error': 'Некорректная push-подписка'}, status=400)
    PushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={'user': request.user, 'p256dh': p256dh, 'auth': auth},
    )
    return JsonResponse({'ok': True})


@require_POST
@master_required
def master_change_password(request):
    form = PasswordChangeForm(request.user, request.POST)
    if not form.is_valid():
        return JsonResponse(
            {'ok': False, 'error': ' '.join(error for errors in form.errors.values() for error in errors)},
            status=400,
        )
    user = form.save()
    update_session_auth_hash(request, user)
    return JsonResponse({'ok': True})


@require_POST
def create_request(request):
    try:
        data = json.loads(request.body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'ok': False, 'error': 'Некорректные данные'}, status=400)

    full_name = str(data.get('full_name', '')).strip()
    phone = str(data.get('phone', '')).strip()
    issue = str(data.get('issue', '')).strip()
    address = str(data.get('address', '')).strip()
    preferred_time = str(data.get('preferred_time', '')).strip()
    subcategory_ids = data.get('subcategory_ids') or []
    work_ids = data.get('work_ids') or []

    digits = re.sub(r'\D', '', phone)
    if len(digits) < 10:
        return JsonResponse({'ok': False, 'error': 'Укажите корректный телефон'}, status=400)

    selected = []
    if isinstance(subcategory_ids, list) and subcategory_ids:
        try:
            ids = [int(item) for item in subcategory_ids]
        except (TypeError, ValueError):
            return JsonResponse({'ok': False, 'error': 'Некорректный список услуг'}, status=400)
        selected = list(
            SubCategory.objects.filter(id__in=ids, is_active=True, category__is_active=True)
        )

    selected_works = []
    if isinstance(work_ids, list) and work_ids:
        try:
            ids = [int(item) for item in work_ids]
        except (TypeError, ValueError):
            return JsonResponse({'ok': False, 'error': 'Некорректный список работ'}, status=400)
        selected_works = list(
            Work.objects.filter(
                id__in=ids,
                is_active=True,
                service__is_active=True,
                service__category__is_active=True,
            ).select_related('service')
        )
        selected = list({work.service for work in selected_works})

    if not selected and not selected_works and not issue:
        return JsonResponse({'ok': False, 'error': 'Укажите, что случилось'}, status=400)

    service_request = ServiceRequest.objects.create(
        full_name=full_name,
        phone=phone,
        issue=issue,
        address=address,
        preferred_time=preferred_time,
    )
    if selected:
        service_request.subcategories.set(selected)
    if selected_works:
        service_request.works.set(selected_works)

    transaction.on_commit(
        lambda: threading.Thread(
            target=_send_new_request_push,
            args=(service_request.id,),
            daemon=True,
        ).start()
    )

    return JsonResponse(
        {
            'ok': True,
            'id': service_request.id,
            'success_url': reverse('request_success'),
        }
    )
