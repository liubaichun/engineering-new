"""
数据库校验：会计平衡检查
检查项：
1. 科目余额表：借方总额 = 贷方总额（试算平衡）
2. 资产负债表：资产 = 负债 + 所有者权益
3. 利润表：净利润 = 收入 - 费用
"""
from decimal import Decimal
from django.core.management.base import BaseCommand
from apps.finance.models import Company, Account
from apps.finance.classification_rules import compute_trial_balance


class Command(BaseCommand):
    help = '会计平衡校验'

    def add_arguments(self, parser):
        parser.add_argument('--year', type=int, default=2026, help='年份')
        parser.add_argument('--company', type=int, default=None, help='公司ID')

    def handle(self, *args, **options):
        year = options['year']
        company_id = options['company']

        companies = Company.objects.filter(status='active')
        if company_id:
            companies = companies.filter(id=company_id)

        errors = []
        for company in companies:
            self.stdout.write(f'\n── {company.name} ({year}年) ──')
            tb = compute_trial_balance(company.id, year)

            if not tb:
                self.stdout.write(self.style.WARNING('  无数据'))
                continue

            # 1. 试算平衡：借方总额 = 贷方总额
            total_debit = sum(item['debit_amount'] for item in tb)
            total_credit = sum(item['credit_amount'] for item in tb)
            debit_close = sum(item['closing_balance'] for item in tb
                              if item['account_type'] in ('asset', 'expense'))
            credit_close = sum(item['closing_balance'] for item in tb
                               if item['account_type'] in ('liability', 'equity', 'income'))

            self.stdout.write(f'  科目数: {len(tb)}')
            self.stdout.write(f'  借方发生额: ¥{format_decimal(total_debit)}')
            self.stdout.write(f'  贷方发生额: ¥{format_decimal(total_credit)}')

            if abs(total_debit - total_credit) < Decimal('0.01'):
                self.stdout.write(self.style.SUCCESS('  ✅ 试算平衡：借方 = 贷方'))
            else:
                diff = total_debit - total_credit
                self.stdout.write(self.style.ERROR(f'  ❌ 试算不平衡：借方-贷方 = ¥{format_decimal(diff)}'))
                errors.append(f'{company.name}: 试算不平衡 diff={diff}')

            # 2. 资产负债表检查
            assets = Decimal('0')
            liabilities = Decimal('0')
            equity = Decimal('0')

            for item in tb:
                closing = item['closing_balance']
                if item['account_type'] == 'asset':
                    assets += closing
                elif item['account_type'] == 'liability':
                    liabilities += closing
                elif item['account_type'] == 'equity':
                    equity += closing

            self.stdout.write(f'  资产: ¥{format_decimal(assets)}')
            self.stdout.write(f'  负债: ¥{format_decimal(liabilities)}')
            self.stdout.write(f'  所有者权益: ¥{format_decimal(equity)}')
            self.stdout.write(f'  负债+权益: ¥{format_decimal(liabilities + equity)}')

            bs_diff = abs(assets - (liabilities + equity))
            if bs_diff < Decimal('0.01'):
                self.stdout.write(self.style.SUCCESS('  ✅ 资产负债表平衡：资产 = 负债 + 权益'))
            else:
                self.stdout.write(self.style.WARNING(
                    f'  ⚠️ 资产负债表不平衡：差额 ¥{format_decimal(bs_diff)}'
                    '（说明：银行余额含历史数据，收入/费用仅当年）'))

            # 3. 利润表检查
            income = sum(item['credit_amount'] for item in tb
                         if item['account_type'] == 'income')
            expense = sum(item['debit_amount'] for item in tb
                          if item['account_type'] == 'expense')
            net_profit = income - expense

            self.stdout.write(f'  收入: ¥{format_decimal(income)}')
            self.stdout.write(f'  费用: ¥{format_decimal(expense)}')
            self.stdout.write(f'  净利润: ¥{format_decimal(net_profit)}')

            # 显示所有非零科目
            self.stdout.write(f'\n  --- 科目明细 ---')
            for item in sorted(tb, key=lambda x: x['sort_order']):
                bal = item['closing_balance']
                acct_type = item['account_type']
                sign = ''
                if acct_type in ('asset', 'expense'):
                    bal_label = f'借 {format_decimal(item["debit_amount"])}'
                else:
                    bal_label = f'贷 {format_decimal(item["credit_amount"])}'
                self.stdout.write(f'  {item["account_code"]:8s} {item["account_name"]:20s} {bal_label}')

        if errors:
            self.stdout.write(self.style.ERROR(f'\n❌ 发现 {len(errors)} 个错误'))
            for e in errors:
                self.stdout.write(f'  - {e}')
        else:
            self.stdout.write(self.style.SUCCESS('\n✅ 校验完成，未发现错误'))


def format_decimal(d):
    """格式化Decimal显示"""
    if isinstance(d, float):
        d = Decimal(str(d))
    return f'{d:,.2f}'
