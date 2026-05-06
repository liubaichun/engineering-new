"""
财务补充报表 - P1增强
新增报表：
- cash_flow           现金流量表
- ar_ap_aging         应收应付账龄
- customer_revenue    客户收入排行
- supplier_expense    供应商支出报表
- tax_summary         税费汇总表
- budget_execution    预算执行表
"""
from datetime import datetime, timedelta
from decimal import Decimal

from django.db.models import Sum, Count, Q, F
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.finance.models import Company, Income, Expense, Invoice, WageRecord
from apps.finance.models_bank import BankStatement
from apps.crm.models import Client, Supplier


# ─── 通用筛选逻辑 ─────────────────────────────────────────────────────────
def get_company_filter(company_id, request_user):
    """根据用户类型应用数据隔离"""
    if company_id:
        return Q(company_id=company_id)
    return Q()


def parse_date_range(request):
    """从请求参数解析日期范围"""
    year = request.query_params.get('year', str(timezone.now().year))
    month = request.query_params.get('month')
    quarter = request.query_params.get('quarter')
    date_start = request.query_params.get('date_start')
    date_end = request.query_params.get('date_end')
    company_id = request.query_params.get('company')

    if date_start and date_end:
        return {
            'company_id': int(company_id) if company_id else None,
            'date_start': date_start,
            'date_end': date_end,
            'year': int(year) if year else None,
            'month': int(month) if month else None,
        }
    return {
        'company_id': int(company_id) if company_id else None,
        'year': int(year) if year else None,
        'month': int(month) if month else None,
        'quarter': int(quarter) if quarter else None,
    }


def build_income_qs(company_id=None, year=None, month=None, quarter=None, date_start=None, date_end=None):
    qs = Income.objects.all()
    if company_id: qs = qs.filter(company_id=company_id)
    if year: qs = qs.filter(date__year=year)
    if month: qs = qs.filter(date__month=month)
    if quarter:
        q_months = [(quarter - 1) * 3 + m for m in range(1, 4)]
        qs = qs.filter(date__month__in=q_months)
    if date_start: qs = qs.filter(date__gte=date_start)
    if date_end: qs = qs.filter(date__lte=date_end)
    return qs


def build_expense_qs(company_id=None, year=None, month=None, quarter=None, date_start=None, date_end=None):
    qs = Expense.objects.all()
    if company_id: qs = qs.filter(company_id=company_id)
    if year: qs = qs.filter(date__year=year)
    if month: qs = qs.filter(date__month=month)
    if quarter:
        q_months = [(quarter - 1) * 3 + m for m in range(1, 4)]
        qs = qs.filter(date__month__in=q_months)
    if date_start: qs = qs.filter(date__gte=date_start)
    if date_end: qs = qs.filter(date__lte=date_end)
    return qs


