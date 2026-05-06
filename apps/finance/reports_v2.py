"""
财务补充报表 - P1增强
"""
from datetime import datetime, timedelta
from decimal import Decimal

from django.db.models import Sum, Count, Q, F
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.finance.models import Company, Income, Expense, Invoice, WageRecord
from apps.finance.models_bank import BankStatement
from apps.crm.models import Client, Supplier


def agg(qs, field):
    """安全聚合，返回float，None当0处理"""
    v = qs.aggregate(t=Sum(field))['t']
    return float(v) if v is not None else 0.0




# ─── 通用筛选逻辑 ─────────────────────────────────────────────────────────
def parse_date_range(request):
    year = request.query_params.get('year', str(timezone.now().year))
    month = request.query_params.get('month')
    company_id = request.query_params.get('company')
    return {
        'company_id': int(company_id) if company_id else None,
        'year': int(year) if year else None,
        'month': int(month) if month else None,
    }


def build_qs(model, company_id=None, year=None, month=None):
    qs = model.objects.all()
    if company_id: qs = qs.filter(company_id=company_id)
    if year: qs = qs.filter(date__year=year)
    if month: qs = qs.filter(date__month=month)
    return qs


# ─── 1. 现金流量表 ───────────────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def cash_flow_report(request):
    params = parse_date_range(request)
    year = params['year']
    company_id = params['company_id']

    companies = Company.objects.all()
    if company_id:
        companies = companies.filter(id=company_id)

    rows = []
    grand_income = 0
    grand_expense = 0

    for company in companies:
        # 期初余额（年初之前累计）
        begin_inc = Income.objects.filter(company=company)
        begin_exp = Expense.objects.filter(company=company)
        if year:
            begin_inc = begin_inc.filter(date__lt=f"{year}-01-01")
            begin_exp = begin_exp.filter(date__lt=f"{year}-01-01")
        begin_balance = (
            agg(begin_inc, 'amount') -
            agg(begin_exp, 'amount')
        )

        monthly_data = []
        for month in range(1, 13):
            inc_total = agg(build_qs(Income, company.id, year, month), 'amount')
            exp_total = agg(build_qs(Expense, company.id, year, month), 'amount')
            begin_balance = begin_balance + inc_total - exp_total

            monthly_data.append({
                'month': month,
                'income': inc_total,
                'expense': exp_total,
                'net': inc_total - exp_total,
                'end_balance': begin_balance,
            })

        year_income = sum(m['income'] for m in monthly_data)
        year_expense = sum(m['expense'] for m in monthly_data)
        rows.append({
            'company_id': company.id,
            'company_name': company.name,
            'year': year,
            'year_income': year_income,
            'year_expense': year_expense,
            'year_net': year_income - year_expense,
            'monthly': [m for m in monthly_data if m['income'] > 0 or m['expense'] > 0],
        })
        grand_income += year_income
        grand_expense += year_expense

    return Response({
        'report': 'cash_flow',
        'title': f'{year}年 现金流量表',
        'params': params,
        'results': rows,
        'summary': {
            'total_income': grand_income,
            'total_expense': grand_expense,
            'total_net': grand_income - grand_expense,
        }
    })


# ─── 2. 应收应付账龄分析 ────────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ar_ap_aging_report(request):
    params = parse_date_range(request)
    today = timezone.now().date()
    company_id = params['company_id']

    def age_bucket(due_date):
        if not due_date:
            return 'unknown'
        days = (today - due_date).days
        if days <= 30: return 'bucket_1_30'
        elif days <= 60: return 'bucket_31_60'
        elif days <= 90: return 'bucket_61_90'
        else: return 'bucket_over_90'

    def build_arap(qs, name_field):
        companies = Company.objects.all()
        if company_id:
            companies = companies.filter(id=company_id)

        results = []
        for company in companies:
            records = qs.filter(company=company)
            buckets = {'bucket_1_30': 0, 'bucket_31_60': 0, 'bucket_61_90': 0, 'bucket_over_90': 0}
            details = []
            for rec in records:
                due = getattr(rec, 'due_date', None) or getattr(rec, 'date', None) or today
                bucket = age_bucket(due)
                amount = float(getattr(rec, 'amount', 0) or 0)
                if bucket in buckets:
                    buckets[bucket] += amount
                name = getattr(rec, name_field, '') or ''
                details.append({
                    'id': rec.id, 'name': str(name), 'amount': amount,
                    'due_date': str(due), 'days': (today - due).days if due else 0,
                    'bucket': bucket,
                })
            total = sum(buckets.values())
            results.append({
                'company_id': company.id, 'company_name': company.name,
                'total': total, 'buckets': buckets,
                'details': sorted(details, key=lambda x: x['days'], reverse=True)[:30],
            })
        return results

    ar_results = build_arap(
        Income.objects.filter(status='pending'),
        'customer'
    )
    ap_results = build_arap(
        Expense.objects.filter(status='pending'),
        'supplier'
    )

    return Response({
        'report': 'ar_ap_aging',
        'title': '应收应付账龄分析',
        'as_of_date': str(today),
        'params': params,
        'accounts_receivable': ar_results,
        'accounts_payable': ap_results,
        'summary': {
            'total_ar': sum(r['total'] for r in ar_results),
            'total_ap': sum(r['total'] for r in ap_results),
            'net_position': sum(r['total'] for r in ar_results) - sum(r['total'] for r in ap_results),
        }
    })


