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

# 2. 创建虚拟环境并安装依赖
echo "[2/6] 创建虚拟环境并安装依赖..."
cd "$PROJECT_DIR"
if [ ! -f "venv/bin/activate" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
if [ -f "requirements.txt" ]; then
    pip install -q -r requirements.txt
fi

# 3. 收集静态文件
echo "[3/6] 收集静态文件..."
python manage.py collectstatic --noinput

# 4. 数据库迁移
echo "[4/6] 检查数据库迁移..."
python manage.py migrate --run-syncdb

# 5. 安装 systemd 服务（首次部署或服务文件更新时）
echo "[5/6] 配置 systemd 服务..."
if [ -f "$PROJECT_DIR/deploy/engineering-gunicorn.service" ]; then
    cp "$PROJECT_DIR/deploy/engineering-gunicorn.service" /etc/systemd/system/engineering-gunicorn.service
    systemctl daemon-reload
    systemctl enable engineering-gunicorn
    echo "  systemd 服务已配置"
else
    echo "  警告: 未找到 systemd 服务文件，跳过"
fi

# 清理可能冲突的旧服务文件
for old_svc in engineering.service gunicorn.service engineering-new.service; do
    if [ -f "/etc/systemd/system/$old_svc" ]; then
        echo "  发现残留服务文件 $old_svc，已清理"
        rm -f "/etc/systemd/system/$old_svc"
    fi
done

# 6. 重启 gunicorn（通过 systemd）
echo "[6/6] 重启 gunicorn..."
pkill -9 -f "gunicorn.*engineering" 2>/dev/null || true; sleep 2
systemctl restart engineering-gunicorn
sleep 3
if curl -sf http://127.0.0.1:8001/api/core/auth/login/ > /dev/null 2>&1; then
    echo "✅ 服务启动成功: http://43.156.139.37:8001"
else
    echo "❌ 服务启动失败，请检查日志"
fi
