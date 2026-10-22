from django.conf import settings
from django.db import models
from decimal import Decimal, ROUND_HALF_UP
from django.core.validators import MaxValueValidator, MinValueValidator


class Category(models.Model):
    name = models.CharField('Название', max_length=120)
    slug = models.SlugField('Слаг', max_length=140, unique=True)
    description = models.TextField('Описание', blank=True)
    sort_order = models.PositiveIntegerField('Порядок', default=0)
    is_active = models.BooleanField('Активна', default=True)

    class Meta:
        ordering = ['sort_order', 'name']
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'

    def __str__(self):
        return self.name


class SubCategory(models.Model):
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='subcategories',
        verbose_name='Категория',
    )
    name = models.CharField('Название', max_length=160)
    description = models.TextField(
        'Описание карточки',
        blank=True,
        help_text='Коротко опишите услугу. Если оставить пустым, будет показано описание категории.',
    )
    image = models.ImageField(
        'Изображение карточки',
        upload_to='services/',
        blank=True,
        null=True,
    )
    approximate_price = models.DecimalField(
        'Примерная стоимость, ₽',
        max_digits=10,
        decimal_places=0,
    )
    sort_order = models.PositiveIntegerField('Порядок', default=0)
    is_active = models.BooleanField('Активна', default=True)

    class Meta:
        ordering = ['sort_order', 'name']
        verbose_name = 'Услуга'
        verbose_name_plural = 'Услуги'

    def __str__(self):
        return f'{self.category.name} — {self.name}'


class Work(models.Model):
    service = models.ForeignKey(
        SubCategory,
        on_delete=models.CASCADE,
        related_name='works',
        verbose_name='Услуга',
    )
    name = models.CharField('Название работы', max_length=180)
    description = models.TextField('Подробное описание', blank=True)
    price = models.DecimalField('Стоимость, ₽', max_digits=10, decimal_places=0)
    sort_order = models.PositiveIntegerField('Порядок', default=0)
    is_active = models.BooleanField('Активна', default=True)

    class Meta:
        ordering = ['sort_order', 'name']
        verbose_name = 'Работа'
        verbose_name_plural = 'Работы'

    def __str__(self):
        return f'{self.service.name} — {self.name}'


