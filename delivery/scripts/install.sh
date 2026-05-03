#!/bin/bash
#========================================#
# 企业信息化管理系统 GREEN - 一键安装脚本
# 支持: Ubuntu 20.04+ / CentOS 7+
#
# 交互式: sudo bash install.sh
# 非交互式（环境变量）:
#   DB_HOST=localhost DB_NAME=engineering DB_USER=engineer DB_PASS=xxx \
#   SERVER_DOMAIN=example.com ADMIN_PASS=admin123 \
#   bash install.sh
#========================================#

set -e

echo "========================================"
echo "GREEN 企业信息化管理系统 - 一键安装"
echo "========================================"

# ── 颜色 ──
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# ── 操作系统检测 ──
if [ -f /etc/debian_version ]; then
    OS="debian"; PKG_MGR="apt-get"
elif [ -f /etc/redhat-release ]; then
    OS="rhel";   PKG_MGR="yum"
else
    error "不支持的操作系统"
fi
info "检测到: $OS 系统"

# ── root 检查 ──
[ "$EUID" -ne 0 ] && error "请使用 root 权限运行: sudo bash install.sh"

# ── 交互式输入（如果环境变量未提供）───────────
# 数据库
DB_HOST="${DB_HOST:-}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-}"
DB_USER="${DB_USER:-}"
DB_PASS="${DB_PASS:-}"

if [ -z "$DB_HOST" ]; then
    read -p "数据库地址 [localhost]: " _input; DB_HOST="${_input:-localhost}"
fi
if [ -z "$DB_NAME" ]; then
    read -p "数据库名 [engineering_new]: " _input; DB_NAME="${_input:-engineering_new}"
fi
if [ -z "$DB_USER" ]; then
    read -p "数据库用户名 [engineer]: " _input; DB_USER="${_input:-engineer}"
fi
if [ -z "$DB_PASS" ]; then
    read -s -p "数据库密码: " DB_PASS; echo ""
    [ -z "$DB_PASS" ] && error "数据库密码不能为空"
fi

# 邮件服务（可选）
read -p "SMTP主机（留空跳过邮件配置）[smtp.qq.com]: " SMTP_HOST
SMTP_HOST="${SMTP_HOST:-smtp.qq.com}"
read -p "SMTP端口 [587]: " SMTP_PORT
SMTP_PORT="${SMTP_PORT:-587}"
read -p "SMTP用户名: " SMTP_USER
read -s -p "SMTP密码: " SMTP_PASS; echo ""
read -p "发件人邮箱: " SMTP_FROM
read -p "启用TLS [true]: " SMTP_TLS
SMTP_TLS="${SMTP_TLS:-true}"

# 域名
read -p "系统域名（留空=仅用IP访问）[${SERVER_IP:-}]: " SERVER_DOMAIN
SERVER_DOMAIN="${SERVER_DOMAIN:-}"
if [ -n "$SERVER_DOMAIN" ]; then
    read -p "是否自动申请 Let's Encrypt SSL证书 [y/N]: " DO_SSL
    DO_SSL="${DO_SSL:-N}"
fi

# 管理员密码
ADMIN_PASS="${ADMIN_PASS:-}"
if [ -z "$ADMIN_PASS" ]; then
    read -s -p "管理员初始密码 [admin123]: " ADMIN_PASS; echo ""
    ADMIN_PASS="${ADMIN_PASS:-admin123}"
fi

NGINX_PORT="${NGINX_PORT:-80}"
APP_DIR="/opt/green-engineering"
SERVICE_USER="green"
SERVICE_NAME="green-gunicorn"

info ""
info "配置汇总:"
info "  数据库:    ${DB_HOST}:${DB_PORT}/${DB_NAME}"
info "  域名:      ${SERVER_DOMAIN:-未配置（仅IP访问）}"
info "  邮件SMTP:  ${SMTP_USER:+已配置} ${SMTP_HOST}"
info "  SSL证书:   ${DO_SSL:-N}"
info ""

