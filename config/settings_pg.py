"""
PostgreSQL生产配置
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# 从 .env 文件读取配置
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

SECRET_KEY = os.environ.get('SECRET_KEY', 'h06uLptG8EmilFtVJjiEFdnpro0qx3UGvpdGwkRZCUqToG7ZbCPHD_cZXtPJA6M-DJozdLjhAOkC7LBosnJJew')
DEBUG = os.environ.get('DEBUG', 'False').lower() in ('true', '1', 'yes')
ALLOWED_HOSTS = [h.strip() for h in os.environ.get("ALLOWED_HOSTS", "124.222.227.37,43.156.139.37,localhost,127.0.0.1").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = ["https://43.156.139.37", "https://124.222.227.37", "https://localhost", "https://127.0.0.1"]
X_FRAME_OPTIONS = 'SAMEORIGIN'

INSTALLED_APPS = [
    'django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes',
    'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles',
    'rest_framework', 'corsheaders', 'django_filters', 'drf_spectacular',
    'apps.core', 'apps.tasks', 'apps.approvals', 'apps.notifications',
    'apps.finance', 'apps.crm', 'apps.files', 'apps.material', 'apps.equipment',
    'apps.purchasing', 'apps.repair',
]

AUTH_USER_MODEL = 'core.User'
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'apps.core.middleware.CompanyContextMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'apps.core.audit.AuditRequestMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
SESSION_COOKIE_AGE = 60 * 60 * 24 * 30
SESSION_COOKIE_NAME = 'engineering_sessionid'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_SAVE_EVERY_REQUEST = True
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
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('PG_DATABASE', 'engineering_new'),
        'USER': os.environ.get('PG_USER', 'engineer'),
        'PASSWORD': os.environ.get('PG_PASSWORD', 'engineer123'),
        'HOST': os.environ.get('PG_HOST', 'localhost'),
        'PORT': os.environ.get('PG_PORT', '5432'),
        'OPTIONS': {'connect_timeout': 10},
    }
}
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
LANGUAGE_CODE = 'zh-hans'
TIME_ZONE = 'Asia/Shanghai'
USE_I18N = True
USE_TZ = True
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'company_files'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
CORS_ALLOWED_ORIGINS = [h.strip() for h in os.environ.get('CORS_ALLOWED_ORIGINS', '').split(',') if h.strip()]

# ─── 租户模式配置 ───
# 'subscription' = 租赁版（多租户SaaS，注册入口开放，需审批）
# 'standalone'   = 买断版（单公司部署，注册入口关闭，直接使用预置公司）
TENANT_MODE = os.environ.get('TENANT_MODE', 'subscription')

# 买断版专用：指定系统使用的默认公司ID（standalone模式必填）
DEFAULT_COMPANY_ID = os.environ.get('DEFAULT_COMPANY_ID', None)
if DEFAULT_COMPANY_ID:
    DEFAULT_COMPANY_ID = int(DEFAULT_COMPANY_ID)

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ['apps.core.auth.CSRFExemptSessionAuthentication'],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.example.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True').lower() in ('true', '1', 'yes')
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', '企业管理信息系统 <noreply@eng-system.com>')
