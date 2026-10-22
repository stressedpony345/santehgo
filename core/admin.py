from django.contrib import admin, messages
from django.db import transaction
from django.utils import timezone
from django.utils.html import format_html

from .models import Category, CompletionMedia, ExtraWork, PushSubscription, ServiceRequest, SubCategory, WithdrawalRequest, Work


class SubCategoryInline(admin.TabularInline):
    model = SubCategory
    extra = 1
    fields = ('name', 'description', 'image', 'approximate_price', 'sort_order', 'is_active')


class WorkInline(admin.TabularInline):
    model = Work
    extra = 1
    fields = ('name', 'description', 'price', 'sort_order', 'is_active')


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'sort_order', 'is_active', 'subcategories_count')
    list_editable = ('sort_order', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'subcategories__name')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [SubCategoryInline]

    @admin.display(description='Подкатегорий')
    def subcategories_count(self, obj):
        return obj.subcategories.count()


@admin.register(SubCategory)
class SubCategoryAdmin(admin.ModelAdmin):
    list_display = ('image_preview', 'name', 'category', 'approximate_price', 'sort_order', 'is_active')
    list_editable = ('approximate_price', 'sort_order', 'is_active')
    list_filter = ('category', 'is_active')
    search_fields = ('name', 'description', 'category__name')
    fields = (
        'category', 'name', 'description', 'image', 'image_preview',
        'approximate_price', 'sort_order', 'is_active',
    )
    readonly_fields = ('image_preview',)
    inlines = (WorkInline,)

    @admin.display(description='Фото')
    def image_preview(self, obj):
        if obj and obj.image:
            return format_html(
                '<img src="{}" style="width:72px;height:52px;object-fit:cover;border-radius:8px">',
                obj.image.url,
            )
        return '—'


@admin.register(Work)
class WorkAdmin(admin.ModelAdmin):
    list_display = ('name', 'service', 'category_name', 'price', 'sort_order', 'is_active')
    list_editable = ('price', 'sort_order', 'is_active')
    list_filter = ('service__category', 'service', 'is_active')
    search_fields = ('name', 'description', 'service__name', 'service__category__name')

    @admin.display(description='Категория', ordering='service__category__name')
    def category_name(self, obj):
        return obj.service.category.name


@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at', 'updated_at')
    search_fields = ('user__username', 'endpoint')
    readonly_fields = ('created_at', 'updated_at')


