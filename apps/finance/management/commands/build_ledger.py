"""
从已有的 Income/Expense 记录反推建立关联方往来台账（RelatedPartyLedger）。

核心逻辑：
  - 只处理 expense 表中摘要明确含"往来/借款/备用金/设备定金"的支出 → 借出
  - 只处理 income 表中 income_category=internal_transfer 的收入 → 还款
  - 自动按时间线匹配借出→还款，计算余额
"""

from collections import defaultdict
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.finance.models import Income, Expense, RelatedPartyLedger


# 支出中认定为"借出"的关键词
LEND_EXPENSE_KEYWORDS = ['往来', '借款', '备用金', '设备定金']

# 支出中认定为"非借款"的关键词（即使对手方是关联方）
EXCLUDE_EXPENSE_KEYWORDS = ['报销', '工资', '年终奖', '差旅', '费用']

# 收入描述中认定为"还款"的关键词（匹配 internal_transfer 记录）
# 备注：internal_transfer 本身已标记不走收入，这里只是细分到台账
REPAY_KEYWORDS = ['还款', '退备用金', '退款', '退订金', '转账汇款']

# 已知的个人关联方
PERSONAL_PARTIES = ['刘柏春', '马利英', '郑晚霞', '沈容', '谢超', '邓阳']


def get_counterparty_type(name):
    for p in PERSONAL_PARTIES:
        if p in name:
            return 'personal'
    return 'company'


def short_name(name):
    """取公司简称（去掉"深圳市""有限公司"等）"""
    for s in ['深圳市', '有限公司', '科技发展', '信息技术', '科技有限公司']:
        name = name.replace(s, '')
    return name


def build_ledger():
    RelatedPartyLedger.objects.all().delete()

    entries = []
    group_counter = 0

    # ─── 第一步：扫描 Expense → 借出记录 ───
    # 规则：摘要中明确含"往来/借款/备用金/设备定金"，且不含"报销/工资/差旅"
    lend_expenses = []
    for exp in Expense.objects.select_related('company').order_by('date', 'id'):
        supplier = (exp.supplier or '').strip()
        summary = (exp.summary or exp.description or '').strip()

        # 必须有摘要/描述
        if not summary and not supplier:
            continue

        # 必须含借出关键词
        if not any(kw in summary for kw in LEND_EXPENSE_KEYWORDS):
            continue

        # 不得含排除关键词
        if any(kw in summary for kw in EXCLUDE_EXPENSE_KEYWORDS):
            continue

        # 必须有对手方
        counterparty = supplier if supplier else summary
        if not counterparty:
            continue

        # 如果 supplier 为空且 summary 只是关键词（不是公司/人名），跳过
        # 这种记录无法确定实际对手方
        if not supplier:
            pure_keywords = ['往来', '借款', '备用金', '设备定金', '还款', '退款', '转账']
            if summary.strip() in pure_keywords or len(summary.strip()) <= 4:
                continue

        group_counter += 1
        lend_expenses.append(
            {
                'exp': exp,
                'counterparty': counterparty,
                'ctype': get_counterparty_type(counterparty),
                'amount': float(exp.amount),
                'date': exp.date,
                'desc': summary,
                'group_id': f'G{group_counter:04d}',
            }
        )

    # 先创建借出记录
    for le in lend_expenses:
        entries.append(
            RelatedPartyLedger(
                company=le['exp'].company,
                counterparty=le['counterparty'],
                counterparty_type=le['ctype'],
                direction='lend_out',
                amount=le['amount'],
                balance=le['amount'],
                transaction_date=le['date'],
                description=le['desc'],
                source_type='expense',
                source_id=le['exp'].id,
                status='active',
                group_id=le['group_id'],
            )
        )

    # ─── 第二步：扫描 Income → 还款 + 投资款 ───
    # 规则：income_category = internal_transfer 或 equity
    income_items = []
    for inc in (
        Income.objects.filter(income_category__in=['internal_transfer', 'equity'])
        .select_related('company')
        .order_by('date', 'id')
    ):
        customer = (inc.customer or '').strip()
        desc = (inc.description or inc.summary or '').strip()
        counterparty = customer or desc

        if inc.income_category == 'equity':
            direction = 'lend_in'
        else:
            direction = 'repay'

        income_items.append(
            {
                'inc': inc,
                'counterparty': counterparty,
                'ctype': get_counterparty_type(counterparty),
                'direction': direction,
                'amount': float(inc.amount),
                'date': inc.date,
                'desc': desc,
            }
        )

    # ─── 第三步：匹配还款到借出记录 ───
    # 按 (company_id, counterparty) 分组
    lend_map = defaultdict(list)
    for idx, le in enumerate(lend_expenses):
        key = (le['exp'].company_id, le['counterparty'])
        lend_map[key].append(idx)

    lend_balances = [float(le['amount']) for le in lend_expenses]
    lend_status = ['active'] * len(lend_expenses)
    lend_group = [le['group_id'] for le in lend_expenses]

    for item in income_items:
        key = (item['inc'].company_id, item['counterparty'])

        # 投资款不匹配借出，直接创建
        if item['direction'] == 'lend_in':
            entries.append(
                RelatedPartyLedger(
                    company=item['inc'].company,
                    counterparty=item['counterparty'],
                    counterparty_type=item['ctype'],
                    direction='lend_in',
                    amount=item['inc'].amount,
                    balance=item['amount'],
                    transaction_date=item['date'],
                    description='投资款',
                    source_type='income',
                    source_id=item['inc'].id,
                    status='active',
                )
            )
            continue

        # 还款：尝试匹配借出记录
        matched_idx = None
        for idx in lend_map.get(key, []):
            if lend_status[idx] == 'settled':
                continue
            if lend_expenses[idx]['date'] <= item['date'] and lend_balances[idx] > 0:
                matched_idx = idx
                break

        if matched_idx is not None:
            repay_amount = item['amount']
            old_balance = lend_balances[matched_idx]
            new_balance = max(0, old_balance - repay_amount)
            lend_balances[matched_idx] = new_balance
            if new_balance <= 0:
                lend_status[matched_idx] = 'settled'

            entries.append(
                RelatedPartyLedger(
                    company=item['inc'].company,
                    counterparty=item['counterparty'],
                    counterparty_type=item['ctype'],
                    direction='repay',
                    amount=item['inc'].amount,
                    balance=new_balance,
                    transaction_date=item['date'],
                    description=item['desc'],
                    source_type='income',
                    source_id=item['inc'].id,
                    status='settled',
                    group_id=lend_group[matched_idx],
                )
            )
        else:
            # 没有匹配到借出记录
            entries.append(
                RelatedPartyLedger(
                    company=item['inc'].company,
                    counterparty=item['counterparty'],
                    counterparty_type=item['ctype'],
                    direction='repay',
                    amount=item['inc'].amount,
                    balance=0,
                    transaction_date=item['date'],
                    description=item['desc'],
                    source_type='income',
                    source_id=item['inc'].id,
                    status='settled',
                )
            )

    # 更新借出记录的最终余额和状态
    for idx, le in enumerate(lend_expenses):
        # 找到刚创建的对应借出记录
        for e in entries:
            if e.source_type == 'expense' and e.source_id == le['exp'].id:
                e.balance = lend_balances[idx]
                if lend_status[idx] == 'settled':
                    e.status = 'settled'
                break

    # ─── 批量写入 ───
    with transaction.atomic():
        RelatedPartyLedger.objects.bulk_create(entries)

    return len(entries)


