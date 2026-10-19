#!/bin/sh
set -eu

mkdir -p /app/data /app/media /app/staticfiles

if [ -d /app/media-seed ] && [ -z "$(ls -A /app/media 2>/dev/null)" ]; then
    cp -a /app/media-seed/. /app/media/
fi

if [ -z "${DJANGO_SECRET_KEY:-}" ]; then
    secret_file=/app/data/.django_secret_key
    if [ ! -f "$secret_file" ]; then
        python -c "import secrets; print(secrets.token_urlsafe(64))" > "$secret_file"
        chmod 600 "$secret_file"
    fi
    DJANGO_SECRET_KEY="$(cat "$secret_file")"
    export DJANGO_SECRET_KEY
fi

python manage.py migrate --noinput

if [ -f /app/deploy-data.json ]; then
    object_count="$(python manage.py shell -c "from core.models import Category; print(Category.objects.count())" | tail -n 1)"
    if [ "$object_count" = "0" ]; then
        python manage.py loaddata /app/deploy-data.json
    fi
fi

python manage.py collectstatic --noinput --clear

exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-2}" \
    --timeout "${GUNICORN_TIMEOUT:-60}" \
    --access-logfile - \
    --error-logfile -