class ExtraWorkInline(admin.TabularInline):
    model = ExtraWork
    extra = 0
    readonly_fields = ('name', 'price', 'added_by', 'created_at')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class CompletionMediaInline(admin.TabularInline):
    model = CompletionMedia
    extra = 0
    readonly_fields = ('kind', 'file', 'uploaded_at')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
    inlines = (ExtraWorkInline, CompletionMediaInline)
    list_display = (
        'full_name', 'phone', 'issue', 'assigned_to', 'completion_status',
        'order_total', 'master_amount', 'created_at', 'completion_photo_preview', 'services_preview',
    )
    list_filter = ('completion_status', 'assigned_to', 'created_at', 'preferred_time')
    search_fields = ('full_name', 'phone', 'issue', 'address', 'subcategories__name')
    filter_horizontal = ('subcategories', 'works')
    readonly_fields = (
        'created_at', 'assigned_at', 'completion_requested_at',
        'completion_reviewed_at', 'completion_reviewed_by', 'completion_photo_preview',
        'approved_total', 'approved_payout', 'cash_status', 'cash_due_at', 'cash_reported_at', 'cash_confirmed_at',
        'completion_status', 'payment_method',
    )
    fields = (
        'full_name', 'phone', 'issue', 'address', 'preferred_time',
        'subcategories', 'works', 'assigned_to', 'assigned_at', 'created_at',
        'master_share_percent', 'approved_total', 'approved_payout',
        'completion_status', 'completion_photo', 'completion_photo_preview', 'completion_comment',
        'payment_method', 'cash_status', 'cash_due_at', 'cash_reported_at', 'cash_confirmed_at',
        'completion_requested_at', 'completion_reviewed_at', 'completion_reviewed_by',
    )
    actions = ('approve_completion', 'reject_completion', 'confirm_cash')
    date_hierarchy = 'created_at'

    @admin.display(description='Стоимость заявки')
    def order_total(self, obj):
        return obj.approved_total if obj.approved_total is not None else obj.total_price

    @admin.display(description='Мастеру')
    def master_amount(self, obj):
        return obj.master_payout

    @admin.display(description='Услуги')
    def services_preview(self, obj):
        names = list(obj.subcategories.select_related('category').all()[:4])
        if not names:
            return '—'
        text = ', '.join(f'{item.category.name}: {item.name}' for item in names)
        extra = obj.subcategories.count() - len(names)
        return f'{text}…' if extra > 0 else text

    @admin.display(description='Фото работы')
    def completion_photo_preview(self, obj):
        if obj.completion_photo:
            return format_html(
                '<a href="{0}" target="_blank"><img src="{0}" style="width:96px;height:72px;object-fit:cover;border-radius:8px"></a>',
                obj.completion_photo.url,
            )
        return '—'

    def get_actions(self, request):
        actions = super().get_actions(request)
        if not request.user.is_superuser:
            actions.pop('approve_completion', None)
            actions.pop('reject_completion', None)
            actions.pop('confirm_cash', None)
        return actions

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if obj and obj.completion_status == ServiceRequest.CompletionStatus.APPROVED:
            fields.append('master_share_percent')
        return fields

    @admin.action(description='Подтвердить завершение выбранных заявок')
    def approve_completion(self, request, queryset):
        changed = 0
        with transaction.atomic():
            selected_ids = queryset.values_list('pk', flat=True)
            pending = ServiceRequest.objects.filter(
                pk__in=selected_ids,
                completion_status=ServiceRequest.CompletionStatus.PENDING,
            ).select_for_update()
            for item in pending:
                item.freeze_amounts()
                item.completion_status = ServiceRequest.CompletionStatus.APPROVED
                item.completion_reviewed_at = timezone.now()
                item.completion_reviewed_by = request.user
                item.is_processed = True
                item.save(update_fields=('approved_total', 'approved_payout', 'completion_status', 'completion_reviewed_at', 'completion_reviewed_by', 'is_processed'))
                changed += 1
        self.message_user(request, f'Подтверждено заявок: {changed}.', messages.SUCCESS)

    @admin.action(description='Подтвердить сдачу наличных')
    def confirm_cash(self, request, queryset):
        changed = queryset.filter(payment_method=ServiceRequest.PaymentMethod.CASH, cash_status=ServiceRequest.CashStatus.REPORTED).update(
            cash_status=ServiceRequest.CashStatus.CONFIRMED, cash_confirmed_at=timezone.now(),
        )
        self.message_user(request, f'Подтверждено сдач: {changed}.', messages.SUCCESS)

    @admin.action(description='Отклонить фото выбранных заявок')
    def reject_completion(self, request, queryset):
        pending = queryset.filter(completion_status=ServiceRequest.CompletionStatus.PENDING)
        changed = pending.update(
            completion_status=ServiceRequest.CompletionStatus.REJECTED,
            completion_reviewed_at=timezone.now(),
            completion_reviewed_by=request.user,
            is_processed=False,
        )
        self.message_user(request, f'Отклонено заявок: {changed}.', messages.WARNING)


@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(admin.ModelAdmin):
    list_display = ('master', 'amount', 'status', 'created_at', 'reviewed_at', 'reviewed_by')
    list_filter = ('status', 'created_at')
    readonly_fields = ('master', 'amount', 'status', 'created_at', 'reviewed_at', 'reviewed_by')
    actions = ('approve_withdrawal', 'reject_withdrawal')

    def has_add_permission(self, request):
        return False

    def get_actions(self, request):
        actions = super().get_actions(request)
        if not request.user.is_superuser:
            actions.pop('approve_withdrawal', None)
            actions.pop('reject_withdrawal', None)
        return actions

    @admin.action(description='Подтвердить заявки на вывод (тест, без перевода денег)')
    def approve_withdrawal(self, request, queryset):
        changed = queryset.filter(status=WithdrawalRequest.Status.PENDING).update(
            status=WithdrawalRequest.Status.APPROVED, reviewed_at=timezone.now(), reviewed_by=request.user,
        )
        self.message_user(request, f'Подтверждено заявок на вывод: {changed}. Перевод денег не производится.', messages.SUCCESS)

    @admin.action(description='Отклонить заявки на вывод')
    def reject_withdrawal(self, request, queryset):
        changed = queryset.filter(status=WithdrawalRequest.Status.PENDING).update(
            status=WithdrawalRequest.Status.REJECTED, reviewed_at=timezone.now(), reviewed_by=request.user,
        )
        self.message_user(request, f'Отклонено заявок на вывод: {changed}.', messages.WARNING)