# ── 1. 安装系统依赖 ──
info "[1/8] 安装系统依赖..."
if [ "$OS" = "debian" ]; then
    $PKG_MGR update -qq
    $PKG_MGR install -y -q python3.11 python3.11-venv python3-pip \
        postgresql postgresql-client nginx certbot python3-certbot-nginx \
        libpq-dev curl > /dev/null 2>&1
else
    $PKG_MGR install -y -q python3 python3-pip postgresql postgresql-server nginx \
        libpq-devel curl > /dev/null 2>&1
    postgresql-setup initdb > /dev/null 2>&1 || true
fi
systemctl enable postgresql > /dev/null 2>&1 || true
systemctl start postgresql 2>/dev/null || true

# ── 2. 初始化数据库 ──
info "[2/8] 初始化 PostgreSQL..."
sleep 2
su - postgres -c "psql -c \"CREATE USER $DB_USER WITH PASSWORD '$DB_PASS';\"" 2>/dev/null || true
su - postgres -c "psql -c \"CREATE DATABASE $DB_NAME OWNER $DB_USER;\"" 2>/dev/null || true
su - postgres -c "psql -c \"ALTER USER $DB_USER CREATEDB;\"" 2>/dev/null || true

# ── 3. 安装应用 ──
info "[3/8] 安装应用到 $APP_DIR..."
mkdir -p "$APP_DIR"
cp -r . "$APP_DIR/" 2>/dev/null || true
cd "$APP_DIR"

