"""
生产环境配置 — 覆盖 base 中的差异项。

通过 .env 文件或环境变量驱动，所有服务器使用同一份代码，
差异仅在于 .env（ALLOWED_HOSTS、数据库密码等）。

使用方式：
  export DJANGO_SETTINGS_MODULE=config.settings.prod
  gunicorn config.wsgi:application ...

📌 SaaS 扩展入口：若要支持多租户动态配置，在此文件顶部插入
   `from .saas import *` 即可加载租户路由；无需改造 base。
"""
from .base import *

# 生产环境默认关闭调试
DEBUG = os.environ.get('DEBUG', 'False') == 'True'

# ── 安全加固（等保二级） ─────────────────────────────────
# 部署 HTTPS 后取消以下注释：
# SECURE_HSTS_SECONDS = 31536000
# SECURE_HSTS_INCLUDE_SUBDOMAINS = True
# SECURE_SSL_REDIRECT = True
# SESSION_COOKIE_SECURE = True
# CSRF_COOKIE_SECURE = True

CSRF_TRUSTED_ORIGINS = [
    h.strip()
    for h in os.environ.get('CSRF_TRUSTED_ORIGINS', '').split(',')
    if h.strip()
]

# ── 生产数据库（PostgreSQL） ──────────────────────────────
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('PG_DATABASE', 'engineering_new'),
        'USER': os.environ.get('PG_USER', 'engineer'),
        'PASSWORD': os.environ.get('PG_PASSWORD', 'engineer123'),
        'HOST': os.environ.get('PG_HOST', 'localhost'),
        'PORT': os.environ.get('PG_PORT', '5432'),
        'OPTIONS': {
            'connect_timeout': 10,
        },
        'CONN_MAX_AGE': None,    # 强制新建连接，让 statement_timeout 生效
        'CONN_HEALTH_CHECKS': True,
    }
}

# ── 日志 ──────────────────────────────────────────────────
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'level': 'WARNING',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'maxBytes': 10 * 1024 * 1024,  # 10MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
}
