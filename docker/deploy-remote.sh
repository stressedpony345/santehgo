#!/bin/sh
set -eu

install -d -m 755 /opt/santehgo
tar -xzf /tmp/santehgo-deploy.tar.gz -C /opt/santehgo
cd /opt/santehgo

umask 077
postgres_password="$(head -c 32 /dev/urandom | base64)"
{
    echo "HTTP_PORT=80"
    echo "DJANGO_ALLOWED_HOSTS=xn--80agf5ahnjz.xn--p1ai,www.xn--80agf5ahnjz.xn--p1ai,45.142.36.78,localhost,127.0.0.1"
    echo "DJANGO_CSRF_TRUSTED_ORIGINS=https://xn--80agf5ahnjz.xn--p1ai,https://www.xn--80agf5ahnjz.xn--p1ai,http://45.142.36.78"
    echo "GUNICORN_WORKERS=2"
    echo "POSTGRES_DB=santehgo"
    echo "POSTGRES_USER=santehgo"
    echo "POSTGRES_PASSWORD=$postgres_password"
} > .env

docker compose up -d --build
