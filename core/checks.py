from django.conf import settings
from django.core.checks import Error, register
from urllib.parse import urlsplit
import ipaddress


def _is_public_https_url(value):
    try:
        parsed = urlsplit(value)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
            return False
        hostname = parsed.hostname.rstrip('.').lower()
        if hostname == 'localhost' or hostname.endswith('.local'):
            return False
        try:
            address = ipaddress.ip_address(hostname)
        except ValueError:
            return True
        return not (
            address.is_private or address.is_loopback or address.is_link_local
            or address.is_reserved or address.is_unspecified
        )
    except (ValueError, AttributeError):
        return False


@register()
def check_legal_configuration(app_configs, **kwargs):
    if not settings.LEGAL_PAGES_REQUIRED:
        return []

    errors = []
    required = (
        ('LEGAL_OPERATOR_NAME', 'core.E001', 'Укажите юридическое имя оператора персональных данных.'),
        ('PERSONAL_DATA_CONSENT_VERSION', 'core.E002', 'Укажите версию опубликованного согласия.'),
        ('PERSONAL_DATA_CONSENT_EFFECTIVE_DATE', 'core.E003', 'Укажите дату вступления согласия в силу.'),
    )
    for setting_name, error_id, message in required:
        if not str(getattr(settings, setting_name, '')).strip():
            errors.append(Error(message, id=error_id))
    return errors


@register()
def check_client_notification_configuration(app_configs, **kwargs):
    if not settings.CLIENT_NOTIFICATIONS_ENABLED:
        return []

    errors = []
    webhook_url = settings.CLIENT_NOTIFICATION_WEBHOOK_URL.strip()
    if not _is_public_https_url(webhook_url):
        errors.append(Error('Укажите HTTPS URL SMS-провайдера.', id='core.E010'))
    if not settings.CLIENT_NOTIFICATION_TOKEN.strip():
        errors.append(Error('Укажите токен SMS-провайдера.', id='core.E011'))
    if not _is_public_https_url(settings.PUBLIC_BASE_URL.strip()):
        errors.append(Error('Укажите публичный HTTPS адрес сайта.', id='core.E012'))
    return errors


@register()
def check_production_security(app_configs, **kwargs):
    if not getattr(settings, 'PRODUCTION_MODE', False):
        return []

    errors = []
    if settings.DEBUG:
        errors.append(Error('В production режим DEBUG должен быть выключен.', id='core.E020'))
    if not settings.ALLOWED_HOSTS or '*' in settings.ALLOWED_HOSTS:
        errors.append(Error('В production укажите точные ALLOWED_HOSTS без wildcard.', id='core.E021'))
    secure_settings = (
        ('SESSION_COOKIE_SECURE', 'core.E022', 'В production session cookie должна передаваться только по HTTPS.'),
        ('CSRF_COOKIE_SECURE', 'core.E023', 'В production CSRF cookie должна передаваться только по HTTPS.'),
        ('SECURE_SSL_REDIRECT', 'core.E024', 'В production Django должен отклонять HTTP-запросы.'),
        ('SECURE_PROXY_SSL_HEADER', 'core.E025', 'В production нужен контролируемый HTTPS proxy header.'),
    )
    for setting_name, error_id, message in secure_settings:
        if not getattr(settings, setting_name, None):
            errors.append(Error(message, id=error_id))
    secret_key = str(settings.SECRET_KEY)
    if secret_key.startswith('django-insecure-') or len(secret_key) < 50 or len(set(secret_key)) < 5:
        errors.append(Error('В production нужен случайный DJANGO_SECRET_KEY длиной не менее 50 символов.', id='core.E026'))
    database = settings.DATABASES.get('default', {})
    if 'postgresql' in database.get('ENGINE', '') and database.get('PASSWORD', '') in ('', 'change-this-password'):
        errors.append(Error('В production укажите сильный пароль PostgreSQL.', id='core.E027'))
    return errors
