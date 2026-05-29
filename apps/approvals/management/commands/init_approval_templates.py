"""
初始化多级审批模板（按金额自动路由）

支出审批模板（5级）：
  ≤5,000    → 主管一级审批
  ≤20,000  → 主管 → 财务
  ≤50,000  → 主管 → 财务 → 总监
  ≤100,000 → 主管 → 财务 → 总监 → 总经理
  >100,000 → 主管 → 财务 → 总监 → 总经理 → 董事会

收入确认模板（3级）：
  ≤5,000    → 无需审批（直接确认）
  ≤50,000  → 主管 → 财务
  >50,000  → 主管 → 财务 → 总监

工资审批模板（2级）：
  ≤10,000  → 主管
  >10,000  → 主管 → 财务

用法：
    python manage.py init_approval_templates [--force]
"""

from django.core.management.base import BaseCommand
from apps.approvals.models import ApprovalTemplate
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = '初始化多级审批模板（按金额自动路由）'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='强制覆盖现有模板')

    def handle(self, *args, **options):
        force = options['force']
        admin_user = User.objects.filter(is_superuser=True).first()

        # ── 支出审批模板（5级金额路由）─────────────────────────────────────────
        expense_templates = [
            {
                'code': 'EXP-L1-001',
                'name': '支出审批-L1级（≤5000元）',
                'flow_type': 'expense',
                'conditions': {'min_amount': 0, 'max_amount': 5000},
                'nodes': [
                    {
                        'node_order': 1,
                        'approver_type': 'admin',
                        'approver_id': None,
                        'timeout_hours': 24,
                        'node_type': 'single',
                        'description': '主管审批',
                    },
                ],
                'description': '小额支出，主管一级审批即可',
            },
            {
                'code': 'EXP-L2-001',
                'name': '支出审批-L2级（5001-20000元）',
                'flow_type': 'expense',
                'conditions': {'min_amount': 5000, 'max_amount': 20000},
                'nodes': [
                    {
                        'node_order': 1,
                        'approver_type': 'admin',
                        'approver_id': None,
                        'timeout_hours': 24,
                        'node_type': 'single',
                        'description': '主管审批',
                    },
                    {
                        'node_order': 2,
                        'approver_type': 'specific_user',
                        'approver_id': admin_user.id if admin_user else None,
                        'timeout_hours': 48,
                        'node_type': 'single',
                        'description': '财务复核',
                    },
                ],
                'description': '中等金额，主管+财务两级审批',
            },
            {
                'code': 'EXP-L3-001',
                'name': '支出审批-L3级（20001-50000元）',
                'flow_type': 'expense',
                'conditions': {'min_amount': 20000, 'max_amount': 50000},
                'nodes': [
                    {
                        'node_order': 1,
                        'approver_type': 'admin',
                        'approver_id': None,
                        'timeout_hours': 24,
                        'node_type': 'single',
                        'description': '主管审批',
                    },
                    {
                        'node_order': 2,
                        'approver_type': 'specific_user',
                        'approver_id': admin_user.id if admin_user else None,
                        'timeout_hours': 48,
                        'node_type': 'single',
                        'description': '财务复核',
                    },
                    {
                        'node_order': 3,
                        'approver_type': 'department_head',
                        'approver_id': None,
                        'timeout_hours': 72,
                        'node_type': 'single',
                        'description': '总监审批',
                    },
                ],
                'description': '较大金额，主管+财务+总监三级审批',
            },
            {
                'code': 'EXP-L4-001',
                'name': '支出审批-L4级（50001-100000元）',
                'flow_type': 'expense',
                'conditions': {'min_amount': 50000, 'max_amount': 100000},
                'nodes': [
                    {
                        'node_order': 1,
                        'approver_type': 'admin',
                        'approver_id': None,
                        'timeout_hours': 24,
                        'node_type': 'single',
                        'description': '主管审批',
                    },
                    {
                        'node_order': 2,
                        'approver_type': 'specific_user',
                        'approver_id': admin_user.id if admin_user else None,
                        'timeout_hours': 48,
                        'node_type': 'single',
                        'description': '财务复核',
                    },
                    {
                        'node_order': 3,
                        'approver_type': 'department_head',
                        'approver_id': None,
                        'timeout_hours': 72,
                        'node_type': 'single',
                        'description': '总监审批',
                    },
                    {
                        'node_order': 4,
                        'approver_type': 'manager',
                        'approver_id': None,
                        'timeout_hours': 96,
                        'node_type': 'single',
                        'description': '总经理审批',
                    },
                ],
                'description': '大额支出，四级审批',
            },
            {
                'code': 'EXP-L5-001',
                'name': '支出审批-L5级（>100000元）',
                'flow_type': 'expense',
                'conditions': {'min_amount': 100000, 'max_amount': None},
                'nodes': [
                    {
                        'node_order': 1,
                        'approver_type': 'admin',
                        'approver_id': None,
                        'timeout_hours': 24,
                        'node_type': 'single',
                        'description': '主管审批',
                    },
                    {
                        'node_order': 2,
                        'approver_type': 'specific_user',
                        'approver_id': admin_user.id if admin_user else None,
                        'timeout_hours': 48,
                        'node_type': 'single',
                        'description': '财务复核',
                    },
                    {
                        'node_order': 3,
                        'approver_type': 'department_head',
                        'approver_id': None,
                        'timeout_hours': 72,
                        'node_type': 'single',
                        'description': '总监审批',
                    },
                    {
                        'node_order': 4,
                        'approver_type': 'manager',
                        'approver_id': None,
                        'timeout_hours': 96,
                        'node_type': 'single',
                        'description': '总经理审批',
                    },
                    {
                        'node_order': 5,
                        'approver_type': 'board',
                        'approver_id': None,
                        'timeout_hours': 168,
                        'node_type': 'single',
                        'description': '董事会审批',
                    },
                ],
                'description': '超大额支出，五级审批（董事会）',
            },
        ]

        # ── 收入确认模板（3级）─────────────────────────────────────────────────
        income_templates = [
            {
                'code': 'INC-L1-001',
                'name': '收入确认-L1级（≤5000元）',
                'flow_type': 'income',
                'conditions': {'min_amount': 0, 'max_amount': 5000},
                'nodes': [
                    {
                        'node_order': 1,
                        'approver_type': 'admin',
                        'approver_id': None,
                        'timeout_hours': 24,
                        'node_type': 'single',
                        'description': '主管审批',
                    },
                ],
                'description': '小额收入，直接确认',
            },
            {
                'code': 'INC-L2-001',
                'name': '收入确认-L2级（5001-50000元）',
                'flow_type': 'income',
                'conditions': {'min_amount': 5000, 'max_amount': 50000},
                'nodes': [
                    {
                        'node_order': 1,
                        'approver_type': 'admin',
                        'approver_id': None,
                        'timeout_hours': 24,
                        'node_type': 'single',
                        'description': '主管审批',
                    },
                    {
                        'node_order': 2,
                        'approver_type': 'specific_user',
                        'approver_id': admin_user.id if admin_user else None,
                        'timeout_hours': 48,
                        'node_type': 'single',
                        'description': '财务复核',
                    },
                ],
                'description': '中等金额，主管+财务两级审批',
            },
            {
                'code': 'INC-L3-001',
                'name': '收入确认-L3级（>50000元）',
                'flow_type': 'income',
                'conditions': {'min_amount': 50000, 'max_amount': None},
                'nodes': [
                    {
                        'node_order': 1,
                        'approver_type': 'admin',
                        'approver_id': None,
                        'timeout_hours': 24,
                        'node_type': 'single',
                        'description': '主管审批',
                    },
                    {
                        'node_order': 2,
                        'approver_type': 'specific_user',
                        'approver_id': admin_user.id if admin_user else None,
                        'timeout_hours': 48,
                        'node_type': 'single',
                        'description': '财务复核',
                    },
                    {
                        'node_order': 3,
                        'approver_type': 'department_head',
                        'approver_id': None,
                        'timeout_hours': 72,
                        'node_type': 'single',
                        'description': '总监审批',
                    },
                ],
                'description': '大额收入，三级审批',
            },
        ]

        # ── 工资审批模板（2级）─────────────────────────────────────────────────
        wage_templates = [
            {
                'code': 'WAGE-L1-001',
                'name': '工资审批-L1级（≤10000元）',
                'flow_type': 'wage',
                'conditions': {'min_amount': 0, 'max_amount': 10000},
                'nodes': [
                    {
                        'node_order': 1,
                        'approver_type': 'admin',
                        'approver_id': None,
                        'timeout_hours': 24,
                        'node_type': 'single',
                        'description': '主管审批',
                    },
                ],
                'description': '普通工资，主管审批',
            },
            {
                'code': 'WAGE-L2-001',
                'name': '工资审批-L2级（>10000元）',
                'flow_type': 'wage',
                'conditions': {'min_amount': 10000, 'max_amount': None},
                'nodes': [
                    {
                        'node_order': 1,
                        'approver_type': 'admin',
                        'approver_id': None,
                        'timeout_hours': 24,
                        'node_type': 'single',
                        'description': '主管审批',
                    },
                    {
                        'node_order': 2,
                        'approver_type': 'specific_user',
                        'approver_id': admin_user.id if admin_user else None,
                        'timeout_hours': 48,
                        'node_type': 'single',
                        'description': '财务复核',
                    },
                ],
                'description': '高额工资，主管+财务审批',
            },
        ]

        all_templates = expense_templates + income_templates + wage_templates

        created = 0
        updated = 0
        for tpl in all_templates:
            obj, is_new = ApprovalTemplate.objects.update_or_create(
                code=tpl['code'],
                defaults={
                    'name': tpl['name'],
                    'flow_type': tpl['flow_type'],
                    'conditions': tpl['conditions'],
                    'nodes': tpl['nodes'],
                    'description': tpl['description'],
                    'is_active': True,
                    'created_by': admin_user,
                },
            )
            if is_new:
                created += 1
                self.stdout.write(self.style.SUCCESS(f'[新建] {obj.code} - {obj.name}'))
            else:
                updated += 1
                self.stdout.write(f'[更新] {obj.code} - {obj.name}')

        self.stdout.write(
            self.style.SUCCESS(f'\n完成！新建 {created} 个模板，更新 {updated} 个模板，共 {len(all_templates)} 个')
        )
