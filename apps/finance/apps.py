from django.apps import AppConfig


class FinanceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.finance'
    verbose_name = '财务管理'

    def ready(self):
        """
        Django 启动时注册模块到内存注册表，并同步到数据库。

        1. import modules.py → 触发 @register_module → 填充 _REGISTRY 内存表
        2. 调用 sync_all_modules() → 将模块信息写入 permission_registry_module 表

        这样重启服务后 DB 里就有数据了，ModulePermission 权限类才能正常工作。
        """
        # 填充内存注册表
        from apps.finance import modules as _fm
        # 同步到数据库
        from apps.permission_registry.registry import sync_all_modules
        sync_all_modules()
