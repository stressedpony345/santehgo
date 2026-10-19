from django.contrib import admin, messages
from django.utils import timezone
from django.utils.html import format_html

from .models import Category, PushSubscription, ServiceRequest, SubCategory, Work


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


@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
    list_display = (
        'full_name', 'phone', 'issue', 'assigned_to', 'completion_status',
        'created_at', 'completion_photo_preview', 'services_preview',
    )
    list_filter = ('completion_status', 'assigned_to', 'created_at', 'preferred_time')
    search_fields = ('full_name', 'phone', 'issue', 'address', 'subcategories__name')
    filter_horizontal = ('subcategories', 'works')
    readonly_fields = (
        'created_at', 'assigned_at', 'completion_requested_at',
        'completion_reviewed_at', 'completion_reviewed_by', 'completion_photo_preview',
    )
    fields = (
        'full_name', 'phone', 'issue', 'address', 'preferred_time',
        'subcategories', 'works', 'assigned_to', 'assigned_at', 'created_at',
        'completion_status', 'completion_photo', 'completion_photo_preview',
        'completion_requested_at', 'completion_reviewed_at', 'completion_reviewed_by',
    )
    actions = ('approve_completion', 'reject_completion')
    date_hierarchy = 'created_at'

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
        return actions

    @admin.action(description='Подтвердить завершение выбранных заявок')
    def approve_completion(self, request, queryset):
        pending = queryset.filter(completion_status=ServiceRequest.CompletionStatus.PENDING)
        changed = pending.update(
            completion_status=ServiceRequest.CompletionStatus.APPROVED,
            completion_reviewed_at=timezone.now(),
            completion_reviewed_by=request.user,
            is_processed=True,
        )
        self.message_user(request, f'Подтверждено заявок: {changed}.', messages.SUCCESS)

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
