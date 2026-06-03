"""
共享基础配置 — 所有环境的公共配置集中于此。

各环境仅需覆盖差异项（如 DEBUG、DATABASES、CSRF_TRUSTED_ORIGINS 等），
新增公共配置请加在此文件。
"""

import os
import logging
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent


# ── 从 .env 文件读取（如存在） ──────────────────────────────
def _load_env():
    env_path = BASE_DIR / '.env'
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, val = line.split('=', 1)
                    os.environ.setdefault(key.strip(), val.strip())


_load_env()

# ── Django 核心 ──────────────────────────────────────────
SECRET_KEY = os.environ.get('SECRET_KEY')

DEBUG = os.environ.get('DEBUG', 'False') == 'True'

X_FRAME_OPTIONS = 'SAMEORIGIN'
CSRF_COOKIE_SECURE = False  # 内部系统；部署 HTTPS 后改为 True
CSRF_COOKIE_HTTPONLY = False  # 允许前端 JS 读取 token（配合 csrftoken cookie）

ALLOWED_HOSTS = [h.strip() for h in os.environ.get('ALLOWED_HOSTS', '*').split(',') if h.strip()]

# ── 已安装应用 ────────────────────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third party
    'rest_framework',
    'corsheaders',
    'django_filters',
    'drf_spectacular',
    # Local apps
    'apps.core',
    'apps.tasks',
    'apps.approvals',
    'apps.notifications',
    'apps.channels',
    'apps.finance',
    'apps.crm',
    'apps.files',
    'apps.material',
    'apps.equipment',
    'apps.purchasing',
    'apps.repair',
]

AUTH_USER_MODEL = 'core.User'

# ── 中间件 ────────────────────────────────────────────────
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'apps.core.middleware.CompanyContextMiddleware',
    'apps.core.audit.AuditRequestMiddleware',
    'apps.core.middleware_timing.RequestTimingMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# ── Session ───────────────────────────────────────────────
SESSION_COOKIE_AGE = 60 * 60 * 24 * 30  # 30 天
SESSION_COOKIE_NAME = 'engineering_sessionid'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_SAVE_EVERY_REQUEST = False

# ── URL / 模板 / WSGI ────────────────────────────────────
ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.core.context_processors.menu_permissions',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# ── 密码校验 ──────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ── 国际化 ────────────────────────────────────────────────
LANGUAGE_CODE = 'zh-hans'
TIME_ZONE = 'Asia/Shanghai'
USE_I18N = True
USE_TZ = True

# ── 静态 / 媒体文件 ──────────────────────────────────────
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'company_files'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── CORS ──────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = [h.strip() for h in os.environ.get('CORS_ALLOWED_ORIGINS', '').split(',') if h.strip()]

# ── 默认公司（无 session 时降级用） ─────────────────────
DEFAULT_COMPANY_ID = os.environ.get('DEFAULT_COMPANY_ID', None)
if DEFAULT_COMPANY_ID:
    DEFAULT_COMPANY_ID = int(DEFAULT_COMPANY_ID)

# ── REST Framework ───────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'apps.core.auth.CSRFExemptSessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'EXCEPTION_HANDLER': 'apps.core.exceptions.unified_exception_handler',
}

