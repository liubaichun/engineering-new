"""
种子数据：填充标准会计科目表（Chart of Accounts）
参照小企业会计准则简化版，适用于多公司经营管理台账
"""
from django.core.management.base import BaseCommand
from apps.finance.models import Account


STANDARD_ACCOUNTS = [
    # ─── 资产类（1000系列） ──────────────────────────────────────
    # 一级科目
    {'code': '1001', 'name': '银行存款', 'account_type': 'asset', 'level': 1, 'is_leaf': False, 'sort_order': 100},
    {'code': '1002', 'name': '应收账款', 'account_type': 'asset', 'level': 1, 'is_leaf': False, 'sort_order': 200},
    {'code': '1003', 'name': '其他应收款', 'account_type': 'asset', 'level': 1, 'is_leaf': False, 'sort_order': 300},

    # 二级科目（银行存款）
    {'code': '1001-01', 'name': '银行存款-基本户', 'account_type': 'asset', 'level': 2, 'parent_code': '1001', 'is_leaf': True, 'sort_order': 101},
    {'code': '1001-02', 'name': '银行存款-一般户', 'account_type': 'asset', 'level': 2, 'parent_code': '1001', 'is_leaf': True, 'sort_order': 102},

    # 二级科目（应收账款）- 按客户自动衍生，不预设

    # ─── 负债类（2000系列） ──────────────────────────────────────
    {'code': '2001', 'name': '应付账款', 'account_type': 'liability', 'level': 1, 'is_leaf': False, 'sort_order': 400},
    {'code': '2002', 'name': '应付职工薪酬', 'account_type': 'liability', 'level': 1, 'is_leaf': True, 'sort_order': 500},
    {'code': '2003', 'name': '应交税费', 'account_type': 'liability', 'level': 1, 'is_leaf': True, 'sort_order': 600},
    {'code': '2004', 'name': '其他应付款', 'account_type': 'liability', 'level': 1, 'is_leaf': True, 'sort_order': 700},

    # ─── 所有者权益类（3000系列） ────────────────────────────────
    {'code': '3001', 'name': '实收资本', 'account_type': 'equity', 'level': 1, 'is_leaf': True, 'sort_order': 800},
    {'code': '3002', 'name': '未分配利润', 'account_type': 'equity', 'level': 1, 'is_leaf': True, 'sort_order': 900},

    # ─── 收入类（4000系列） ──────────────────────────────────────
    {'code': '4001', 'name': '主营业务收入', 'account_type': 'income', 'level': 1, 'is_leaf': False, 'sort_order': 1000},
    {'code': '4002', 'name': '其他业务收入', 'account_type': 'income', 'level': 1, 'is_leaf': True, 'sort_order': 1100},
    {'code': '4003', 'name': '营业外收入', 'account_type': 'income', 'level': 1, 'is_leaf': True, 'sort_order': 1200},
    {'code': '4004', 'name': '其他收益', 'account_type': 'income', 'level': 1, 'is_leaf': True, 'sort_order': 1300},
    {'code': '4005', 'name': '投资收益', 'account_type': 'income', 'level': 1, 'is_leaf': True, 'sort_order': 1400},

    # 二级科目（主营业务收入）
    {'code': '4001-01', 'name': '主营业务收入-服务收入', 'account_type': 'income', 'level': 2, 'parent_code': '4001', 'is_leaf': True, 'sort_order': 1001},
    {'code': '4001-02', 'name': '主营业务收入-销售收入', 'account_type': 'income', 'level': 2, 'parent_code': '4001', 'is_leaf': True, 'sort_order': 1002},

    # ─── 费用类（5000系列） ──────────────────────────────────────
    {'code': '5001', 'name': '主营业务成本', 'account_type': 'expense', 'level': 1, 'is_leaf': False, 'sort_order': 2000},
    {'code': '5002', 'name': '管理费用', 'account_type': 'expense', 'level': 1, 'is_leaf': False, 'sort_order': 2100},
    {'code': '5003', 'name': '税金及附加', 'account_type': 'expense', 'level': 1, 'is_leaf': True, 'sort_order': 2200},
    {'code': '5004', 'name': '营业外支出', 'account_type': 'expense', 'level': 1, 'is_leaf': True, 'sort_order': 2250},
    {'code': '5005', 'name': '财务费用', 'account_type': 'expense', 'level': 1, 'is_leaf': True, 'sort_order': 2300},

    # 二级科目（主营业务成本）
    {'code': '5001-01', 'name': '主营业务成本-采购成本', 'account_type': 'expense', 'level': 2, 'parent_code': '5001', 'is_leaf': True, 'sort_order': 2001},

    # 二级科目（管理费用）
    {'code': '5002-01', 'name': '管理费用-工资薪酬', 'account_type': 'expense', 'level': 2, 'parent_code': '5002', 'is_leaf': True, 'sort_order': 2101},
    {'code': '5002-02', 'name': '管理费用-社保费用', 'account_type': 'expense', 'level': 2, 'parent_code': '5002', 'is_leaf': True, 'sort_order': 2102},
    {'code': '5002-03', 'name': '管理费用-办公费用', 'account_type': 'expense', 'level': 2, 'parent_code': '5002', 'is_leaf': True, 'sort_order': 2103},
    {'code': '5002-04', 'name': '管理费用-差旅费用', 'account_type': 'expense', 'level': 2, 'parent_code': '5002', 'is_leaf': True, 'sort_order': 2104},
    {'code': '5002-05', 'name': '管理费用-业务招待费', 'account_type': 'expense', 'level': 2, 'parent_code': '5002', 'is_leaf': True, 'sort_order': 2105},
    {'code': '5002-06', 'name': '管理费用-通讯费用', 'account_type': 'expense', 'level': 2, 'parent_code': '5002', 'is_leaf': True, 'sort_order': 2106},
    {'code': '5002-07', 'name': '管理费用-市场营销', 'account_type': 'expense', 'level': 2, 'parent_code': '5002', 'is_leaf': True, 'sort_order': 2107},
    {'code': '5002-08', 'name': '管理费用-研发费用', 'account_type': 'expense', 'level': 2, 'parent_code': '5002', 'is_leaf': True, 'sort_order': 2108},
    {'code': '5002-09', 'name': '管理费用-税费', 'account_type': 'expense', 'level': 2, 'parent_code': '5002', 'is_leaf': True, 'sort_order': 2109},
    {'code': '5002-10', 'name': '管理费用-其他', 'account_type': 'expense', 'level': 2, 'parent_code': '5002', 'is_leaf': True, 'sort_order': 2199},
]


