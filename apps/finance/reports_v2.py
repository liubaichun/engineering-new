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

# 内部公司名称（同一集团内各公司互转不算外部收入）
INTERNAL_COMPANY_NAMES = {
    '深圳市绿聚能科技有限公司',
    '深圳市金易豪信息技术有限公司',
    '深圳市百川软件科技发展有限公司',
}


def agg(qs, field):
    """安全聚合，返回float，None当0处理"""
    v = qs.aggregate(t=Sum(field))['t']
    return float(v) if v is not None else 0.0




# ─── 通用筛选逻辑 ─────────────────────────────────────────────────────────
def parse_date_range(request):
    year = request.query_params.get('year', str(timezone.now().year))
    month = request.query_params.get('month')
    company_id = request.query_params.get('company')
    # 多租户隔离：非超级用户强制使用自己的公司ID
    # 超级用户（admin）company_id=NULL，视为"全公司视图"，不过滤company_id
    user = request.user
    effective_company_id = None
    if user.is_authenticated and not user.is_superuser:
        if hasattr(user, 'company') and user.company_id:
            if company_id and int(company_id) != user.company_id:
                effective_company_id = user.company_id
            else:
                effective_company_id = user.company_id
    elif company_id:
        effective_company_id = int(company_id)
    # else: superuser with no company_id → effective_company_id=None（查全部）
    return {
        'company_id': effective_company_id,
        'year': int(year) if year else None,
        'month': int(month) if month else None,
    }


