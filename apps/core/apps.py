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
