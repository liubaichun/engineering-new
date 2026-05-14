#!/bin/bash
set -e

echo "[ENTRYPOINT] Starting GREEN ERP..."

export DJANGO_SETTINGS_MODULE=config.settings

# ── 等待数据库就绪 ──────────────────────────────────────
echo "[ENTRYPOINT] Waiting for database..."
until python -c "import django; django.setup(); from django.db import connection; connection.ensure_connection()" 2>/dev/null; do
    echo "[ENTRYPOINT] Database not ready, waiting..."
    sleep 2
done
echo "[ENTRYPOINT] Database ready."

# ── 执行未完成的迁移 ───────────────────────────────────
echo "[ENTRYPOINT] Running migrations..."
python manage.py migrate --noinput

# ── 收集静态文件 ───────────────────────────────────────
echo "[ENTRYPOINT] Collecting static files..."
python manage.py collectstatic --noinput --clear

# ── 创建超级管理员（如不存在）───────────────────────────
# 环境变量：ADMIN_USERNAME / ADMIN_PASSWORD / ADMIN_EMAIL
if [ -n "$ADMIN_USERNAME" ] && [ -n "$ADMIN_PASSWORD" ]; then
    echo "[ENTRYPOINT] Creating superuser if not exists..."
    export DJANGO_SUPERUSER_PASSWORD="$ADMIN_PASSWORD"
    python manage.py createsuperuser \
        --noinput \
        --username "$ADMIN_USERNAME" \
        --email "${ADMIN_EMAIL:-admin@example.com}" \
        2>/dev/null || true
    # 如果用户已存在，更新密码
    python -c "
import os, django
django.setup()
from django.contrib.auth import get_user_model
User = get_user_model()
try:
    user = User.objects.get(username=os.environ.get('ADMIN_USERNAME'))
    user.set_password(os.environ.get('ADMIN_PASSWORD'))
    user.save()
    print('[ENTRYPOINT] Superuser password updated.')
except Exception as e:
    print(f'[ENTRYPOINT] Superuser update skipped: {e}')
"
    echo "[ENTRYPOINT] Superuser ready."
fi

# ── 启动 Gunicorn ──────────────────────────────────────
echo "[ENTRYPOINT] Starting Gunicorn..."
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8001 \
    --workers 2 \
    --log-level info \
    --log-file /var/log/gunicorn.log \
    --access-logfile /var/log/gunicorn_access.log \
    --error-logfile /var/log/gunicorn_error.log \
    --chdir /app
