from django.apps import AppConfig


class FinanceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.finance'
    verbose_name = '财务管理'

    def ready(self):
        """
        Django 启动时注册模块到内存注册表。

        注意：这里只填充 _REGISTRY 内存表，不写数据库。
        数据库同步由 post_migrate 信号处理（在 migrate 之后执行）。
        """
        # import modules.py → 触发 @register_module → 填充 _REGISTRY 内存表
        from apps.finance import modules as _fm
