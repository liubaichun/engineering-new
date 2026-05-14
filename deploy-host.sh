#!/bin/bash
# ============================================================
# GREEN ERP — Host模式标准化部署脚本
# 适用：全新部署或日常更新
#
# 用法：
#   bash deploy-host.sh                    # 交互式（全新部署引导）
#   bash deploy-host.sh --non-interactive  # 自动模式（已有.env）
# ============================================================

set -e

APP_DIR="/root/engineering-new"
SERVICE_NAME="engineering-gunicorn"
VENV_PYTHON="$APP_DIR/venv/bin/python"
VENV_PIP="$APP_DIR/venv/bin/pip"
GUNICORN_PORT="${GUNICORN_PORT:-8001}"
HEALTH_URL="http://127.0.0.1:$GUNICORN_PORT/api/core/health/"

# 颜色输出
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error(){ echo -e "${RED}[ERROR]${NC} $1"; }

# ── 检查：以root运行 ───────────────────────────────────
if [ "$EUID" -ne 0 ]; then
    log_error "请以 root 运行此脚本"
    exit 1
fi

# ── 检查：Python venv是否存在 ──────────────────────────
if [ ! -f "$VENV_PYTHON" ]; then
    log_error "虚拟环境不存在：$VENV_PYTHON"
    log_info "创建虚拟环境..."
    python3 -m venv "$APP_DIR/venv"
    $VENV_PIP install --upgrade pip
fi

# ── 全新部署引导（.env不存在时）───────────────────────
if [ ! -f "$APP_DIR/.env" ] && [ ! -f "/etc/engineering-env" ]; then
    log_warn "未检测到 .env 或 /etc/engineering-env，执行全新部署引导..."

    read -rp "请输入服务器公网IP: " SERVER_IP
    read -rp "输入 PostgreSQL 密码: " PG_PASS
    read -rp "输入 Redis 密码: " REDIS_PASS
    read -rp "输入 Django SECRET_KEY（至少50字符）: " SECRET_KEY
    read -rp "输入超级管理员密码: " ADMIN_PASS

    ENV_CONTENT="
DEBUG=False
SECRET_KEY=$SECRET_KEY
ALLOWED_HOSTS=$SERVER_IP,localhost,127.0.0.1
PG_USER=engineer
PG_PASSWORD=$PG_PASS
PG_DATABASE=engineering_new
PG_HOST=localhost
REDIS_PASSWORD=$REDIS_PASS
ADMIN_USERNAME=admin
ADMIN_PASSWORD=$ADMIN_PASS
ADMIN_EMAIL=admin@example.com
"

    echo "$ENV_CONTENT" > "$APP_DIR/.env"
    echo "$ENV_CONTENT" > /etc/engineering-env
    log_info ".env 和 /etc/engineering-env 已创建"
fi

# ── 1. 拉取最新代码 ────────────────────────────────────
log_info "拉取最新代码..."
cd "$APP_DIR"
git fetch origin master
CURRENT=$(git rev-parse HEAD)
UPSTREAM=$(git rev-parse origin/master)
if [ "$CURRENT" = "$UPSTREAM" ]; then
    log_info "代码已是最新，无需更新"
else
    git reset --hard origin/master
    log_info "代码已更新到最新 commit"
fi

# ── 2. 安装/更新依赖 ──────────────────────────────────
log_info "安装依赖..."
$VENV_PIP install -r requirements.txt -q

# ── 3. 执行数据库迁移 ──────────────────────────────────
log_info "执行数据库迁移..."
$VENV_PYTHON manage.py migrate --noinput

# ── 4. 收集静态文件 ────────────────────────────────────
log_info "收集静态文件..."
$VENV_PYTHON manage.py collectstatic --noinput --clear 2>/dev/null || true

# ── 5. 重启 Gunicorn ───────────────────────────────────
log_info "重启 $SERVICE_NAME..."
if systemctl is-active --quiet "$SERVICE_NAME"; then
    systemctl restart "$SERVICE_NAME"
else
    log_warn "$SERVICE_NAME 未运行，尝试启动..."
    systemctl restart "$SERVICE_NAME"
fi

# ── 6. 健康检查 ────────────────────────────────────────
log_info "等待服务启动..."
sleep 3
for i in {1..10}; do
    HTTP_CODE=$(curl -sf -o /dev/null -w "%{http_code}" "$HEALTH_URL" 2>/dev/null || echo "000")
    if [ "$HTTP_CODE" = "200" ]; then
        log_info "健康检查通过！HTTP $HTTP_CODE"
        break
    fi
    if [ "$i" -eq 10 ]; then
        log_error "健康检查失败（HTTP $HTTP_CODE），请检查日志："
        log_error "  journalctl -u $SERVICE_NAME -n 30"
        exit 1
    fi
    sleep 2
done

# ── 7. 显示结果 ────────────────────────────────────────
NEW_COMMIT=$(git rev-parse --short origin/master)
log_info "═══════════════════════════════════════"
log_info "  部署完成"
log_info "  版本: $NEW_COMMIT"
log_info "  服务: http://localhost:$GUNICORN_PORT"
log_info "  健康检查: $HEALTH_URL"
log_info "  部署日志: journalctl -u $SERVICE_NAME -f"
log_info "═══════════════════════════════════════"
