"""批量填充收入记录的 income_category 字段。
分类优先级：
  1. 投资款 → 实收资本（equity，不入损益表）
  2. 退款/退定金 → 内部往来（internal_transfer，冲预付/往来）
  3. 描述含"往来/借款/还款/备用金" → 内部往来
  4. 内部公司转账 → 内部往来
  5. 个人往来（刘柏春/马利英/郑晚霞/沈容/谢超/邓阳）→ 内部往来
  6. 生育津贴 → 内部往来（代收代付，不入损益表）
  7. 稳岗补贴/政府补助 → 其他收益（other_income）
  8. 银行利息、退税 → 营业外收入
  9. 其余 → 主营业务收入
"""
from django.core.management.base import BaseCommand
from apps.finance.models import Income, Company


def get_internal_names():
    return set(Company.objects.values_list('name', flat=True))


# 投资款 → 实收资本
INVESTMENT_DESC_PATTERNS = ['投资款']

# 按描述判断内部往来（优先级最高，不看客户名）
INTERNAL_TRANSFER_DESC_PATTERNS = [
    '往来', '借款', '还款', '备用金', '退款', '退订金', '退定金',
]

# 内部往来 - 客户名为个人姓名
INTERNAL_TRANSFER_CUSTOMER_PATTERNS = [
    '刘柏春', '马利英', '郑晚霞', '沈容', '谢超', '邓阳',
]

# 生育津贴 → 内部往来（代收代付，不入损益表）
MATERNITY_DESC_PATTERNS = ['生育津贴']

# 稳岗补贴/政府补助 → 其他收益
SUBSIDY_DESC_PATTERNS = ['稳岗', '稳岗补贴']

# 营业外收入 - 客户名
NON_OPERATING_CUSTOMER_PATTERNS = [
    '应付利息', '待报解预算收入', '利息',
]

# 营业外收入 - 描述
NON_OPERATING_DESC_PATTERNS = [
    '利息', '退税', '退库', '电子退库',
]


class Command(BaseCommand):
    help = '批量填充收入科目'

    def handle(self, *args, **options):
        internal_names = get_internal_names()
        updated = {'main_business': 0, 'non_operating': 0, 'other_income': 0,
                   'internal_transfer': 0, 'equity': 0}

        for inc in Income.objects.iterator():
            customer = (inc.customer or '').strip()
            desc = (inc.description or '').strip()

            # 1. 投资款 → 实收资本（最高优先级，不入损益表）
            if any(p in desc for p in INVESTMENT_DESC_PATTERNS):
                inc.income_category = 'equity'
                updated['equity'] += 1

            # 2. 退款/退订金 → 内部往来（冲原预付/往来款）
            elif any(p in desc for p in ['退款', '退订金', '退定金']):
                inc.income_category = 'internal_transfer'
                updated['internal_transfer'] += 1

            # 3. 描述含"往来/借款/还款/备用金" → 内部往来
            elif any(p in desc for p in INTERNAL_TRANSFER_DESC_PATTERNS):
                inc.income_category = 'internal_transfer'
                updated['internal_transfer'] += 1

            # 4. 内部公司转账 → 内部往来
            elif customer in internal_names:
                inc.income_category = 'internal_transfer'
                updated['internal_transfer'] += 1

            # 5. 个人往来 → 内部往来
            elif any(p in customer for p in INTERNAL_TRANSFER_CUSTOMER_PATTERNS):
                inc.income_category = 'internal_transfer'
                updated['internal_transfer'] += 1

            # 6. 生育津贴 → 内部往来（代收代付，不入损益表）
            elif any(p in desc for p in MATERNITY_DESC_PATTERNS):
                inc.income_category = 'internal_transfer'
                updated['internal_transfer'] += 1

            # 7. 稳岗补贴/政府补助 → 其他收益
            elif any(p in desc for p in SUBSIDY_DESC_PATTERNS):
                inc.income_category = 'other_income'
                updated['other_income'] += 1

            # 8. 银行利息、退税 → 营业外收入
            elif any(p in customer for p in NON_OPERATING_CUSTOMER_PATTERNS):
                inc.income_category = 'non_operating'
                updated['non_operating'] += 1

            elif any(p in desc for p in NON_OPERATING_DESC_PATTERNS):
                inc.income_category = 'non_operating'
                updated['non_operating'] += 1

            # 9. 其余 → 主营业务收入
            else:
                inc.income_category = 'main_business'
                updated['main_business'] += 1

            inc.save(update_fields=['income_category'])

        self.stdout.write(f'分类完成：')
        self.stdout.write(f'  主营业务收入: {updated["main_business"]}条')
        self.stdout.write(f'  营业外收入:   {updated["non_operating"]}条')
        self.stdout.write(f'  其他收益:     {updated["other_income"]}条')
        self.stdout.write(f'  内部往来:     {updated["internal_transfer"]}条（不计入收入）')
        self.stdout.write(f'  实收资本:     {updated["equity"]}条（权益类，不计入收入）')
        self.stdout.write(f'  合计: {sum(updated.values())}条')
