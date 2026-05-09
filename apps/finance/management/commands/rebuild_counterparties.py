"""
反向补填 Income.customer / Expense.supplier 字段。

BankStatement 有 counterparty_name，Income/Expense 的对应字段却为空，
本命令通过 BankStatement 关联反向补填。

用法：
    python manage.py backfill_counterparty_fields
    python manage.py backfill_counterparty_fields --dry-run
    python manage.py backfill_counterparty_fields --company=3
"""
import re

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.crm.models import Client, Supplier
from apps.finance.models import Company, Expense, Income
from apps.finance.models_bank import BankStatement


def is_personal_name(name: str) -> bool:
    if not name:
        return False
    if not re.fullmatch(r'[\u4e00-\u9fff]{2,6}', name):
        return False
    if re.search(r'[a-zA-Z0-9]', name):
        return False
    for suf in ('公司', '有限', '集团', '企业', '科技', '贸易', '实业'):
        if suf in name:
            return False
    return True


def is_excluded(name: str) -> bool:
    """判断对手方名称是否应排除不建档（仅用于档案创建）。"""
    if not name or not name.strip():
        return True
    if name in ('未知对手方',):
        return True
    for p in (
        '个人', '利息', '结算', '转账', '充值', '提现', '退款',
        '备用金', '内部户', '过渡户', '暂挂户', '备付金',
        '税款', '社保', '公积金', '代发', '代扣',
        '暂收款', '对公中间业务收入', '中间业务收入',
        '应付利息', '单位活期存款利息', '自动计提',
    ):
        if p in name:
            return True
    if is_personal_name(name):
        return True
    return False


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--company', type=int, default=None)
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        target_id = options.get('company')

        companies = [Company.objects.get(id=target_id)] if target_id \
                    else Company.objects.all()

        total_income = total_expense = 0

        for co in companies:
            self.stdout.write(f'\n处理公司: {co.id} {co.name}')

            # ── 反填 Income.customer ─────────────────────────────────────
            # 找 customer 为空/未知、但 BankStatement 有真实对手方 的记录
            inc_qs = Income.objects.filter(
                company=co
            ).filter(
                # 以下两个条件满足任一即需要处理
                customer=''
            )
            inc_filled = 0
            for inc in inc_qs:
                bs = BankStatement.objects.filter(
                    company=co, matched_income=inc
                ).exclude(
                    counterparty_name__isnull=True
                ).exclude(
                    counterparty_name=''
                ).first()
                if not bs:
                    continue
                cp = bs.counterparty_name.strip()
                if not cp or cp == '未知对手方':
                    continue
                # 排除词命中的不填入（个人/银行账户，保持空）
                if is_excluded(cp):
                    continue
                if dry_run:
                    self.stdout.write(f'  [DRY] Income {inc.id}: 空 → {cp}')
                else:
                    inc.customer = cp
                    inc.save(update_fields=['customer'])
                inc_filled += 1

            self.stdout.write(f'  Income 反填: {inc_filled} 条')
            total_income += inc_filled

            # ── 反填 Expense.supplier ───────────────────────────────────
            exp_qs = Expense.objects.filter(
                company=co, supplier=''
            )
            exp_filled = 0
            for exp in exp_qs:
                bs = BankStatement.objects.filter(
                    company=co, matched_expense=exp
                ).exclude(
                    counterparty_name__isnull=True
                ).exclude(
                    counterparty_name=''
                ).first()
                if not bs:
                    continue
                cp = bs.counterparty_name.strip()
                if not cp or cp == '未知对手方':
                    continue
                if is_excluded(cp):
                    continue
                if dry_run:
                    self.stdout.write(f'  [DRY] Expense {exp.id}: 空 → {cp}')
                else:
                    exp.supplier = cp
                    exp.save(update_fields=['supplier'])
                exp_filled += 1

            self.stdout.write(f'  Expense 反填: {exp_filled} 条')
            total_expense += exp_filled

        self.stdout.write(f'\n总计: Income {total_income} 条, Expense {total_expense} 条')
        if dry_run:
            self.stdout.write(self.style.WARNING('  [DRY RUN]'))
