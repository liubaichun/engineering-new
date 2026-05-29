#!/usr/bin/env python3
"""发票到期提醒脚本 — 每日检查逾期待付/待收发票"""

import os
import sys
from datetime import date, timedelta

# Django 环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, '/root/engineering-new')

import django

django.setup()

from apps.finance.models import Invoice

today = date.today()

# ============================================================
# 1. 已逾期的发票（due_date < today，且状态未完成）
# ============================================================
overdue_expense = Invoice.objects.filter(due_date__lt=today, type='expense', status='pending').order_by('due_date')

overdue_income = Invoice.objects.filter(due_date__lt=today, type='income', status='pending').order_by('due_date')

# ============================================================
# 2. 即将到期的发票（due_date 在未来7天内）
# ============================================================
cutoff = today + timedelta(days=7)
coming_expense = Invoice.objects.filter(
    due_date__gte=today, due_date__lte=cutoff, type='expense', status='pending'
).order_by('due_date')

coming_income = Invoice.objects.filter(
    due_date__gte=today, due_date__lte=cutoff, type='income', status='pending'
).order_by('due_date')

# ============================================================
# 3. 组消息
# ============================================================
lines = []
total_alerts = 0

if overdue_expense:
    total_alerts += overdue_expense.count()
    lines.append(f'🔴 **逾期未付发票（{overdue_expense.count()} 条）**')
    for inv in overdue_expense:
        days = (today - inv.due_date).days
        lines.append(
            f'  - {inv.invoice_no} | {inv.counterparty} | ¥{inv.amount} | 已逾期 {days} 天 | 到期日 {inv.due_date}'
        )
    lines.append('')

if overdue_income:
    total_alerts += overdue_income.count()
    lines.append(f'🔴 **逾期未收发票（{overdue_income.count()} 条）**')
    for inv in overdue_income:
        days = (today - inv.due_date).days
        lines.append(
            f'  - {inv.invoice_no} | {inv.counterparty} | ¥{inv.amount} | 已逾期 {days} 天 | 到期日 {inv.due_date}'
        )
    lines.append('')

if coming_expense:
    total_alerts += coming_expense.count()
    lines.append(f'🟡 **即将到期应付（{coming_expense.count()} 条）**')
    for inv in coming_expense:
        d = (inv.due_date - today).days
        label = '今天到期' if d == 0 else f'还剩 {d} 天'
        lines.append(f'  - {inv.invoice_no} | {inv.counterparty} | ¥{inv.amount} | {label} | 到期日 {inv.due_date}')
    lines.append('')

if coming_income:
    total_alerts += coming_income.count()
    lines.append(f'🟡 **即将到期应收（{coming_income.count()} 条）**')
    for inv in coming_income:
        d = (inv.due_date - today).days
        label = '今天到期' if d == 0 else f'还剩 {d} 天'
        lines.append(f'  - {inv.invoice_no} | {inv.counterparty} | ¥{inv.amount} | {label} | 到期日 {inv.due_date}')
    lines.append('')

if not lines:
    # 静默退出 — 没有逾期/即将到期的发票，不发通知
    sys.exit(0)

header = f'📋 **发票到期提醒**  |  {today.strftime("%Y-%m-%d")}\n{"─" * 40}'
footer = f'\n{"─" * 40}\n💡 请及时处理到期发票，避免产生滞纳金或影响信用。'

print(f'{header}\n{"".join(lines)}{footer}')
