"""
财务补充报表 - P1增强
"""

from rest_framework.decorators import api_view
from apps.core.permissions import require_perms
from rest_framework.response import Response

from apps.finance.models import Company
from apps.finance.models_bank import BankStatement


@api_view(['GET'])
@require_perms('finance:report:read')
def cash_flow_report(request):
    params = parse_date_range(request)
    year = params['year']
    month = params['month']  # 可选，若指定则只看该月
    company_id = params['company_id']

    # month 参数：若指定则只统计该月，否则统计全年
    if month:
        months_to_process = [month]
    else:
        months_to_process = list(range(1, 13))

    companies = Company.objects.all()
    if company_id:
        companies = companies.filter(id=company_id)

    rows = []
    grand_income = 0
    grand_expense = 0

    for company in companies:
        # ── 取该公司所有银行账户的流水 ───────────────────────────────────────
        bs_qs = BankStatement.objects.filter(company=company).order_by('transaction_date', 'id')

        # 期初余额：取 year-01-01 之前最近一条有余额的记录
        year_start = f'{year}-01-01'
        prior_bs = (
            bs_qs.filter(transaction_date__lt=year_start)
            .exclude(balance__isnull=True)
            .order_by('transaction_date', 'id')
        )
        begin_balance = 0.0
        if prior_bs.exists():
            begin_balance = float(prior_bs.last().balance or 0)

        monthly_data = []
        for month in months_to_process:
            month_start = f'{year}-{month:02d}-01'
            # 下个月1日
            if month == 12:
                month_end = f'{year + 1}-01-01'
            else:
                month_end = f'{year}-{month + 1:02d}-01'

            # 该月所有流水
            month_bs = bs_qs.filter(
                transaction_date__gte=month_start,
                transaction_date__lt=month_end,
            )

            inc_total = 0.0
            exp_total = 0.0
            for bs in month_bs:
                amt = float(bs.amount or 0)
                if bs.direction == 'income':
                    inc_total += amt
                else:
                    exp_total += amt

            # 月末余额：优先取该月最后一条有余额的记录
            # ── 【P0-3 修复】───────────────────────────────────────────────
            # 原逻辑：若 month_end_bs 不存在，则用 begin+inc-exp 推算
            # 问题：begin+inc-exp 是"全部交易完成后"的推算值，不代表真实月末银行账户余额
            #      真实月末余额 = 该月最后一笔有余额记录的值（银行系统快照的时点余额）
            # 修复：若无月末余额记录，取该月最后一笔有余额的发生额记录作为月末余额
            month_end_bs = month_bs.exclude(balance__isnull=True).order_by('transaction_date', 'id')
            if month_end_bs.exists():
                end_balance = float(month_end_bs.last().balance or 0)
            elif month_bs.exists():
                # 月末无快照余额，但月内有发生额 → 取月内最后一笔有余额记录
                last_with_balance = month_bs.exclude(balance__isnull=True).order_by('transaction_date', 'id').last()
                if last_with_balance:
                    end_balance = float(last_with_balance.balance or 0)
                else:
                    end_balance = begin_balance + inc_total - exp_total
                # else: 整个月无任何余额记录，保留 begin+inc-exp 作为近似

            # 只有有发生额才记录
            if inc_total > 0 or exp_total > 0:
                monthly_data.append(
                    {
                        'month': month,
                        'income': round(inc_total, 2),
                        'expense': round(exp_total, 2),
                        'net': round(inc_total - exp_total, 2),
                        'end_balance': round(end_balance, 2),
                    }
                )

            begin_balance = end_balance  # 下月期初 = 本月末

        year_income = sum(m['income'] for m in monthly_data)
        year_expense = sum(m['expense'] for m in monthly_data)
        rows.append(
            {
                'company_id': company.id,
                'company_name': company.name,
                'year': year,
                'year_income': round(year_income, 2),
                'year_expense': round(year_expense, 2),
                'year_net': round(year_income - year_expense, 2),
                'monthly': monthly_data,
            }
        )
        grand_income += year_income
        grand_expense += year_expense

    return Response(
        {
            'report': 'cash_flow',
            'title': f'{year}年 银行余额变动表',
            'params': params,
            'results': rows,
            'summary': {
                'total_income': round(grand_income, 2),
                'total_expense': round(grand_expense, 2),
                'total_net': round(grand_income - grand_expense, 2),
            },
        }
    )


# ─── 2. 应收应付账龄分析 ────────────────────────────────────────────────
