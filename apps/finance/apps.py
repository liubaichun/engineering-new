from django.apps import AppConfig


class FinanceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.finance'
    verbose_name = '财务管理'

    def ready(self):
        # 触发 modules.py 加载（填充装饰器注册表，供 UI 渲染使用）
        from apps.finance import modules as _fm  # noqa: F401
