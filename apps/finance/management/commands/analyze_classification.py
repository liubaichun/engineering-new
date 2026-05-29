from django.core.management.base import BaseCommand
from apps.finance.models import Expense
from django.db.models import Count, Sum

class Command(BaseCommand):
    help = 'Analyze expense classification accuracy'

    def handle(self, *args, **options):
        self.stdout.write('=== finance_expense 全部记录 ===')
        for e in Expense.objects.filter(expense_type='finance_expense').order_by('-amount'):
            desc = e.description or ''
            supplier = e.supplier or ''
            company = e.company.name if e.company else '?'
            bs = e.bank_statement.first()
            bs_summary = bs.summary if bs else ''
            self.stdout.write(f"¥{e.amount:>10,.2f} | desc=[{desc[:40]}] | bs=[{bs_summary[:50]}] | {supplier[:20]:20s} | {company[:10]}")

        self.stdout.write('\n=== admin_expense(非报销) 前30条 ===')
        for e in Expense.objects.filter(expense_type='admin_expense').exclude(description__contains='报销').order_by('-amount')[:30]:
            desc = e.description or ''
            supplier = e.supplier or ''
            company = e.company.name if e.company else '?'
            bs = e.bank_statement.first()
            bs_summary = bs.summary if bs else ''
            self.stdout.write(f"¥{e.amount:>10,.2f} | desc=[{desc[:40]}] | bs=[{bs_summary[:50]}] | {supplier[:25]:25s} | {company[:10]}")

        self.stdout.write('\n=== main_cost 全部记录 ===')
        for e in Expense.objects.filter(expense_type='main_cost').order_by('-amount'):
            desc = e.description or ''
            supplier = e.supplier or ''
            company = e.company.name if e.company else '?'
            bs = e.bank_statement.first()
            bs_summary = bs.summary if bs else ''
            self.stdout.write(f"¥{e.amount:>10,.2f} | desc=[{desc[:40]}] | bs=[{bs_summary[:50]}] | {supplier[:25]:25s} | {company[:10]}")
