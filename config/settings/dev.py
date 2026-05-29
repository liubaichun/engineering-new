"""
开发环境配置 — 覆盖 base 中的差异项。

使用方式：
  export DJANGO_SETTINGS_MODULE=config.settings.dev
  python manage.py runserver
"""

from .base import *

# 开发环境默认开启调试
DEBUG = os.environ.get('DEBUG', 'True') == 'True'

# 开发环境数据库：优先用本地 PostgreSQL（从 .env 读），无配置时降级 SQLite
DATABASES = {
    'default': {
        'ENGINE': os.environ.get('DB_ENGINE', 'django.db.backends.postgresql'),
        'NAME': os.environ.get('PG_DATABASE', 'engineering_new'),
        'USER': os.environ.get('PG_USER', 'engineer'),
        'PASSWORD': os.environ.get('PG_PASSWORD', 'engineer123'),
        'HOST': os.environ.get('PG_HOST', 'localhost'),
        'PORT': os.environ.get('PG_PORT', '5432'),
    }
}
