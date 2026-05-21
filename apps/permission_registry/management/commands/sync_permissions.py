"""
手动触发权限模块同步。

用法：
    python manage.py sync_permissions
    python manage.py sync_permissions --force   # 强制打印详情
"""

from django.core.management.base import BaseCommand
from django.apps import apps


class Command(BaseCommand):
    help = '触发所有模块的权限同步，将 @register_module 声明同步到数据库'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='显示详细同步日志'
        )

    def handle(self, *args, **options):
        verbose = options.get('force', False)

        if verbose:
            self.stdout.write('开始同步权限模块...')

        # 触发 AppConfig.ready() 逻辑
        from apps.permission_registry.registry import sync_all_modules, get_registry
        sync_all_modules()

        registry = get_registry()
        self.stdout.write(
            self.style.SUCCESS(f'同步完成，共注册 {len(registry)} 个模块：')
        )
        for name, info in registry.items():
            perm_count = len(info.get('permissions', []))
            self.stdout.write(f'  ✓ {name} ({info["label"]}) — {perm_count} 个权限档位')

        if verbose:
            # 打印数据库中的实际记录
            from apps.permission_registry.models import Module
            db_modules = Module.objects.filter(is_active=True).count()
            self.stdout.write(f'\n数据库中活跃模块数：{db_modules}')
