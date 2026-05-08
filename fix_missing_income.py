"""
一次性修复脚本：补建因"往来款分流"逻辑而缺失的Income记录

运行方式：
  cd /root/engineering-new
  source venv/bin/activate
  python fix_missing_income.py

背景：原 bank_import_views.py 第849-854行有"往来款只写BankStatement跳过Income"的错误逻辑，
      已bd6faaf修复。此脚本处理修复前已入库但缺失Income的5条记录。
"""
import os, sys
sys.path.insert(0, '/root/engineering-new')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from apps.finance.models import Company, Income
from apps.finance.models_bank import BankStatement
from decimal import Decimal

def fix():
    company = Company.objects.get(id=6)
    # 找所有direction=income但没有matched_income_id的BankStatement
    bs_list = BankStatement.objects.filter(
        company=company,
        direction='income',
        matched_income_id__isnull=True
    ).order_by('transaction_date')

    if not bs_list.exists():
        print('没有需要修复的记录')
        return

    print(f'发现 {bs_list.count()} 条缺失Income的BankStatement：')
    fixed = 0
    for bs in bs_list:
        # 跳过已存在的重复Income（按日期+金额+客户去重）
        exists = Income.objects.filter(
            company=company,
            customer=bs.counterparty_name,
            amount=bs.amount,
            date=bs.transaction_date
        ).exists()
        if exists:
            print(f'  跳过（Income已存在）: BS {bs.id} {bs.transaction_date} {bs.counterparty_name} {bs.amount}')
            # 回填FK
            inc = Income.objects.filter(
                company=company,
                customer=bs.counterparty_name,
                amount=bs.amount,
                date=bs.transaction_date
            ).first()
            bs.matched_income = inc
            bs.save(update_fields=['matched_income'])
            print(f'    → 回填matched_income_id={inc.id}')
            continue

        # 创建Income
        inc = Income.objects.create(
            company=company,
            customer=bs.counterparty_name,
            source='bank_import',
            amount=bs.amount,
            date=bs.transaction_date,
            description=bs.summary + (f" [流水号:{bs.bank_serial}]" if bs.bank_serial else ''),
        )
        # 回填FK
        bs.matched_income = inc
        bs.save(update_fields=['matched_income'])
        print(f'  创建Income {inc.id}: BS {bs.id} {bs.transaction_date} {bs.counterparty_name} {bs.amount}')
        fixed += 1

    print(f'\n修复完成：{fixed} 条Income已创建并回填FK')

    # 验证
    total_income = Income.objects.filter(company=company).count()
    bs_income = BankStatement.objects.filter(company=company, direction='income').count()
    bs_income_with_fk = BankStatement.objects.filter(company=company, direction='income', matched_income_id__isnull=False).count()
    print(f'\n验证：')
    print(f'  Income台账总数: {total_income}')
    print(f'  BankStatement收入流水: {bs_income}')
    print(f'  其中有matched_income_id: {bs_income_with_fk}')
    print(f'  缺失: {bs_income - bs_income_with_fk}')

if __name__ == '__main__':
    fix()
