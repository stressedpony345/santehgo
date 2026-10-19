# Деплой через GitHub Actions

Workflow `.github/workflows/deploy.yml` автоматически публикует ветку `main` на production-сервер и также поддерживает ручной запуск через вкладку **Actions**.

## Secrets репозитория

В настройках репозитория откройте **Settings → Secrets and variables → Actions** и добавьте:

- `DEPLOY_HOST` — IP или домен сервера;
- `DEPLOY_USER` — SSH-пользователь;
- `DEPLOY_PORT` — SSH-порт, обычно `22`;
- `DEPLOY_PATH` — каталог проекта на сервере, сейчас `/opt/santehgo`;
- `DEPLOY_SSH_KEY` — приватный SSH-ключ целиком;
- `DEPLOY_KNOWN_HOSTS` — строка публичного ключа сервера из `known_hosts`.

Пароли, `.env`, `deploy-data.json`, база данных и каталог `media` в Git не отправляются. PostgreSQL и медиа продолжают храниться в постоянных Docker volumes на сервере.

## Запуск

Каждый push в `main` запускает деплой автоматически. Для ручного запуска откройте **Actions → Deploy production → Run workflow**.

Workflow упаковывает только отслеживаемые Git-файлы, загружает архив во временный каталог сервера, пересобирает `web`, проверяет Django и затем проверяет публичный HTTPS-адрес.

Job отмечен окружением `production`, поэтому его история также видна в разделе Deployments. При необходимости для этого окружения можно включить ручное подтверждение перед публикацией.
