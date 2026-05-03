#!/bin/bash
# ============================================================
# SSL 证书自动申请脚本（Let's Encrypt / Certbot）
# 用法: bash ssl-setup.sh <域名> [邮箱]
# 示例: bash ssl-setup.sh example.com admin@example.com
# ============================================================
set -e

DOMAIN="${1?用法: bash ssl-setup.sh <域名> [邮箱]}"
EMAIL="${2:-admin@${DOMAIN}}"
CERT_DIR="/etc/letsencrypt/live/${DOMAIN}"
WEBROOT="/var/www/static"

echo "=== SSL 证书申请工具 ==="
echo "域名: ${DOMAIN}"
echo "邮箱: ${EMAIL}"
echo ""

# 检查 root 权限
if [ "$EUID" -ne 0 ]; then
    echo "❌ 请使用 root 权限运行: sudo bash ssl-setup.sh ${DOMAIN} ${EMAIL}"
    exit 1
fi

# 1. 安装 certbot
echo "[1/5] 安装 certbot ..."
if command -v certbot &>/dev/null; then
    echo "  certbot 已安装，跳过"
else
    apt-get update -qq
    apt-get install -y -qq certbot python3-certbot-nginx || apt-get install -y -qq certbot
fi

# 2. 申请证书（standalone 模式，暂不支持 Nginx 反代）
echo "[2/5] 申请 Let's Encrypt 证书 ..."
if [ -d "$CERT_DIR" ]; then
    echo "  证书已存在: ${CERT_DIR}"
    echo "  如需重新申请，请先: rm -rf ${CERT_DIR}"
else
    certbot certonly --standalone \
        --non-interactive --agree-tos --email "${EMAIL}" -d "${DOMAIN}" \
        --pre-hook "systemctl stop nginx || true" \
        --post-hook "systemctl start nginx || true" \
        || { echo "❌ 证书申请失败，域名 DNS 是否已解析到本服务器？"; exit 1; }
fi

# 3. 验证证书存在
echo "[3/5] 验证证书文件 ..."
if [ -f "${CERT_DIR}/fullchain.pem" ] && [ -f "${CERT_DIR}/privkey.pem" ]; then
    echo "  ✅ 证书路径: ${CERT_DIR}/fullchain.pem"
    echo "  ✅ 私钥路径: ${CERT_DIR}/privkey.pem"
else
    echo "❌ 证书文件不完整"
    exit 1
fi

# 4. 生成 Nginx HTTPS 配置
echo "[4/5] 生成 HTTPS Nginx 配置 ..."
cat > /etc/nginx/sites-available/engineering-https <<EOF
# HTTPS 配置（自动生成 by ssl-setup.sh）
# 域名: ${DOMAIN}
upstream engineering_app {
    server 127.0.0.1:8001;
}

server {
    listen 80;
    server_name ${DOMAIN};
    # HTTP 强制跳转 HTTPS
    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name ${DOMAIN};

    ssl_certificate     ${CERT_DIR}/fullchain.pem;
    ssl_certificate_key ${CERT_DIR}/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;

    client_max_body_size 20M;

    location /static/ {
        alias /var/www/static/;
        expires 30d;
    }

    location /media/ {
        alias /var/www/media/;
        expires 30d;
    }

    location / {
        proxy_pass         http://engineering_app;
        proxy_set_header   Host \$host;
        proxy_set_header   X-Real-IP \$remote_addr;
        proxy_set_header   X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto \$scheme;
        proxy_redirect     off;
    }
}
EOF

# 5. 启用配置
echo "[5/5] 启用 HTTPS 配置 ..."
ln -sf /etc/nginx/sites-available/engineering-https /etc/nginx/sites-enabled/engineering-https
rm -f /etc/nginx/sites-enabled/default  # 移除默认站
nginx -t && systemctl reload nginx

# 6. 设置自动续期
echo ""
echo "=== 设置自动续期 ==="
(crontab -l 2>/dev/null | grep -v certbot; echo "0 3 * * * certbot renew --quiet --deploy-hook 'systemctl reload nginx'") | crontab -
echo "  ✅ 已添加 crontab: 每天凌晨3点检查续期"

# 7. 输出结果
echo ""
echo "=== ✅ SSL 配置完成 ==="
echo "  域名:      https://${DOMAIN}"
echo "  证书路径:  ${CERT_DIR}/fullchain.pem"
echo "  私钥路径:  ${CERT_DIR}/privkey.pem"
echo ""
echo "现在请在系统设置中填写以下配置项（系统管理 → 系统参数）："
echo "  site_domain          = ${DOMAIN}"
echo "  site_https_enabled  = true"
echo "  ssl_cert_path       = ${CERT_DIR}/fullchain.pem"
echo "  ssl_key_path        = ${CERT_DIR}/privkey.pem"
echo ""
echo "重启 Gunicorn 使配置生效:"
echo "  systemctl restart engineering-gunicorn"