# ── API 文档 ──────────────────────────────────────────────
SPECTACULAR_SETTINGS = {
    'TITLE': '企业信息化管理系统 API',
    'DESCRIPTION': """
GREEN 企业信息化管理系统 RESTful API

## 认证说明
- 登录后 cookie 会话自动携带（credentials: include）
- 需 CSRF 保护的操作请从 `/api/auth/status/` 获取 csrftoken

## 通用筛选参数
- `page` / `page_size` — 分页
- `search` — 全文搜索
- `ordering` — 排序字段，如 `ordering=-created_at`

## 错误响应
所有错误以统一 JSON 格式返回：
- `code`: 错误码（1001-5000）
- `message`: 错误描述
- `detail`: 字段级校验详情（可选）

错误码：1001=未登录 1004=权限不足 2001=校验失败 2002=资源不存在 2003=资源已存在 2004=状态不允许 5000=内部错误

## 数据格式
- 请求：`Content-Type: application/json`，POST/PATCH body 为 JSON
- 响应：分页格式 `{ "count": N, "next": "...", "previous": "...", "results": [...] }`
    """,
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'TAGS': [
        {'name': 'auth', 'description': '认证 — 登录/登出/注册/密码重置'},
        {'name': 'core', 'description': '系统核心 — 用户/权限/公司/审计日志/系统设置/通知'},
        {'name': 'finance', 'description': '财务 — 公司/收入/支出/发票/工资/员工/社保/应收应付/预算/银行账户'},
        {'name': 'crm', 'description': '客户关系 — 客户/合同/供应商，含Excel导入'},
        {'name': 'tasks', 'description': '任务与审批 — 项目/任务/审批流/审批实例/评论/附件'},
        {'name': 'approvals', 'description': '审批模板 — 审批流模板/节点模板定义'},
        {'name': 'equipment', 'description': '设备管理 — 设备台账/BOM关系'},
        {'name': 'material', 'description': '物料管理 — 物料台账/库存/使用记录'},
        {'name': 'files', 'description': '文件管理 — 文件分类/上传/下载'},
        {'name': 'notifications', 'description': '通知管理 — 通知渠道/绑定/发送/日志'},
    ],
    'POSTPROCESSING_HOOKS': [
        'config.schema.autogenerate_chinese_summary',
    ],
}

# ── 性能监控（Sentry — 可选）───────────────────────────────
SENTRY_DSN = os.environ.get('SENTRY_DSN', '')
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            DjangoIntegration(),
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
        send_default_pii=False,  # 不发送用户 PII
        traces_sample_rate=float(os.environ.get('SENTRY_TRACES_SAMPLE_RATE', '0.1')),
        profiles_sample_rate=float(os.environ.get('SENTRY_PROFILES_SAMPLE_RATE', '0.0')),
    )

# ── 请求耗时监控 ──────────────────────────────────────────
SLOW_REQUEST_THRESHOLD_MS = int(os.environ.get('SLOW_REQUEST_THRESHOLD_MS', '500'))

# ── 邮件 ──────────────────────────────────────────────────
EMAIL_BACKEND = os.environ.get(
    'EMAIL_BACKEND',
    'django.core.mail.backends.console.EmailBackend',
)
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.example.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True').lower() in ('true', '1', 'yes')
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get(
    'DEFAULT_FROM_EMAIL',
    '企业信息化管理系统 <noreply@eng-system.com>',
)


# ── AI 服务层 ─────────────────────────────────────────────
AI_SERVICE = {
    'active_model': 'deepseek-chat',
    'fallback_model': None,
    'request_timeout': 120,
    'max_retries': 3,
    'cache_ttl': 0,
    'models': {
        'deepseek-chat': {
            'provider': 'deepseek',
            'display_name': 'DeepSeek Chat',
            'model': 'deepseek-chat',
            'max_tokens': 8192,
            'supports_vision': False,
        },
        'gpt-4o': {
            'provider': 'openai',
            'display_name': 'GPT-4o',
            'model': 'gpt-4o',
            'max_tokens': 16384,
            'supports_vision': True,
        },
        'claude-sonnet': {
            'provider': 'anthropic',
            'display_name': 'Claude Sonnet',
            'model': 'claude-sonnet-4-20250514',
            'max_tokens': 8192,
            'supports_vision': True,
        },
        'qwen-plus': {
            'provider': 'qwen',
            'display_name': '通义千问 Plus',
            'model': 'qwen-plus',
            'max_tokens': 16384,
            'supports_vision': True,
        },
    },
    'api_key_sources': {
        'deepseek': 'DEEPSEEK_API_KEY',
        'openai': 'OPENAI_API_KEY',
        'anthropic': 'ANTHROPIC_API_KEY',
        'qwen': 'QWEN_API_KEY',
    },
}