def build_qs(model, company_id=None, year=None, month=None):
    qs = model.objects.all()
    if company_id: qs = qs.filter(company_id=company_id)
    # 不同模型使用不同日期字段
    date_field = 'date'
    if model.__name__ == 'Expense':
        date_field = 'expense_date'
    elif model.__name__ == 'Income':
        date_field = 'date'
    if year:  qs = qs.filter(**{f'{date_field}__year': year})
    if month: qs = qs.filter(**{f'{date_field}__month': month})
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
        # ── 取该公司所有银行账户的流水 ───────────────────────────────────────
        bs_qs = BankStatement.objects.filter(company=company).order_by('transaction_date', 'id')

        # 期初余额：取 year-01-01 之前最近一条有余额的记录
        year_start = f"{year}-01-01"
        prior_bs = bs_qs.filter(transaction_date__lt=year_start).exclude(
            balance__isnull=True
        ).order_by('transaction_date', 'id')
        begin_balance = 0.0
        if prior_bs.exists():
            begin_balance = float(prior_bs.last().balance or 0)

        monthly_data = []
        for month in range(1, 13):
            month_start = f"{year}-{month:02d}-01"
            # 下个月1日
            if month == 12:
                month_end = f"{year+1}-01-01"
            else:
                month_end = f"{year}-{month+1:02d}-01"

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

            # 月末余额：取该月最后一条有余额的记录
            end_balance = begin_balance + inc_total - exp_total
            month_end_bs = month_bs.exclude(balance__isnull=True).order_by('transaction_date', 'id')
            if month_end_bs.exists():
                end_balance = float(month_end_bs.last().balance or 0)

            # 只有有发生额才记录
            if inc_total > 0 or exp_total > 0:
                monthly_data.append({
                    'month': month,
                    'income': round(inc_total, 2),
                    'expense': round(exp_total, 2),
                    'net': round(inc_total - exp_total, 2),
                    'end_balance': round(end_balance, 2),
                })

            begin_balance = end_balance  # 下月期初 = 本月末

        year_income = sum(m['income'] for m in monthly_data)
        year_expense = sum(m['expense'] for m in monthly_data)
        rows.append({
            'company_id': company.id,
            'company_name': company.name,
            'year': year,
            'year_income': round(year_income, 2),
            'year_expense': round(year_expense, 2),
            'year_net': round(year_income - year_expense, 2),
            'monthly': monthly_data,
        })
        grand_income += year_income
        grand_expense += year_expense

    return Response({
        'report': 'cash_flow',
        'title': f'{year}年 现金流量表',
        'params': params,
        'results': rows,
        'summary': {
            'total_income': round(grand_income, 2),
            'total_expense': round(grand_expense, 2),
            'total_net': round(grand_income - grand_expense, 2),
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
                tax_amount = float(getattr(rec, 'tax_amount', 0) or 0) if hasattr(rec, 'tax_amount') else 0
                amount_with_tax = amount + tax_amount
                if bucket in buckets:
                    buckets[bucket] += amount_with_tax
                name = getattr(rec, name_field, '') or ''
                details.append({
                    'id': rec.id, 'name': str(name), 'amount': amount_with_tax,
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
        Invoice.objects.filter(type='income', status='pending'),
        'counterparty'
    )
    ap_results = build_arap(
        Invoice.objects.filter(type='expense', status='pending'),
        'counterparty'
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
    internal_stats = {'total': 0.0, 'count': 0}
    for inc in inc_qs.select_related('company'):
        # 内部公司转账不计入外部客户收入
        if inc.customer in INTERNAL_COMPANY_NAMES:
            internal_stats['total'] += float(inc.amount or 0)
            internal_stats['count'] += 1
            continue
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
        'internal_transfers': internal_stats,
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
    personal_stats = {'total': 0.0, 'count': 0, 'types': {}}
    for exp in exp_qs.select_related('company', 'project'):
        supplier = exp.supplier or ''
        # 无供应商名称 → 个人支付/内部转账，不计入供应商报表
        if not supplier:
            personal_stats['total'] += float(exp.amount or 0)
            personal_stats['count'] += 1
            exp_type = exp.expense_type or '未分类'
            personal_stats['types'][exp_type] = \
                personal_stats['types'].get(exp_type, 0.0) + float(exp.amount or 0)
            continue
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
        'personal_payments': personal_stats,
        'summary': {
            'total_expense': sum(r['total'] for r in results),
            'supplier_count': len(results),
        }
    })


# ─── 5. 税费汇总表 ─────────────────────────────────────────────────────
def _parse_tax_type(desc: str, amount: float):
    """根据税单号前缀和金额推断税费类型
    344036 = 个税（龙华区税务局第三税务所）
    625/626 = 增值税（龙华区税务局第二税务所）
    444036 = 企业所得税（龙华区税务局第四税务所），但其中amount<2000为个税代扣
    """
    if '344036' in desc:
        return 'personal_income_tax'
    vat_codes = ['625', '626']
    if any(f'{c}{y}' in desc or f'{c}1{y}' in desc or f'{c}2{y}' in desc
           for c in vat_codes for y in ['2', '3']):
        return 'vat'
    if '444036' in desc:
        # 444036里金额<2000的为个税代扣，>=2000的为企业所得税
        if abs(amount) < 2000:
            return 'personal_income_tax'
        return 'corporate_income_tax'
    # 其他税费归为其他
    return 'other'


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
    grand_input_tax = 0
    grand_output_tax = 0
    grand_personal_tax = 0
    grand_corporate_tax = 0
    grand_vat = 0
    grand_social = 0

    for company in companies:
        inv_qs = Invoice.objects.filter(company=company)
        # 银行实时缴税：从Expense.category='税款'按税种拆分
        exp_tax_qs = Expense.objects.filter(company=company, expense_category='税款')
        # 社保公积金
        social_qs = Expense.objects.filter(company=company, expense_type='social')

        if year:
            inv_qs = inv_qs.filter(issue_date__year=year)
            exp_tax_qs = exp_tax_qs.filter(expense_date__year=year)
            social_qs = social_qs.filter(expense_date__year=year)
        if month:
            inv_qs = inv_qs.filter(issue_date__month=month)
            exp_tax_qs = exp_tax_qs.filter(expense_date__month=month)
            social_qs = social_qs.filter(expense_date__month=month)

        # 发票税额：销项（开给客户）和进项（收供应商）
        invoice_input_tax = agg(inv_qs.filter(type='expense'), 'tax_amount')
        invoice_output_tax = agg(inv_qs.filter(type='income'), 'tax_amount')

        # 银行缴税：按税单号前缀拆分为三类
        personal_tax = 0.0
        corporate_tax = 0.0
        vat = 0.0
        other_tax = 0.0
        for row in exp_tax_qs.only('amount', 'description'):
            t = _parse_tax_type(row.description, float(row.amount))
            if t == 'personal_income_tax':
                personal_tax += float(row.amount)
            elif t == 'corporate_income_tax':
                corporate_tax += float(row.amount)
            elif t == 'vat':
                vat += float(row.amount)
            else:
                other_tax += float(row.amount)

        # 社保公积金
        social_total = agg(social_qs, 'amount')

        # 合计
        company_tax_total = personal_tax + corporate_tax + vat + social_total

        results.append({
            'company_id': company.id,
            'company_name': company.name,
            'invoice_input_tax': round(invoice_input_tax, 2),
            'invoice_output_tax': round(invoice_output_tax, 2),
            'personal_income_tax': round(personal_tax, 2),        # 代扣个税
            'corporate_income_tax': round(corporate_tax, 2),       # 企业所得税
            'vat': round(vat, 2),                                  # 增值税
            'social_housing_total': round(social_total, 2),        # 社保公积金
            'other_tax': round(other_tax, 2),                       # 其他税费
            'company_tax_total': round(company_tax_total, 2),
        })
        grand_input_tax += invoice_input_tax
        grand_output_tax += invoice_output_tax
        grand_personal_tax += personal_tax
        grand_corporate_tax += corporate_tax
        grand_vat += vat
        grand_social += social_total

    grand_company_total = grand_personal_tax + grand_corporate_tax + grand_vat + grand_social

    return Response({
        'report': 'tax_summary',
        'title': f'{year}年 税费汇总表',
        'params': params,
        'results': results,
        'summary': {
            'total_invoice_input_tax': round(grand_input_tax, 2),
            'total_invoice_output_tax': round(grand_output_tax, 2),
            'total_personal_income_tax': round(grand_personal_tax, 2),
            'total_corporate_income_tax': round(grand_corporate_tax, 2),
            'total_vat': round(grand_vat, 2),
            'total_social_housing': round(grand_social, 2),
            'grand_company_tax_total': round(grand_company_total, 2),
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
                total = agg(WageRecord.objects.filter(company=company, year=year), 'gross_salary')
            elif exp_type == 'social':
                total = agg(WageRecord.objects.filter(company=company, year=year), 'social_insurance')
            else:
                total = agg(Expense.objects.filter(
                    company=company, expense_date__year=year, expense_type=exp_type), 'amount')
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
