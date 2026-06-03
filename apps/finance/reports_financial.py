"""
财务补充报表 - P1增强
"""

from django.utils import timezone
from rest_framework.decorators import api_view
from apps.core.permissions import require_perms
from rest_framework.response import Response

from apps.finance.models import Company
from apps.finance.reports_common import get_user_report_companies, parse_date_range


@api_view(['GET'])
@require_perms('finance:report:read')
def income_statement_report(request):
    """利润表 — P3 新增

    基于科目余额表计算层级利润表
    API: GET /api/finance/reports/p3/income-statement/?company=X&year=2026
    """
    from .classification_rules import compute_trial_balance

    params = parse_date_range(request)
    year = params['year'] or timezone.now().year
    company_id = params['company_id']

    # 如果不指定公司，汇总所有用户有权限的公司
    if not company_id:
        companies = get_user_report_companies(request)
    else:
        companies = get_user_report_companies(request).filter(id=company_id)

    # 逐公司计算
    company_results = []
    totals = {
        'revenue': 0.0,
        'revenue_main': 0.0,
        'revenue_other': 0.0,
        'revenue_non_op': 0.0,
        'cost': 0.0,
        'tax_surcharge': 0.0,
        'admin_expense': 0.0,
        'wage_expense': 0.0,
        'social_expense': 0.0,
        'office_expense': 0.0,
        'travel_expense': 0.0,
        'entertainment_expense': 0.0,
        'comm_expense': 0.0,
        'marketing_expense': 0.0,
        'rd_expense': 0.0,
        'tax_expense': 0.0,
        'other_expense': 0.0,
        'non_op_expense': 0.0,
        'total_expense': 0.0,
        'profit': 0.0,
    }

    for company in companies:
        tb = compute_trial_balance(company.id, year)

        # 从科目余额表提取数据
        revenue = 0.0
        revenue_main = 0.0
        revenue_other = 0.0
        revenue_non_op = 0.0
        cost = 0.0
        tax_surcharge = 0.0
        non_op_expense = 0.0

        for item in tb:
            credit = float(item['credit_amount'])
            if item['account_code'] == '4001':
                revenue_main = credit
                revenue += credit
            elif item['account_code'] == '4002':
                revenue_other = credit
                revenue += credit
            elif item['account_code'] == '4003':
                revenue_non_op = credit
            elif item['account_code'] == '5001':
                cost += float(item['debit_amount'])
            elif item['account_code'] == '5003':
                tax_surcharge += float(item['debit_amount'])
            elif item['account_code'] == '5004':
                non_op_expense += float(item['debit_amount'])

        # 管理费明细
        expense_by_code = {item['account_code']: float(item['debit_amount']) for item in tb}
        wage_exp = expense_by_code.get('5002-01', 0.0)
        social_exp = expense_by_code.get('5002-02', 0.0)
        office_exp = expense_by_code.get('5002-03', 0.0)
        travel_exp = expense_by_code.get('5002-04', 0.0)
        ent_exp = expense_by_code.get('5002-05', 0.0)
        comm_exp = expense_by_code.get('5002-06', 0.0)
        mkt_exp = expense_by_code.get('5002-07', 0.0)
        rd_exp = expense_by_code.get('5002-08', 0.0)
        tax_exp = expense_by_code.get('5002-09', 0.0)
        other_exp = expense_by_code.get('5002-10', 0.0)
        admin_exp = (
            wage_exp
            + social_exp
            + office_exp
            + travel_exp
            + ent_exp
            + comm_exp
            + mkt_exp
            + rd_exp
            + tax_exp
            + other_exp
        )

        total_expense = cost + tax_surcharge + admin_exp + non_op_expense
        profit = revenue + revenue_non_op - total_expense

        row = {
            'company_id': company.id,
            'company_name': company.name,
            'revenue': round(revenue, 2),
            'revenue_main': round(revenue_main, 2),
            'revenue_other': round(revenue_other, 2),
            'revenue_non_operating': round(revenue_non_op, 2),
            'cost': round(cost, 2),
            'tax_surcharge': round(tax_surcharge, 2),
            'admin_expense': round(admin_exp, 2),
            'wage_expense': round(wage_exp, 2),
            'social_expense': round(social_exp, 2),
            'office_expense': round(office_exp, 2),
            'travel_expense': round(travel_exp, 2),
            'entertainment_expense': round(ent_exp, 2),
            'communication_expense': round(comm_exp, 2),
            'marketing_expense': round(mkt_exp, 2),
            'rd_expense': round(rd_exp, 2),
            'tax_expense': round(tax_exp, 2),
            'other_expense': round(other_exp, 2),
            'non_operating_expense': round(non_op_expense, 2),
            'total_expense': round(total_expense, 2),
            'profit': round(profit, 2),
            'profit_margin': round(profit / revenue * 100, 2) if revenue else 0,
        }
        company_results.append(row)

        # 累加汇总
        for k in totals:
            totals[k] += row.get(k, 0.0)

    # 最终汇总
    if len(company_results) > 1:
        profit_margin = round(totals['profit'] / totals['revenue'] * 100, 2) if totals['revenue'] else 0
        totals_row = {**totals, 'profit_margin': profit_margin}
    else:
        totals_row = company_results[0] if company_results else totals

    return Response(
        {
            'report': 'income_statement',
            'title': f'{year}年 利润表（会计科目版）',
            'params': {'year': year, 'company_id': company_id},
            'summary': totals_row,
            'details': company_results,
        }
    )


