"""
修复 ModuleAction.label 英文混入问题，并按菜单分组排权重排模块顺序。
"""
from django.core.management.base import BaseCommand
from django.db import connection
from apps.core.models import ModuleAction, Module


class Command(BaseCommand):
    def handle(self, *args, **options):
        # ── Step 1: Fix ModuleAction labels (English → Chinese) ──────────────────
        fixes = [
            # purchasing
            ('request', 'create', '新建'),
            ('request', 'read',   '查看'),
            ('request', 'update', '编辑'),
            ('request', 'approve','审批'),
            ('request', 'reject', '驳回'),
            ('order',   'create', '新建'),
            ('order',   'read',   '查看'),
            ('order',   'update', '编辑'),
            ('order',   'approve','审批'),
            ('order',   'reject', '驳回'),
            ('receive', 'create', '新建'),
            ('receive', 'read',   '查看'),
            ('receive', 'update', '编辑'),
            # equipment
            ('equipment','repair','维修'),
        ]

        for mod_name, action, new_label in fixes:
            updated = ModuleAction.objects.filter(
                module__name=mod_name, name=action
            ).update(label=new_label)
            self.stdout.write(f'  {"✓" if updated else "✗"} {mod_name}.{action} → {new_label}')

        # ── Step 2: Fix Module.sort_order (menu-aligned) ────────────────────────
        sort_fixes = {
            # 项目 (sort 1-3)
            'project': 1, 'stage': 2, 'task': 3,
            # 审批 (4)
            'template': 4,
            # 财务 (11-19)
            'income': 11, 'expense': 12, 'invoice': 13, 'wage': 14,
            'report': 15, 'bank': 16, 'employee': 17, 'company': 18, 'approval': 19,
            # CRM (21-30)
            'customer': 21, 'supplier': 22, 'contract': 23, 'contact': 24,
            'opportunity': 25, 'follow_up_record': 26, 'payment_plan': 27,
            'client_source': 28, 'contract_change_log': 29, 'followup': 30,
            # 采购 (31-33)
            'request': 31, 'order': 32, 'receive': 33,
            # 运营/物料/维修 (41-44)
            'equipment': 41, 'stock': 42, 'usage': 43, 'repair_request': 44,
            # 系统 (51-53)
            'user': 51, 'role': 52, 'setting': 53,
            # 通知 (61)
            'channel': 61,
        }

        for mod_name, new_sort in sort_fixes.items():
            updated = Module.objects.filter(name=mod_name).update(sort_order=new_sort)
            self.stdout.write(f'  {"✓" if updated else "✗"} {mod_name} sort → {new_sort}')

        self.stdout.write(self.style.SUCCESS('\n✓ 数据修复完成'))