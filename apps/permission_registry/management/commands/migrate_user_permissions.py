"""
用户权限迁移命令。

将旧 UserCompanyRole（admin/staff 两档）迁移到新的 UserCompanyPermission 五档表。

迁移规则：
  UserCompanyRole.role='admin'
    → can_view=True, can_create=True, can_edit=True, can_delete=True, can_approve=True
    → is_primary=True（该用户在该公司列表的第一个公司）

  UserCompanyRole.role='staff'
    → can_view=True, can_create=True
    → is_primary=True（该用户在该公司列表的第一个公司）

用法：
    python manage.py migrate_user_permissions --dry-run  # 先预览
    python manage.py migrate_user_permissions           # 正式执行
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.apps import apps


class Command(BaseCommand):
    help = '将 UserCompanyRole 数据迁移到 UserCompanyPermission 五档权限表'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='仅预览迁移结果，不写入数据库'
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)

        UserCompanyRole = apps.get_model('core', 'UserCompanyRole')
        UserCompanyPermission = apps.get_model('permission_registry', 'UserCompanyPermission')
        Module = apps.get_model('permission_registry', 'Module')
        User = apps.get_model('core', 'User')
        Company = apps.get_model('finance', 'Company')

        ucr_qs = UserCompanyRole.objects.select_related('user', 'company').order_by('user_id', 'company_id')

        if not ucr_qs.exists():
            self.stdout.write(self.style.WARNING('UserCompanyRole 表为空，无需迁移'))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING('=== DRY RUN — 仅预览，不写入数据库 ===\n'))

        modules = list(Module.objects.filter(is_active=True))
        if not modules:
            self.stdout.write(self.style.ERROR('permission_registry_module 表为空，请先运行 sync_permissions'))
            return

        total_created = 0

        # 按用户分组，看每用户关联几个公司
        from collections import defaultdict
        user_companies = defaultdict(list)
        for ucr in ucr_qs:
            user_companies[ucr.user_id].append(ucr)

        for user_id, ucr_list in user_companies.items():
            user = ucr_list[0].user
            # 第一个公司为 is_primary=True
            is_first = True

            for ucr in ucr_list:
                for module in modules:
                    defaults = {
                        'is_primary': is_first,
                        'can_view': True,
                        'can_create': True,
                        'can_edit': ucr.role == 'admin',
                        'can_delete': ucr.role == 'admin',
                        'can_approve': ucr.role == 'admin',
                        'created_by_id': 1,  # 超管执行
                    }
                    if dry_run:
                        action = 'CREATE' if not UserCompanyPermission.objects.filter(
                            user=user, company=ucr.company, module=module
                        ).exists() else 'SKIP'
                        self.stdout.write(
                            f'  [{action}] {user.username} @ {ucr.company.name} / {module.name} '
                            f'→ view=1 create=1 edit={int(ucr.role=="admin")} '
                            f'delete={int(ucr.role=="admin")} approve={int(ucr.role=="admin")} '
                            f'primary={is_first}'
                        )
                    else:
                        obj, created = UserCompanyPermission.objects.update_or_create(
                            user=user,
                            company=ucr.company,
                            module=module,
                            defaults=defaults
                        )
                        if created:
                            total_created += 1
                is_first = False

        if dry_run:
            self.stdout.write(f'\n共 {len(ucr_qs)} 条 UserCompanyRole × {len(modules)} 模块')
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n迁移完成：新建 {total_created} 条 UserCompanyPermission 记录，'
                    f'更新 {len(ucr_qs) * len(modules) - total_created} 条。'
                )
            )
            # 验证
            total_ucp = UserCompanyPermission.objects.count()
            self.stdout.write(f'UserCompanyPermission 表现有 {total_ucp} 条记录')