@api_view(['GET'])
@require_perms('finance:report:read')
def balance_sheet_report(request):
    """资产负债表（真正的版本）— P3 新增

    基于科目余额表编制，遵守 资产 = 负债 + 所有者权益
    API: GET /api/finance/reports/p3/balance-sheet/?company=X&year=2026
    """
    from .classification_rules import compute_trial_balance

    params = parse_date_range(request)
    year = params['year'] or timezone.now().year
    company_id = params['company_id']

    if not company_id:
        companies = get_user_report_companies(request)
    else:
        companies = get_user_report_companies(request).filter(id=company_id)

    company_results = []
    totals = {'total_assets': 0.0, 'total_liabilities': 0.0, 'total_equity': 0.0}

    for company in companies:
        tb = compute_trial_balance(company.id, year)

        balance = {'company_id': company.id, 'company_name': company.name}

        # 资产
        assets = {
            'bank_balance': 0.0,
            'accounts_receivable': 0.0,
            'other_receivable': 0.0,
        }
        # 负债
        liabilities = {
            'accounts_payable': 0.0,
            'payroll_payable': 0.0,
            'tax_payable': 0.0,
            'other_payable': 0.0,
        }
        # 权益
        equity = {
            'paid_in_capital': 0.0,
            'retained_earnings': 0.0,
        }

        for item in tb:
            closing = float(item['closing_balance'])
            if item['account_code'] == '1001':
                assets['bank_balance'] = closing
            elif item['account_code'] == '1002':
                assets['accounts_receivable'] = closing
            elif item['account_code'] == '1003':
                assets['other_receivable'] = closing
            elif item['account_code'] == '2001':
                liabilities['accounts_payable'] = closing
            elif item['account_code'] == '2002':
                liabilities['payroll_payable'] = closing
            elif item['account_code'] == '2003':
                liabilities['tax_payable'] = closing
            elif item['account_code'] == '2004':
                liabilities['other_payable'] = closing
            elif item['account_code'] == '3001':
                equity['paid_in_capital'] = closing
            elif item['account_code'] == '3002':
                equity['retained_earnings'] = closing

        total_assets = sum(assets.values())
        total_liabilities = sum(liabilities.values())
        total_equity = sum(equity.values())

        balance['assets'] = {k: round(v, 2) for k, v in assets.items()}
        balance['total_assets'] = round(total_assets, 2)
        balance['liabilities'] = {k: round(v, 2) for k, v in liabilities.items()}
        balance['total_liabilities'] = round(total_liabilities, 2)
        balance['equity'] = {k: round(v, 2) for k, v in equity.items()}
        balance['total_equity'] = round(total_equity, 2)
        balance['liabilities_plus_equity'] = round(total_liabilities + total_equity, 2)
        balance['diff'] = round(total_assets - (total_liabilities + total_equity), 2)

        company_results.append(balance)

        totals['total_assets'] += total_assets
        totals['total_liabilities'] += total_liabilities
        totals['total_equity'] += total_equity

    return Response(
        {
            'report': 'balance_sheet',
            'title': f'{year}年 资产负债表（会计科目版）',
            'params': {'year': year, 'company_id': company_id},
            'summary': {
                'total_assets': round(totals['total_assets'], 2),
                'total_liabilities': round(totals['total_liabilities'], 2),
                'total_equity': round(totals['total_equity'], 2),
                'liabilities_plus_equity': round(totals['total_liabilities'] + totals['total_equity'], 2),
            },
            'details': company_results,
        }
    )
