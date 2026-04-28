#!/bin/bash
# 企业管理系统 - 一键部署脚本
# 用法: bash deploy/deploy.sh

set -e

PROJECT_DIR="/root/engineering-new"
SERVICE_NAME="engineering"

echo "=== 企业管理系统部署 ==="

# 1. 生成 .env 文件（如果不存在）
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo "[1/6] 创建 .env 配置文件..."
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
    echo "  请编辑 $PROJECT_DIR/.env 填入真实 SECRET_KEY 和 ALLOWED_HOSTS"
    echo "  SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(64))')"
fi

# 2. 安装依赖
echo "[2/6] 安装 Python 依赖..."
cd "$PROJECT_DIR"
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt -q
fi

# 3. 收集静态文件
echo "[3/6] 收集静态文件..."
python manage.py collectstatic --noinput

# 4. 数据库迁移
echo "[4/6] 检查数据库迁移..."
python manage.py migrate --run-syncdb

# 5. 重启 gunicorn
echo "[5/6] 重启 gunicorn..."
pkill -f "gunicorn.*config.wsgi" 2>/dev/null || true
sleep 2
cd "$PROJECT_DIR"
nohup venv/bin/gunicorn config.wsgi \
    --bind 0.0.0.0:8001 \
    --workers 4 \
    --timeout 120 \
    --daemon \
    -p "$PROJECT_DIR/gunicorn.pid"

echo "[6/6] 验证服务..."
sleep 2
if curl -sf http://127.0.0.1:8001/api/core/auth/login/ > /dev/null 2>&1; then
    echo "✅ 服务启动成功: http://43.156.139.37:8001"
else
    echo "❌ 服务启动失败，请检查日志"
fi
