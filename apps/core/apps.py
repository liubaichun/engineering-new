from django.apps import AppConfig


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
        # 在 post_migrate 信号中把已注册的模块同步到 DB
        # finance.modules 必须在信号注册前 import，这样 finance 的
        # register_module() 调用才能被 post_migrate 捕捉到
        from django.db.models.signals import post_migrate
        post_migrate.connect(_sync_modules_on_migrate, sender=self)

        # 启动后立即尝试同步（若 migrate 已跑过则成功，否则静默跳过）
        try:
            from apps.core.models import _MODULE_REGISTRY
            if _MODULE_REGISTRY:
                from apps.finance import modules as _fm  # noqa: F401
                _sync_modules_on_migrate(sender=self)
        except Exception:
            pass  # 表不存在时跳过，migrate 会触发 post_migrate 再次同步


def _sync_modules_on_migrate(sender, **kwargs):
    """post_migrate 信号的处理器：将已注册的模块写入 DB"""
    from apps.core.models import sync_modules_to_db
    from apps.finance import modules as _fm  # noqa: F401
    sync_modules_to_db()
