#!/bin/bash
set -e

echo "[ENTRYPOINT] Starting GREEN ERP v2.2.0..."

# 等待数据库就绪
echo "[ENTRYPOINT] Waiting for database..."
until python -c "import django; django.setup(); from django.db import connection; connection.ensure_connection()" 2>/dev/null; do
    echo "[ENTRYPOINT] Database not ready, waiting..."
    sleep 2
done
echo "[ENTRYPOINT] Database ready."

# 执行未完成的迁移
echo "[ENTRYPOINT] Running migrations..."
python manage.py migrate --noinput

# 收集静态文件
echo "[ENTRYPOINT] Collecting static files..."
python manage.py collectstatic --noinput --clear

echo "[ENTRYPOINT] Starting Gunicorn..."
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8001 \
    --workers 2 \
    --log-level info \
    --log-file /var/log/gunicorn.log \
    --access-logfile /var/log/gunicorn_access.log \
    --error-logfile /var/log/gunicorn_error.log \
    --chdir /app
