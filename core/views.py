import json
import re
import base64
import threading
import urllib.error
import urllib.request

from django.conf import settings
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.db import close_old_connections, transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from .models import Category, PushSubscription, ServiceRequest, SubCategory, Work


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
    works = list(service_request.works.all())
    if works:
        return int(sum((work.price for work in works), 0))
    return int(sum((service.approximate_price for service in service_request.subcategories.all()), 0))


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
        'works': works,
        'services': services,
        'is_processed': service_request.is_processed,
        'completion_status': service_request.completion_status,
        'completion_photo': service_request.completion_photo.url if service_request.completion_photo else '',
        'assigned_to': service_request.assigned_to_id,
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
        'works', 'subcategories__category'
    )
    available = queryset.filter(is_processed=False, assigned_to__isnull=True)
    mine = queryset.filter(assigned_to=request.user)
    approved_income = sum(
        _request_price(item)
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


@require_POST
@master_required
def master_claim_request(request, request_id):
    with transaction.atomic():
        service_request = get_object_or_404(ServiceRequest.objects.select_for_update(), pk=request_id)
        if service_request.is_processed:
            return JsonResponse({'ok': False, 'error': 'Заявка уже завершена'}, status=409)
        if service_request.assigned_to_id and service_request.assigned_to_id != request.user.id:
            return JsonResponse({'ok': False, 'error': 'Заявку уже взял другой мастер'}, status=409)
        service_request.assigned_to = request.user
        service_request.assigned_at = timezone.now()
        service_request.save(update_fields=('assigned_to', 'assigned_at'))
    return JsonResponse({'ok': True})


@require_POST
@master_required
def master_complete_request(request, request_id):
    from PIL import Image, UnidentifiedImageError

    service_request = get_object_or_404(ServiceRequest, pk=request_id, assigned_to=request.user)
    if service_request.completion_status == ServiceRequest.CompletionStatus.PENDING:
        return JsonResponse({'ok': False, 'error': 'Заявка уже находится на рассмотрении'}, status=409)
    if service_request.completion_status == ServiceRequest.CompletionStatus.APPROVED:
        return JsonResponse({'ok': False, 'error': 'Заявка уже завершена'}, status=409)
    photo = request.FILES.get('photo')
    if not photo:
        return JsonResponse({'ok': False, 'error': 'Сделайте фото выполненной работы'}, status=400)
    if photo.size > 10 * 1024 * 1024:
        return JsonResponse({'ok': False, 'error': 'Фото должно быть меньше 10 МБ'}, status=400)
    try:
        image = Image.open(photo)
        image.verify()
        photo.seek(0)
    except (UnidentifiedImageError, OSError):
        return JsonResponse({'ok': False, 'error': 'Не удалось прочитать изображение'}, status=400)
    service_request.completion_photo = photo
    service_request.completion_status = ServiceRequest.CompletionStatus.PENDING
    service_request.completion_requested_at = timezone.now()
    service_request.completion_reviewed_at = None
    service_request.completion_reviewed_by = None
    service_request.is_processed = False
    service_request.save(update_fields=(
        'completion_photo', 'completion_status', 'completion_requested_at',
        'completion_reviewed_at', 'completion_reviewed_by', 'is_processed',
    ))
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