# 生成 SECRET_KEY
SECRET_KEY=$(python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")

python3.11 -m venv venv 2>/dev/null || python3 -m venv venv
source venv/bin/activate
pip install -q -r requirements.txt gunicorn > /dev/null 2>&1

# ── 4. 配置环境变量 ──
info "[4/8] 写入环境变量配置..."
ALLOWED_HOSTS="${SERVER_DOMAIN:+$SERVER_DOMAIN,}localhost,127.0.0.1"
CSRF_ORIGINS="http://${SERVER_DOMAIN:-localhost}"
[ -n "$SERVER_DOMAIN" ] && CSRF_ORIGINS="$CSRF_ORIGINS,https://$SERVER_DOMAIN"

cat > "$APP_DIR/.env" << EOF
DEBUG=False
SECRET_KEY=$SECRET_KEY
ALLOWED_HOSTS=$ALLOWED_HOSTS
DATABASE_URL=postgres://$DB_USER:$DB_PASS@$DB_HOST:$DB_PORT/$DB_NAME
CSRF_TRUSTED_ORIGINS=$CSRF_ORIGINS
DEPLOY_MODE=standalone
# 邮件配置
EMAIL_HOST=$SMTP_HOST
EMAIL_PORT=$SMTP_PORT
EMAIL_HOST_USER=$SMTP_USER
EMAIL_HOST_PASSWORD=$SMTP_PASS
EMAIL_USE_TLS=$SMTP_TLS
DEFAULT_FROM_EMAIL=${SMTP_FROM:-noreply@$SERVER_DOMAIN}
EOF

# 站点域名写入数据库配置（用 settings_pg 模板）
if [ -n "$SERVER_DOMAIN" ]; then
    echo "SITE_DOMAIN=$SERVER_DOMAIN" >> "$APP_DIR/.env"
fi

# ── 5. 数据库迁移 ──
info "[5/8] 执行数据库迁移..."
cd "$APP_DIR"
source venv/bin/activate
python manage.py migrate --noinput 2>&1 | tail -3

# ── 6. 创建管理员（如不存在）──
info "[6/8] 创建管理员账户..."
python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@$SERVER_DOMAIN', '$ADMIN_PASS')
    print('  admin 用户已创建')
else:
    print('  admin 用户已存在')
" 2>&1 | grep -v "^SystemCheckError"

# ── 7. 收集静态文件 ──
info "[7/8] 收集静态文件..."
mkdir -p /var/www/static
python manage.py collectstatic --noinput > /dev/null 2>&1
chown -R www-data:www-data /var/www/static 2>/dev/null || true

# ── 8. 配置 Nginx ──
info "[8/8] 配置 Nginx..."
_NGINX_CONFIG="/etc/nginx/sites-available/green"
cat > "$_NGINX_CONFIG" << EOF
upstream green_app {
    server 127.0.0.1:8001;
}

server {
    listen $NGINX_PORT;
    server_name ${SERVER_DOMAIN:-_};
    client_max_body_size 100M;

    location /static/ {
        alias /var/www/static/;
        expires 30d;
    }

    location / {
        proxy_pass         http://green_app;
        proxy_set_header   Host \$host;
        proxy_set_header   X-Real-IP \$remote_addr;
        proxy_set_header   X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto \$scheme;
        proxy_redirect     off;
    }
}
EOF

ln -sf "$_NGINX_CONFIG" /etc/nginx/sites-enabled/green
rm -f /etc/nginx/sites-enabled/default 2>/dev/null
nginx -t || { error "Nginx 配置语法错误"; }
systemctl reload nginx

# ── Gunicorn systemd ──
info "配置 systemd 服务..."
mkdir -p "$APP_DIR/logs"
id "$SERVICE_USER" &>/dev/null || useradd -r -m -s /bin/bash "$SERVICE_USER"
chown -R "$SERVICE_USER:$SERVICE_USER" "$APP_DIR"

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

systemctl daemon-reload
systemctl enable $SERVICE_NAME
systemctl restart $SERVICE_NAME

# ── 防火墙 ──
info "配置防火墙..."
if [ "$OS" = "debian" ]; then
    which ufw &>/dev/null && ufw allow $NGINX_PORT/tcp && ufw allow 8001/tcp
else
    which firewall-cmd &>/dev/null && firewall-cmd --add-port=$NGINX_PORT/tcp --add-port=8001/tcp 2>/dev/null || true
fi

# ── SSL 证书申请（可选）──
if [ "$DO_SSL" = "y" ] || [ "$DO_SSL" = "Y" ]; then
    info "申请 Let's Encrypt SSL 证书..."
    if command -v certbot &>/dev/null; then
        certbot certonly --standalone --non-interactive --agree-tos \
            -d "$SERVER_DOMAIN" -m "${SMTP_FROM:-admin@$SERVER_DOMAIN}" \
            --pre-hook "systemctl stop nginx" \
            --post-hook "systemctl start nginx" \
            2>&1 | tail -3 || warn "SSL 证书申请失败，请检查域名 DNS 是否已解析"
    else
        warn "certbot 未安装，跳过 SSL 申请"
    fi
fi

# ── 完成 ──
info ""
info "========================================"
info "✅ 安装完成！"
info "========================================"
ACCESS_URL="http://${SERVER_DOMAIN:-localhost}/"
[ -n "$SERVER_DOMAIN" ] && ACCESS_URL="http://${SERVER_DOMAIN}/"
info "访问地址: $ACCESS_URL"
info "管理员账号: admin"
info "管理员密码: $ADMIN_PASS"
info ""
info "后续配置（在系统管理 → 系统参数 中填写）："
[ -n "$SERVER_DOMAIN" ] && info "  域名: site_domain = $SERVER_DOMAIN"
info "  邮件: email_smtp_host = $SMTP_HOST"
info "  邮件: email_smtp_user = $SMTP_USER"
[ -n "$SERVER_DOMAIN" ] && info "  SSL:  bash ssl-setup.sh $SERVER_DOMAIN"
info ""
info "常用命令:"
echo "  systemctl status $SERVICE_NAME  # 查看状态"
echo "  journalctl -u $SERVICE_NAME -f  # 查看日志"
echo "  cd $APP_DIR && source venv/bin/activate"
info "========================================"
