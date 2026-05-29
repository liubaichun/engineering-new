"""
共享基础配置 — 所有环境的公共配置集中于此。

各环境仅需覆盖差异项（如 DEBUG、DATABASES、CSRF_TRUSTED_ORIGINS 等），
新增公共配置请加在此文件。
"""
import os
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

ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get('ALLOWED_HOSTS', '*').split(',')
    if h.strip()
]

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
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'apps.core.middleware.CompanyContextMiddleware',
    'apps.core.audit.AuditRequestMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# ── Session ───────────────────────────────────────────────
SESSION_COOKIE_AGE = 60 * 60 * 24 * 30   # 30 天
SESSION_COOKIE_NAME = 'engineering_sessionid'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_SAVE_EVERY_REQUEST = True

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
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'company_files'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── CORS ──────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = [
    h.strip()
    for h in os.environ.get('CORS_ALLOWED_ORIGINS', '').split(',')
    if h.strip()
]

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
}

# ── API 文档 ──────────────────────────────────────────────
SPECTACULAR_SETTINGS = {
    'TITLE': '企业信息化管理系统 API',
    'DESCRIPTION': '''
GREEN 企业信息化管理系统 RESTful API

## 认证说明
- 登录后 cookie 会话自动携带（credentials: include）
- 需 CSRF 保护的操作请从 `/api/auth/status/` 获取 csrftoken

## 通用筛选参数
- `page` / `page_size` — 分页
- `search` — 全文搜索
- `ordering` — 排序字段，如 `ordering=-created_at`

## 数据格式
- 请求：`Content-Type: application/json`，POST/PATCH body 为 JSON
- 响应：分页格式 `{ "count": N, "next": "...", "previous": "...", "results": [...] }`
    ''',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'TAGS': [
        {'name': 'auth', 'description': '认证相关 — 登录/登出/注册/密码重置'},
        {'name': 'core-user', 'description': '用户管理 — 用户 CRUD / 注册审批 / 密码重置 / 角色分配'},
        {'name': 'core-permission', 'description': '权限管理 — 权限定义 CRUD'},
        {'name': 'core-audit', 'description': '审计日志 — 操作日志 / 登录日志 / 权限变更记录'},
        {'name': 'core-setting', 'description': '系统参数 — 审批规则 / 工资规则'},
        {'name': 'core-notification', 'description': '站内通知 — 通知列表 / 标记已读'},
        {'name': 'finance-company', 'description': '公司管理 — 公司信息 / 多租户'},
        {'name': 'finance-income', 'description': '收入管理 — 收入记录 / 审批流'},
        {'name': 'finance-expense', 'description': '支出管理 — 支出记录 / 审批流'},
        {'name': 'finance-invoice', 'description': '发票管理 — 发票开具与作废'},
        {'name': 'finance-wage', 'description': '工资管理 — 工资记录 / 税务计算 / 社保'},
        {'name': 'finance-employee', 'description': '员工管理 — 员工信息'},
        {'name': 'crm-client', 'description': '客户管理 — 客户信息'},
        {'name': 'crm-contract', 'description': '合同管理 — 合同信息'},
        {'name': 'crm-supplier', 'description': '供应商管理 — 供应商信息'},
        {'name': 'tasks-project', 'description': '项目管理 — 项目 CRUD'},
        {'name': 'tasks-task', 'description': '任务管理 — 任务看板'},
        {'name': 'approvals', 'description': '审批管理 — 审批流 / 审批历史'},
        {'name': 'equipment', 'description': '设备管理 — 设备台账'},
        {'name': 'material', 'description': '物料管理 — 物料台账'},
        {'name': 'files', 'description': '文件管理 — 文件上传 / 下载'},
    ],
    'POSTPROCESSING_HOOKS': [
        'config.schema.autogenerate_chinese_summary',
    ],
}

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