class Command(BaseCommand):
    help = '填充标准会计科目表'

    def handle(self, *args, **options):
        # 1. 创建一级科目（无parent）
        created_count = 0
        parent_map = {}

        for acct_data in STANDARD_ACCOUNTS:
            if acct_data['level'] == 1:
                parent_code = None
            else:
                parent_code = acct_data.pop('parent_code')

            obj, created = Account.objects.get_or_create(
                code=acct_data['code'],
                company=None,  # 全局科目
                defaults={
                    'name': acct_data['name'],
                    'account_type': acct_data['account_type'],
                    'level': acct_data['level'],
                    'is_leaf': acct_data['is_leaf'],
                    'sort_order': acct_data['sort_order'],
                    'is_active': True,
                }
            )
            if created:
                created_count += 1
                self.stdout.write(f'  + {acct_data["code"]} {acct_data["name"]}')
            parent_map[acct_data['code']] = obj

        # 2. 设置二级科目的parent
        for acct_data in STANDARD_ACCOUNTS:
            if acct_data.get('parent_code'):
                child = parent_map.get(acct_data['code'])
                parent = parent_map.get(acct_data['parent_code'])
                if child and parent and child.parent_id != parent.id:
                    child.parent = parent
                    child.save(update_fields=['parent'])

        self.stdout.write(self.style.SUCCESS(
            f'\n✅ 科目表初始化完成：共 {Account.objects.count()} 个科目，新增 {created_count} 个'
        ))
