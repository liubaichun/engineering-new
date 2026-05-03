#!/bin/bash
#========================================#
# 企业信息化管理系统 GREEN - 一键安装脚本
# 支持: Ubuntu 20.04+ / CentOS 7+
# 用法: sudo bash install.sh
#========================================#

set -e

echo "========================================"
echo "GREEN 企业信息化管理系统 - 一键安装"
echo "========================================"

# 检测操作系统
if [ -f /etc/debian_version ]; then
    OS="debian"
    echo "[检测] Debian/Ubuntu 系统"
elif [ -f /etc/redhat-release ]; then
    OS="rhel"
    echo "[检测] RHEL/CentOS 系统"
else
    echo "[错误] 不支持的操作系统"
    exit 1
fi

# 颜色输出
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# 检查 root 权限
[ "$EUID" -ne 0 ] && error "请使用 root 权限运行: sudo bash install.sh"

# 交互式输入配置
echo ""
read -p "数据库地址 [localhost]: " DB_HOST
DB_HOST=${DB_HOST:-localhost}
read -p "数据库端口 [5432]: " DB_PORT
DB_PORT=${DB_PORT:-5432}
read -p "数据库名 [engineering_new]: " DB_NAME
DB_NAME=${DB_NAME:-engineering_new}
read -p "数据库用户名 [engineer]: " DB_USER
DB_USER=${DB_USER:-engineer}
read -s -p "数据库密码: " DB_PASS
echo ""
[ -z "$DB_PASS" ] && error "数据库密码不能为空"

read -p "服务器IP/域名 [127.0.0.1]: " SERVER_HOST
SERVER_HOST=${SERVER_HOST:-127.0.0.1}
read -p "Nginx 端口 [80]: " NGINX_PORT
NGINX_PORT=${NGINX_PORT:-80}

APP_DIR="/opt/green-engineering"
SERVICE_USER="green"
SERVICE_NAME="green-gunicorn"

# 1. 创建应用用户
info "创建系统用户 $SERVICE_USER..."
id "$SERVICE_USER" &>/dev/null || useradd -r -m -s /bin/bash "$SERVICE_USER"

# 2. 安装系统依赖
info "安装系统依赖..."
if [ "$OS" = "debian" ]; then
    apt-get update -qq
    apt-get install -y -qq python3.11 python3.11-venv python3-pip \
        postgresql postgresql-client nginx certbot python3-certbot-nginx \
        libpq-dev > /dev/null 2>&1
else
    yum install -y -q python3 python3-pip postgresql postgresql-server nginx \
        libpq-devel > /dev/null 2>&1
    postgresql-setup initdb > /dev/null 2>&1 || true
    systemctl enable postgresql > /dev/null 2>&1 || true
fi

# 3. 初始化数据库
info "初始化 PostgreSQL..."
systemctl enable postgresql > /dev/null 2>&1 || true
systemctl start postgresql 2>/dev/null || true
sleep 2

su - postgres -c "psql -c \"CREATE USER $DB_USER WITH PASSWORD '$DB_PASS';\"" 2>/dev/null || true
su - postgres -c "psql -c \"CREATE DATABASE $DB_NAME OWNER $DB_USER;\"" 2>/dev/null || true
su - postgres -c "psql -c \"ALTER USER $DB_USER CREATEDB;\"" 2>/dev/null || true

# 4. 安装应用
info "安装 GREEN 应用到 $APP_DIR..."
mkdir -p "$APP_DIR"
cp -r . "$APP_DIR/" 2>/dev/null || cp -r /root/engineering-new/. "$APP_DIR/" 2>/dev/null || true

cd "$APP_DIR"
python3.11 -m venv venv
source venv/bin/activate
pip install -q -r requirements.txt gunicorn > /dev/null 2>&1

# 5. 配置环境变量
info "写入配置文件..."
cat > "$APP_DIR/.env" << EOF
DEBUG=False
SECRET_KEY=$(python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")
ALLOWED_HOSTS=$SERVER_HOST,localhost,127.0.0.1
DATABASE_URL=postgres://$DB_USER:$DB_PASS@$DB_HOST:$DB_PORT/$DB_NAME
CSRF_TRUSTED_ORIGINS=http://$SERVER_HOST
DEPLOY_MODE=standalone
EOF

# 6. 数据库迁移
info "执行数据库迁移..."
cd "$APP_DIR"
source venv/bin/activate
python manage.py migrate --noinput

# 7. 收集静态文件
info "收集静态文件..."
python manage.py collectstatic --noinput

# 8. 配置 Nginx
info "配置 Nginx..."
cat > /etc/nginx/sites-available/green << EOF
server {
    listen $NGINX_PORT;
    server_name $SERVER_HOST;

    client_max_body_size 100M;

    location /static/ {
        alias $APP_DIR/staticfiles/;
        expires 30d;
    }

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_redirect off;
    }
}
EOF
ln -sf /etc/nginx/sites-available/green /etc/nginx/sites-enabled/green
rm -f /etc/nginx/sites-enabled/default 2>/dev/null
nginx -t && systemctl reload nginx

# 9. 配置 Gunicorn systemd 服务
info "配置 systemd 服务..."
cat > /etc/systemd/system/$SERVICE_NAME.service << EOF
[Unit]
Description=GREEN Gunicorn
After=network.target postgresql.service

[Service]
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/venv/bin/gunicorn config.wsgi:application \\
    --bind 127.0.0.1:8001 \\
    --workers 3 \\
    --timeout 120 \\
    --log-level info \\
    --log-file $APP_DIR/logs/gunicorn.log
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

mkdir -p "$APP_DIR/logs"
chown -R $SERVICE_USER:$SERVICE_USER "$APP_DIR"
systemctl daemon-reload
systemctl enable $SERVICE_NAME
systemctl restart $SERVICE_NAME

# 10. 防火墙
info "配置防火墙..."
if [ "$OS" = "debian" ]; then
    which ufw &>/dev/null && ufw allow $NGINX_PORT/tcp && ufw allow 8001/tcp
else
    which firewall-cmd &>/dev/null && firewall-cmd --add-port=$NGINX_PORT/tcp --add-port=8001/tcp 2>/dev/null || true
fi

# 完成
info ""
info "========================================"
info "安装完成!"
info "========================================"
info "访问地址: http://$SERVER_HOST/"
info "管理员账号: admin"
info "管理员密码: admin123"
info "⚠️  首次登录后请立即修改密码!"
info ""
info "常用命令:"
echo "  systemctl status $SERVICE_NAME  # 查看状态"
echo "  journalctl -u $SERVICE_NAME -f  # 查看日志"
echo "  cd $APP_DIR && source venv/bin/activate && python manage.py shell  # Django shell"
info "========================================"
