from django.apps import AppConfig
from importlib import import_module
from django.conf import settings


# 哪些 app_label 跳过（无业务模块的辅助app）
SKIP_APPS = {
    'django.contrib.admin', 'django.contrib.auth',
    'django.contrib.contenttypes', 'django.contrib.sessions',
    'django.contrib.messages', 'django.contrib.staticfiles',
    'rest_framework', 'django_filters', 'corsheaders',
    'drf_spectacular', 'drf_spectacular_sidecar',
    'apps.channels',  # 通知渠道系统，不是业务模块
}


def auto_discover():
    """扫描所有 INSTALLED_APPS，import 其 modules.py（如果存在）"""
    imported = []
    for app_label in settings.INSTALLED_APPS:
        if app_label in SKIP_APPS:
            continue
        try:
            import_module(f'{app_label}.modules')
            imported.append(app_label)
        except ModuleNotFoundError:
            pass  # 没有 modules.py 的 app 跳过
        except Exception:
            pass  # 其他错误跳过
    return imported


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'
    verbose_name = '核心模块'

    def ready(self):
        import os
        if os.environ.get('DISABLE_AUDIT') == '1':
            return  # loaddata 时禁用，避免审计日志 FK 错误导致事务中断

        # 启动时自动连接所有模型的审计信号
        from apps.core import audit
        audit.autodiscover()

        # ── Phase2 权限矩阵自注册 ────────────────────────────────
        from django.db.models.signals import post_migrate
        post_migrate.connect(_sync_modules_on_migrate, sender=self)

        # 启动后立即同步模块到 DB（每次启动都跑）
        try:
            imported = auto_discover()
            from apps.core.models import sync_modules_to_db
            sync_modules_to_db()
        except Exception:
            pass  # 表不存在时跳过


def _sync_modules_on_migrate(sender, **kwargs):
    """post_migrate 信号的处理器：将已注册的模块写入 DB"""
    from apps.core.models import sync_modules_to_db
    auto_discover()
    sync_modules_to_db()