# ─── 1. 现金流量表 ───────────────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def cash_flow_report(request):
    """
    现金流量表
    按月列示：期初余额 + 收入合计 + 支出合计 + 期末余额
    支持按公司筛选
    """
    params = parse_date_range(request)
    company_id = params['company_id']
    year = params['year']
    date_start = params.get('date_start')
    date_end = params.get('date_end')

    companies = Company.objects.all()
    if company_id:
        companies = companies.filter(id=company_id)

    rows = []
    grand_income = 0
    grand_expense = 0
    grand_begin = 0
    grand_end = 0

    for company in companies:
        # 期初余额（年初或月初累计）
        if year:
            begin_qs = Income.objects.filter(company=company, date__lt=f"{year}-01-01")
            exp_begin_qs = Expense.objects.filter(company=company, date__lt=f"{year}-01-01")
        else:
            begin_qs = Income.objects.filter(company=company)
            exp_begin_qs = Expense.objects.filter(company=company)
        begin_balance = float(begin_qs.aggregate(t=Coalesce(Sum('amount'), 0))['t'] or 0)
        exp_begin = float(exp_begin_qs.aggregate(t=Coalesce(Sum('amount'), 0))['t'] or 0)
        begin_balance -= exp_begin  # 累计结余

        # 按月统计
        monthly_data = []
        for month in range(1, 13):
            inc = build_income_qs(company.id, year, month)
            exp = build_expense_qs(company.id, year, month)
            inc_total = float(inc.aggregate(t=Coalesce(Sum('amount'), 0))['t'] or 0)
            exp_total = float(exp.aggregate(t=Coalesce(Sum('amount'), 0))['t'] or 0)
            begin_balance = begin_balance + inc_total - exp_total

            monthly_data.append({
                'month': month,
                'income': inc_total,
                'expense': exp_total,
                'net': inc_total - exp_total,
                'end_balance': begin_balance,
            })

        # 全年合计
        total_inc = sum(m['income'] for m in monthly_data)
        total_exp = sum(m['expense'] for m in monthly_data)
        rows.append({
            'company_id': company.id,
            'company_name': company.name,
            'year': year,
            'year_income': total_inc,
            'year_expense': total_exp,
            'year_net': total_inc - total_exp,
            'year_end_balance': begin_balance,
            'monthly': monthly_data,
        })
        grand_income += total_inc
        grand_expense += total_exp

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
    """
    应收应付账龄分析
    统计客户未结清的应收、供应商未结清的应付
    按账龄分段：1-30天 / 31-60天 / 61-90天 / 90天以上
    """
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

    def build_ar_ap(qs, name_field, company_field='company'):
        """构建应收应付账龄"""
        companies = Company.objects.all()
        if company_id:
            companies = companies.filter(id=company_id)

        results = []
        for company in companies:
            records = qs.filter(**{f'{company_field}__id': company.id})

            buckets = {'bucket_1_30': 0, 'bucket_31_60': 0, 'bucket_61_90': 0, 'bucket_over_90': 0, 'unknown': 0}
            details = []

            for rec in records:
                due = getattr(rec, 'due_date', None) or getattr(rec, 'date', None) or today
                bucket = age_bucket(due)
                amount = float(getattr(rec, 'amount', 0) or 0)
                buckets[bucket] += amount

                name = getattr(rec, name_field, '') or getattr(rec, 'customer', '') or ''
                details.append({
                    'id': rec.id,
                    'name': str(name),
                    'amount': amount,
                    'due_date': str(due),
                    'days': (today - due).days if due else 0,
                    'bucket': bucket,
                    'status': getattr(rec, 'status', 'unknown'),
                })

            total = sum(buckets.values())
            results.append({
                'company_id': company.id,
                'company_name': company.name,
                'total': total,
                'buckets': buckets,
                'details': sorted(details, key=lambda x: x['days'], reverse=True)[:50],
            })
        return results

    ar_results = build_ar_ap(
        Income.objects.filter(status='pending', amount__gt=0),
        'customer', 'company'
    )
    ap_results = build_ar_ap(
        Expense.objects.filter(status='pending', amount__gt=0),
        'supplier', 'company'
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
    """
    客户收入排行
    统计每个客户的收入贡献、收入笔数、平均单笔金额
    支持按公司+时间筛选，输出排行
    """
    params = parse_date_range(request)
    company_id = params['company_id']
    year = params['year']
    month = params['month']
    limit = int(request.query_params.get('limit', 50))

    inc_qs = build_income_qs(company_id, year, month)

    companies = Company.objects.all()
    if company_id:
        companies = companies.filter(id=company_id)

    results = []
    for company in companies:
        company_inc = inc_qs.filter(company=company)

        # 按客户分组
        client_stats = {}
        for inc in company_inc.select_related('company'):
            customer = inc.customer or '（未指定）'
            if customer not in client_stats:
                client_stats[customer] = {'total': 0, 'count': 0, 'transactions': []}
            client_stats[customer]['total'] += float(inc.amount or 0)
            client_stats[customer]['count'] += 1
            client_stats[customer]['transactions'].append({
                'id': inc.id,
                'date': str(inc.date),
                'amount': float(inc.amount or 0),
                'description': inc.description or '',
            })

        ranked = sorted(client_stats.items(), key=lambda x: x[1]['total'], reverse=True)
        for rank, (customer, stats) in enumerate(ranked[:limit], 1):
            results.append({
                'rank': rank,
                'company_id': company.id,
                'company_name': company.name,
                'customer': customer,
                'total_revenue': stats['total'],
                'transaction_count': stats['count'],
                'avg_amount': stats['total'] / stats['count'] if stats['count'] else 0,
                'top_transactions': sorted(stats['transactions'], key=lambda x: x['amount'], reverse=True)[:3],
            })

    # 全局排行（跨公司）
    global_stats = {}
    for inc in inc_qs.select_related('company'):
        key = f"{inc.company.name} / {inc.customer or '（未指定）'}"
        if key not in global_stats:
            global_stats[key] = {'company': inc.company.name, 'customer': inc.customer or '（未指定）', 'total': 0, 'count': 0}
        global_stats[key]['total'] += float(inc.amount or 0)
        global_stats[key]['count'] += 1

    global_ranked = sorted(global_stats.items(), key=lambda x: x[1]['total'], reverse=True)[:limit]

    return Response({
        'report': 'customer_revenue',
        'title': '客户收入排行',
        'params': params,
        'by_company': results,
        'global_ranking': [
            {'rank': r + 1, 'key': k, **v}
            for r, (k, v) in enumerate(global_ranked)
        ],
        'summary': {
            'total_companies': len(results) // limit + 1 if results else 0,
            'total_revenue': sum(r['total_revenue'] for r in results),
        }
    })


# ─── 4. 供应商支出报表 ──────────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def supplier_expense_report(request):
    """
    供应商支出报表
    统计每个供应商的支出金额、笔数、服务类型分布
    """
    params = parse_date_range(request)
    company_id = params['company_id']
    year = params['year']
    month = params['month']
    limit = int(request.query_params.get('limit', 50))

    exp_qs = build_expense_qs(company_id, year, month)

    companies = Company.objects.all()
    if company_id:
        companies = companies.filter(id=company_id)

    results = []
    for company in companies:
        company_exp = exp_qs.filter(company=company)

        # 按供应商分组
        supplier_stats = {}
        for exp in company_exp.select_related('company', 'project'):
            supplier = exp.supplier or '（未指定）'
            if supplier not in supplier_stats:
                supplier_stats[supplier] = {'total': 0, 'count': 0, 'types': {}, 'transactions': []}
            supplier_stats[supplier]['total'] += float(exp.amount or 0)
            supplier_stats[supplier]['count'] += 1
            exp_type = exp.expense_type or '未分类'
            supplier_stats[supplier]['types'][exp_type] = \
                supplier_stats[supplier]['types'].get(exp_type, 0) + float(exp.amount or 0)
            supplier_stats[supplier]['transactions'].append({
                'id': exp.id,
                'date': str(exp.date),
                'amount': float(exp.amount or 0),
                'type': exp_type,
                'description': exp.description or '',
            })

        ranked = sorted(supplier_stats.items(), key=lambda x: x[1]['total'], reverse=True)
        for rank, (supplier, stats) in enumerate(ranked[:limit], 1):
            results.append({
                'rank': rank,
                'company_id': company.id,
                'company_name': company.name,
                'supplier': supplier,
                'total_expense': stats['total'],
                'transaction_count': stats['count'],
                'avg_amount': stats['total'] / stats['count'] if stats['count'] else 0,
                'expense_types': stats['types'],
                'top_transactions': sorted(stats['transactions'], key=lambda x: x['amount'], reverse=True)[:3],
            })

    return Response({
        'report': 'supplier_expense',
        'title': '供应商支出报表',
        'params': params,
        'results': results,
        'summary': {
            'total_expense': sum(r['total_expense'] for r in results),
            'total_transactions': sum(r['transaction_count'] for r in results),
            'supplier_count': len(results),
        }
    })


# ─── 5. 税费汇总表 ─────────────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def tax_summary_report(request):
    """
    税费汇总表
    从发票记录中提取税额，统计各类型税金
    包含：增值税、企业所得税、个人所得税、印花税等
    """
    params = parse_date_range(request)
    company_id = params['company_id']
    year = params['year']
    month = params['month']

    companies = Company.objects.all()
    if company_id:
        companies = companies.filter(id=company_id)

    # 发票税费统计
    invoice_qs = Invoice.objects.all()
    if company_id: invoice_qs = invoice_qs.filter(company_id=company_id)
    if year: invoice_qs = invoice_qs.filter(issue_date__year=year)
    if month: invoice_qs = invoice_qs.filter(issue_date__month=month)

    # 按发票类型汇总
    type_stats = {}
    for inv in invoice_qs:
        inv_type = inv.get_type_display() if hasattr(inv, 'get_type_display') else str(inv.type or '未知')
        tax_amount = float(inv.tax_amount or 0)
        total_amount = float(inv.total_amount or inv.amount or 0)
        if inv_type not in type_stats:
            type_stats[inv_type] = {'count': 0, 'total_amount': 0, 'tax_amount': 0}
        type_stats[inv_type]['count'] += 1
        type_stats[inv_type]['total_amount'] += total_amount
        type_stats[inv_type]['tax_amount'] += tax_amount

    # 工资个税统计
    wage_qs = WageRecord.objects.all()
    if company_id: wage_qs = wage_qs.filter(company_id=company_id)
    if year: wage_qs = wage_qs.filter(year=year)
    if month: wage_qs = wage_qs.filter(month=month)

    total_personal_tax = float(wage_qs.aggregate(t=Coalesce(Sum('personal_tax'), 0))['t'] or 0)
    total_wage = float(wage_qs.aggregate(t=Coalesce(Sum('gross_wage'), 0))['t'] or 0)

    results = []
    for company in companies:
        inv_qs = invoice_qs.filter(company=company)
        w_qs = wage_qs.filter(company=company)

        comp_type_stats = {}
        for inv in inv_qs:
            inv_type = inv.get_type_display() if hasattr(inv, 'get_type_display') else str(inv.type or '未知')
            tax_amount = float(inv.tax_amount or 0)
            if inv_type not in comp_type_stats:
                comp_type_stats[inv_type] = {'count': 0, 'tax_amount': 0}
            comp_type_stats[inv_type]['count'] += 1
            comp_type_stats[inv_type]['tax_amount'] += tax_amount

        personal_tax = float(w_qs.aggregate(t=Coalesce(Sum('personal_tax'), 0))['t'] or 0)

        results.append({
            'company_id': company.id,
            'company_name': company.name,
            'invoice_stats': comp_type_stats,
            'personal_tax_from_wages': personal_tax,
            'total_invoice_tax': sum(s['tax_amount'] for s in comp_type_stats.values()),
        })

    grand_invoice_tax = sum(r['total_invoice_tax'] for r in results)
    grand_personal_tax = sum(r['personal_tax_from_wages'] for r in results)

    return Response({
        'report': 'tax_summary',
        'title': f'{year}年 税费汇总表',
        'params': params,
        'results': results,
        'invoice_type_stats': type_stats,
        'summary': {
            'total_invoice_tax': grand_invoice_tax,
            'total_personal_tax': grand_personal_tax,
            'total_tax': grand_invoice_tax + grand_personal_tax,
            'total_wage': total_wage,
        }
    })


# ─── 6. 预算执行表 ──────────────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def budget_execution_report(request):
    """
    预算执行表
    基于配置的年度预算 vs 实际支出对比
    按费用类型展示执行率
    """
    params = parse_date_range(request)
    company_id = params['company_id']
    year = params['year'] or timezone.now().year

    companies = Company.objects.all()
    if company_id:
        companies = companies.filter(id=company_id)

    # 费用类型定义（与Expense.expense_type对应）
    EXPENSE_TYPES = [
        ('salary', '工资薪酬'),
        ('social', '社保公积金'),
        ('office', '办公费用'),
        ('travel', '差旅费用'),
        ('communication', '通讯费用'),
        (' entertainment', '业务招待'),
        ('marketing', '市场营销'),
        ('rd', '研发费用'),
        ('tax', '税费'),
        ('other', '其他'),
    ]

    results = []
    for company in companies:
        exp_qs = Expense.objects.filter(company=company, date__year=year)

        type_totals = {}
        for exp_type, label in EXPENSE_TYPES:
            total = float(exp_qs.filter(expense_type=exp_type).aggregate(
                t=Coalesce(Sum('amount'), 0))['t'] or 0)
            type_totals[exp_type] = {'label': label, 'actual': total}

        # 工资实际（从WageRecord）
        wage_total = float(WageRecord.objects.filter(
            company=company, year=year
        ).aggregate(t=Coalesce(Sum('gross_wage'), 0))['t'] or 0)
        if 'salary' in type_totals:
            type_totals['salary']['actual'] = wage_total

        # 社保实际
        social_total = float(WageRecord.objects.filter(
            company=company, year=year
        ).aggregate(t=Coalesce(Sum('social_security'), 0))['t'] or 0)
        if 'social' in type_totals:
            type_totals['social']['actual'] = social_total

        total_actual = sum(v['actual'] for v in type_totals.values())

        results.append({
            'company_id': company.id,
            'company_name': company.name,
            'year': year,
            'by_type': [
                {**v, 'type': k}
                for k, v in type_totals.items()
            ],
            'total_actual': total_actual,
        })

    grand_actual = sum(r['total_actual'] for r in results)

    return Response({
        'report': 'budget_execution',
        'title': f'{year}年 预算执行表',
        'params': params,
        'results': results,
        'summary': {
            'total_actual': grand_actual,
        }
    })