class Command(BaseCommand):
    help = '从现有收支记录反推建立关联方往来台账'

    def handle(self, *args, **options):
        count = build_ledger()
        self.stdout.write(f'关联方往来台账建立完成，共 {count} 条记录')

        from django.db.models import Sum, Count

        # 按公司+方向汇总
        summary = (
            RelatedPartyLedger.objects.values('company__name', 'direction')
            .annotate(cnt=Count('id'), total=Sum('amount'))
            .order_by('company__name', 'direction')
        )

        self.stdout.write('\n=== 往来台账汇总 ===')
        for row in summary:
            self.stdout.write(
                f'  {row["company__name"]:15s} | {row["direction"]:10s} | {row["cnt"]:>3}笔 | ¥{float(row["total"]):>10.2f}'
            )

        # 按对手方统计未结清余额
        active = (
            RelatedPartyLedger.objects.filter(status='active')
            .values('company__name', 'counterparty')
            .annotate(total=Sum('balance'))
            .filter(total__gt=0)
            .order_by('-total')
        )

        self.stdout.write('\n=== 未结清往来（谁还欠谁钱）===')
        for row in active:
            self.stdout.write(
                f'  {row["company__name"]:15s} ← {row["counterparty"]:25s} 还欠 ¥{float(row["total"]):>10.2f}'
            )

        # 已结清
        settled = (
            RelatedPartyLedger.objects.filter(status='settled')
            .values('company__name', 'counterparty')
            .annotate(total=Sum('amount'))
            .filter(total__gt=0)
            .order_by('-total')
        )

        self.stdout.write('\n=== 已结清往来 ===')
        for row in settled[:20]:
            self.stdout.write(
                f'  {row["company__name"]:15s} ↔ {row["counterparty"]:25s} 共 ¥{float(row["total"]):>10.2f}'
            )