# ─── 3. 客户收入排行 ────────────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def customer_revenue_report(request):
    params = parse_date_range(request)
    year = params['year']
    month = params['month']
    company_id = params['company_id']
    limit = int(request.query_params.get('limit', 50))

    inc_qs = build_qs(Income, company_id, year, month)

    global_stats = {}
    for inc in inc_qs.select_related('company'):
        key = f"{inc.company.name} / {inc.customer or '（未指定）'}"
        if key not in global_stats:
            global_stats[key] = {
                'company': inc.company.name,
                'customer': inc.customer or '（未指定）',
                'total': 0.0, 'count': 0
            }
        global_stats[key]['total'] += float(inc.amount or 0)
        global_stats[key]['count'] += 1

    ranked = sorted(global_stats.items(), key=lambda x: x[1]['total'], reverse=True)[:limit]
    results = [
        {'rank': r + 1, 'key': k, **v}
        for r, (k, v) in enumerate(ranked)
    ]

    return Response({
        'report': 'customer_revenue',
        'title': '客户收入排行',
        'params': params,
        'global_ranking': results,
        'summary': {
            'total_revenue': sum(x['total'] for x in results),
            'customer_count': len(results),
        }
    })


# ─── 4. 供应商支出报表 ──────────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def supplier_expense_report(request):
    params = parse_date_range(request)
    year = params['year']
    month = params['month']
    company_id = params['company_id']
    limit = int(request.query_params.get('limit', 50))

    exp_qs = build_qs(Expense, company_id, year, month)

    global_stats = {}
    for exp in exp_qs.select_related('company', 'project'):
        supplier = exp.supplier or '（未指定）'
        if supplier not in global_stats:
            global_stats[supplier] = {
                'company': exp.company.name,
                'supplier': supplier,
                'total': 0.0, 'count': 0,
                'types': {},
            }
        global_stats[supplier]['total'] += float(exp.amount or 0)
        global_stats[supplier]['count'] += 1
        exp_type = exp.expense_type or '未分类'
        global_stats[supplier]['types'][exp_type] = \
            global_stats[supplier]['types'].get(exp_type, 0.0) + float(exp.amount or 0)

    ranked = sorted(global_stats.items(), key=lambda x: x[1]['total'], reverse=True)[:limit]
    results = [
        {'rank': r + 1, **v}
        for r, (k, v) in enumerate(ranked)
    ]

    return Response({
        'report': 'supplier_expense',
        'title': '供应商支出报表',
        'params': params,
        'results': results,
        'summary': {
            'total_expense': sum(r['total'] for r in results),
            'supplier_count': len(results),
        }
    })


# ─── 5. 税费汇总表 ─────────────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def tax_summary_report(request):
    params = parse_date_range(request)
    year = params['year']
    month = params['month']
    company_id = params['company_id']

    companies = Company.objects.all()
    if company_id:
        companies = companies.filter(id=company_id)

    results = []
    grand_invoice_tax = 0
    grand_personal_tax = 0

    for company in companies:
        inv_qs = Invoice.objects.filter(company=company)
        w_qs = WageRecord.objects.filter(company=company)
        if year:
            inv_qs = inv_qs.filter(issue_date__year=year)
            w_qs = w_qs.filter(year=year)
        if month:
            inv_qs = inv_qs.filter(issue_date__month=month)
            w_qs = w_qs.filter(month=month)

        invoice_tax = agg(inv_qs, 'tax_amount')
        personal_tax = agg(w_qs, 'personal_tax')

        results.append({
            'company_id': company.id,
            'company_name': company.name,
            'invoice_tax': invoice_tax,
            'personal_tax': personal_tax,
            'total_tax': invoice_tax + personal_tax,
        })
        grand_invoice_tax += invoice_tax
        grand_personal_tax += personal_tax

    return Response({
        'report': 'tax_summary',
        'title': f'{year}年 税费汇总表',
        'params': params,
        'results': results,
        'summary': {
            'total_invoice_tax': grand_invoice_tax,
            'total_personal_tax': grand_personal_tax,
            'total_tax': grand_invoice_tax + grand_personal_tax,
        }
    })


# ─── 6. 预算执行表 ──────────────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def budget_execution_report(request):
    params = parse_date_range(request)
    year = params['year'] or timezone.now().year
    company_id = params['company_id']

    EXPENSE_TYPES = [
        ('salary', '工资薪酬'),
        ('social', '社保公积金'),
        ('office', '办公费用'),
        ('travel', '差旅费用'),
        ('communication', '通讯费用'),
        ('entertainment', '业务招待'),
        ('marketing', '市场营销'),
        ('rd', '研发费用'),
        ('tax', '税费'),
        ('other', '其他'),
    ]

    companies = Company.objects.all()
    if company_id:
        companies = companies.filter(id=company_id)

    results = []
    grand_actual = 0

    for company in companies:
        type_totals = []
        for exp_type, label in EXPENSE_TYPES:
            if exp_type == 'salary':
                total = agg(WageRecord.objects.filter(company=company, year=year), 'gross_wage')
            elif exp_type == 'social':
                total = agg(WageRecord.objects.filter(company=company, year=year), 'social_security')
            else:
                total = agg(Expense.objects.filter(
                    company=company, date__year=year, expense_type=exp_type), 'amount')
            type_totals.append({'type': exp_type, 'label': label, 'actual': total})

        total_actual = sum(t['actual'] for t in type_totals)
        results.append({
            'company_id': company.id,
            'company_name': company.name,
            'year': year,
            'by_type': type_totals,
            'total_actual': total_actual,
        })
        grand_actual += total_actual

    return Response({
        'report': 'budget_execution',
        'title': f'{year}年 预算执行表',
        'params': params,
        'results': results,
        'summary': {'total_actual': grand_actual}
    })
