# Запуск сайта через Docker Compose

На сервере должны быть установлены Docker и Docker Compose.

```bash
docker-compose up -d --build
```

После запуска сайт доступен на `https://сантехго.рф/`, админ-панель — на
`https://сантехго.рф/admin/`.

При первом запуске текущие записи автоматически импортируются из SQLite в
PostgreSQL. База PostgreSQL и изображения находятся в постоянных Docker volumes.
При пересборке контейнеров заявки, изменения в каталоге и загруженные через
админку фотографии сохраняются.

## Домен

Для запуска по домену скопируйте `.env.example` в `.env` и замените
`example.ru` своим доменом. После этого снова выполните команду запуска.

## Обязательные данные перед production-деплоем

Заполните в `.env` юридическое имя оператора, версию и дату вступления согласия
в силу. При `LEGAL_PAGES_REQUIRED=true` Django остановит запуск, если эти поля
пусты. Не подставляйте тестовые или вымышленные реквизиты.

Клиентские SMS включаются только через `CLIENT_NOTIFICATIONS_ENABLED=true`.
Провайдер должен принимать HTTPS POST с JSON-полями `channel`, `destination`,
`message`, `idempotency_key` и поддерживать тот же ключ из заголовка
`Idempotency-Key`. Авторизация передаётся как `Authorization: Bearer <token>`.
Контейнер `notifications` отправляет outbox небольшими пачками, повторяет только
временные ошибки и оставляет окончательно недоставленные сообщения в админке.
Произвольный HTTP URL, localhost, приватный IP и URL со встроенным паролем не
проходят production-проверку.

Тестовые QR, подтверждения оплаты и выводы должны оставаться выключенными через
`DEMO_FINANCE_ENABLED=false`. В production фактическую оплату отмечает администратор
действием «Отметить фактическую оплату вручную»; операция сохраняется в истории заявки.

## Полезные команды

```bash
docker-compose logs -f
docker-compose restart
docker-compose down
docker-compose exec web python manage.py createsuperuser
```

Команда `docker-compose down` сохраняет данные. Не добавляйте флаг `-v`, если
не хотите удалить базу и загруженные изображения.

## Обновление сайта с рабочего компьютера

После локальных изменений запустите из папки проекта одну команду:

```powershell
.\deploy.ps1
```

Сценарий отправляет на сервер только код и статические файлы, пересобирает
контейнер Django и применяет новые миграции. PostgreSQL, заявки и изображения,
загруженные через админку, при этом не перезаписываются.

## Резервные копии и restore drill

Копия включает PostgreSQL и `media_files`, но не воспроизводимую статику. Архив
публикуется как `complete-*` только после проверки dump, tar и SHA-256.
Незавершённая попытка не удаляет прежние копии.

```bash
docker compose --profile ops run --rm backup /scripts/backup.sh
docker compose --profile ops run --rm backup /scripts/restore-drill.sh latest
```

Restore drill создаёт отдельную временную БД, восстанавливает dump, сверяет миграции
и ссылки на media, затем удаляет только эту БД. `restore_drill=ok` фиксируется ежемесячно
и после изменения backup-скриптов.

Для автозапуска скопируйте `ops/systemd/santehgo-backup.service` и `.timer` в
`/etc/systemd/system/`. Файл `/etc/santehgo-backup.env`:

```text
BACKUP_ROOT=/var/backups/santehgo
OFFSITE_BACKUP_TARGET=backup-user@backup-host:/srv/santehgo
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now santehgo-backup.timer
sudo systemctl start santehgo-backup.service
systemctl list-timers santehgo-backup.timer
journalctl -u santehgo-backup.service
```

Копия только на том же VPS не защищает от потери сервера. Успешная off-host синхронизация
через `OFFSITE_BACKUP_TARGET` обязательна для production-приёмки.

## Health monitoring и тревоги

`/health/ready/` выполняет SQL-запрос и пробную запись в media. Docker healthcheck
и внешний uptime-monitor должны проверять именно этот URL. Ответ не раскрывает
технические детали.

Для ERROR-тревог заполните `ERROR_ALERT_WEBHOOK_URL` и `ERROR_ALERT_TOKEN`, затем
включите `ERROR_ALERTS_ENABLED=true`. Production-check не примет HTTP, localhost,
приватный IP или пустой токен. После перезапуска обязательно проверьте
фактическую доставку:

```bash
docker compose exec -T web python manage.py send_test_alert
```

Для host-level контроля скопируйте `ops/systemd/santehgo-monitor.service` и `.timer`
в `/etc/systemd/system/`. Пример `/etc/santehgo-monitor.env`:

```text
ERROR_ALERT_WEBHOOK_URL=https://alerts.example/api/events
ERROR_ALERT_TOKEN=replace-with-secret
MONITOR_DISK_PERCENT=85
MONITOR_CERT_DAYS=14
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now santehgo-monitor.timer
sudo systemctl start santehgo-monitor.service
systemctl list-timers santehgo-monitor.timer
journalctl -u santehgo-monitor.service
```

Тест тревоги: временно укажите `MONITOR_DISK_PERCENT=0`, запустите service,
убедитесь, что сигнал получен, и верните порог `85`.