class ServiceRequest(models.Model):
    class PaymentMethod(models.TextChoices):
        UNSET = 'unset', 'Не выбран'
        QR = 'qr', 'QR (тест)'
        CASH = 'cash', 'Наличные (тест)'
        BANK = 'bank', 'Безнал (позже)'

    class CashStatus(models.TextChoices):
        NONE = 'none', 'Не требуется'
        DUE = 'due', 'Сдать до конца дня'
        REPORTED = 'reported', 'Мастер сообщил о сдаче'
        CONFIRMED = 'confirmed', 'Подтверждено модератором'

    class CompletionStatus(models.TextChoices):
        NONE = 'none', 'Не отправлена'
        PENDING = 'pending', 'На рассмотрении'
        APPROVED = 'approved', 'Завершена'
        REJECTED = 'rejected', 'Отклонена'

    full_name = models.CharField('ФИО', max_length=200, blank=True)
    phone = models.CharField('Телефон', max_length=32)
    issue = models.CharField('Что случилось', max_length=500, blank=True)
    address = models.CharField('Адрес', max_length=240, blank=True)
    preferred_time = models.CharField('Когда удобно', max_length=80, blank=True)
    subcategories = models.ManyToManyField(
        SubCategory,
        related_name='service_requests',
        verbose_name='Выбранные услуги',
        blank=True,
    )
    works = models.ManyToManyField(
        Work,
        related_name='service_requests',
        verbose_name='Выбранные работы',
        blank=True,
    )
    created_at = models.DateTimeField('Создана', auto_now_add=True)
    is_processed = models.BooleanField('Обработана', default=False)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='assigned_service_requests',
        verbose_name='Мастер',
        blank=True,
        null=True,
    )
    assigned_at = models.DateTimeField('Передана мастеру', blank=True, null=True)
    work_started_at = models.DateTimeField('Мастер начал работу', blank=True, null=True)
    completion_status = models.CharField(
        'Статус завершения',
        max_length=16,
        choices=CompletionStatus.choices,
        default=CompletionStatus.NONE,
        db_index=True,
    )
    completion_photo = models.ImageField(
        'Фото выполненной работы',
        upload_to='completed/%Y/%m/',
        blank=True,
        null=True,
    )
    completion_comment = models.TextField('Комментарий модератору', blank=True)
    master_share_percent = models.DecimalField(
        'Доля мастера, %', max_digits=5, decimal_places=2, default=40,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    approved_total = models.DecimalField('Подтверждённая стоимость, ₽', max_digits=12, decimal_places=0, null=True, blank=True)
    approved_payout = models.DecimalField('Подтверждено мастеру, ₽', max_digits=12, decimal_places=0, null=True, blank=True)
    payment_method = models.CharField('Способ оплаты (тест)', max_length=8, choices=PaymentMethod.choices, default=PaymentMethod.UNSET)
    payment_confirmed_at = models.DateTimeField('Оплата отмечена (тест)', null=True, blank=True)
    cash_status = models.CharField('Сдача наличных', max_length=12, choices=CashStatus.choices, default=CashStatus.NONE)
    cash_due_at = models.DateTimeField('Сдать наличные до', null=True, blank=True)
    cash_reported_at = models.DateTimeField('Сообщено о сдаче наличных', null=True, blank=True)
    cash_confirmed_at = models.DateTimeField('Сдача наличных подтверждена', null=True, blank=True)
    completion_requested_at = models.DateTimeField('Отправлена на модерацию', blank=True, null=True)
    completion_reviewed_at = models.DateTimeField('Проверена администратором', blank=True, null=True)
    completion_reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='reviewed_service_requests',
        verbose_name='Проверил',
        blank=True,
        null=True,
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Заявка'
        verbose_name_plural = 'Заявки'

    def __str__(self):
        return f'{self.full_name} ({self.phone})'

    @property
    def total_price(self):
        works = list(self.works.all())
        extras = sum((item.price for item in self.extra_works.all()), 0)
        if works:
            return sum((work.price for work in works), 0) + extras
        return sum((service.approximate_price for service in self.subcategories.all()), 0) + extras

    @property
    def master_payout(self):
        if self.approved_payout is not None:
            return self.approved_payout
        return (Decimal(self.total_price) * self.master_share_percent / 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP)

    def freeze_amounts(self):
        self.approved_total = self.total_price
        self.approved_payout = (Decimal(self.approved_total) * self.master_share_percent / 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP)


class CompletionMedia(models.Model):
    service_request = models.ForeignKey(ServiceRequest, on_delete=models.CASCADE, related_name='completion_media')
    file = models.FileField('Фото или видео', upload_to='completed/%Y/%m/')
    kind = models.CharField('Тип', max_length=5, choices=[('photo', 'Фото'), ('video', 'Видео')])
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Материал выполнения'
        verbose_name_plural = 'Материалы выполнения'


class WithdrawalRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Ожидает модератора'
        APPROVED = 'approved', 'Подтверждена (тест)'
        REJECTED = 'rejected', 'Отклонена'

    master = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='withdrawals')
    amount = models.DecimalField('Сумма, ₽', max_digits=12, decimal_places=0)
    status = models.CharField('Статус', max_length=12, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='reviewed_withdrawals')

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Заявка на вывод (тест)'
        verbose_name_plural = 'Заявки на вывод (тест)'


class ExtraWork(models.Model):
    service_request = models.ForeignKey(ServiceRequest, on_delete=models.CASCADE, related_name='extra_works')
    name = models.CharField('Дополнительная работа', max_length=180)
    price = models.DecimalField('Стоимость, ₽', max_digits=10, decimal_places=0)
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField('Добавлена', auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'id']
        verbose_name = 'Дополнительная работа'
        verbose_name_plural = 'Дополнительные работы'

    def __str__(self):
        return f'{self.name} — {self.price} ₽'


class PushSubscription(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='push_subscriptions',
        verbose_name='Мастер',
    )
    endpoint = models.TextField('Endpoint', unique=True)
    p256dh = models.TextField('Ключ p256dh')
    auth = models.TextField('Ключ auth')
    created_at = models.DateTimeField('Создана', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлена', auto_now=True)

    class Meta:
        verbose_name = 'Push-подписка'
        verbose_name_plural = 'Push-подписки'

    def __str__(self):
        return f'{self.user} — {self.endpoint[:48]}'
