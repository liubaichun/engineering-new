from django.apps import AppConfig, apps
from django.db.models.signals import post_migrate


class PermissionRegistryConfig(AppConfig):
    name = 'apps.permission_registry'
    verbose_name = '权限注册中心'

    def ready(self):
        """
        注册 post_migrate 信号，在每次 migrate 之后同步模块到数据库。

        post_migrate 在表创建/迁移完成后触发，此时表已存在，可安全写入。
        注意：post_migrate 在 migrate 命令后立即执行，
              而非在每个 HTTP 请求的 Django 启动时执行。
        """
        post_migrate.connect(_sync_on_migrate, sender=self)


def _sync_on_migrate(app_config, **kwargs):
    """
    post_migrate 信号处理器。

    仅当 permission_registry app 完成迁移时触发，
    此时 permission_registry_module 表已存在，可安全写入。
    """
    if app_config.name != 'apps.permission_registry':
        return
    from apps.permission_registry.registry import sync_all_modules
    sync_all_modules()
