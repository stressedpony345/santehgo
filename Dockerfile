FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN if [ -f /app/db.sqlite3 ]; then mv /app/db.sqlite3 /app/db.seed.sqlite3; fi \
    && if [ -d /app/media ]; then mv /app/media /app/media-seed; fi \
    && mkdir -p /app/data /app/media /app/staticfiles \
    && chmod +x /app/docker/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/docker/entrypoint.sh"]
