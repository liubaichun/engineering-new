"""
财务补充报表 - P1增强
"""
from datetime import datetime, timedelta
from decimal import Decimal
import re

from django.db.models import Sum, Count, Q, F
from django.utils import timezone
from rest_framework.decorators import api_view
from apps.core.permissions import require_perms
from rest_framework.response import Response

from apps.finance.models import Company, Income, Expense, Invoice, WageRecord
from apps.finance.models_bank import BankStatement
from apps.crm.models import Client, Supplier

# 内部公司名称（同一集团内各公司互转不算外部收入）
# ── 【P2-1 修复】从 Company 表动态读取（排除所有公司名，避免硬编码）────
def get_internal_company_names():
    """从 Company 表获取所有公司名称，用于排除内部转账收入"""
    return set(Company.objects.values_list('name', flat=True))

INTERNAL_COMPANY_NAMES = get_internal_company_names()


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


# ─── 1. 银行余额变动表 ───────────────────────────────────────────────────────
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
        year_start = f"{year}-01-01"
        prior_bs = bs_qs.filter(transaction_date__lt=year_start).exclude(
            balance__isnull=True
        ).order_by('transaction_date', 'id')
        begin_balance = 0.0
        if prior_bs.exists():
            begin_balance = float(prior_bs.last().balance or 0)

        monthly_data = []
        for month in months_to_process:
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
        'title': f'{year}年 银行余额变动表',
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
@require_perms('finance:report:read')
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
                due = getattr(rec, 'due_date', None) or getattr(rec, 'issue_date', None) or getattr(rec, 'date', None) or today
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

    ar_qs = Invoice.objects.filter(type='income', status='pending')
    ap_qs = Invoice.objects.filter(type='expense', status='pending')
    # 按时间范围过滤（params 从 parse_date_range 解析得到）
    if params['year']:
        ar_qs = ar_qs.filter(issue_date__year=params['year'])
        ap_qs = ap_qs.filter(issue_date__year=params['year'])
    if params['month']:
        ar_qs = ar_qs.filter(issue_date__month=params['month'])
        ap_qs = ap_qs.filter(issue_date__month=params['month'])

    ar_results = build_arap(ar_qs, 'counterparty')
    ap_results = build_arap(ap_qs, 'counterparty')

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
@require_perms('finance:report:read')
def customer_revenue_report(request):
    params = parse_date_range(request)
    year = params['year']
    month = params['month']
    company_id = params['company_id']
    limit = int(request.query_params.get('limit', 50))

    inc_qs = build_qs(Income, company_id, year, month)

    global_stats = {}
    internal_stats = {'total': 0.0, 'count': 0}
    for inc in inc_qs.select_related('company', 'client_ref'):
        # 内部公司转账不计入外部客户收入
        if inc.customer in INTERNAL_COMPANY_NAMES:
            internal_stats['total'] += float(inc.amount or 0)
            internal_stats['count'] += 1
            continue
        # CRM 标准化：优先使用关联的 CRM Client 名称
        customer_name = inc.client_ref.name if inc.client_ref_id and inc.client_ref else (inc.customer or '（未指定）')
        key = f"{inc.company.name} / {customer_name}"
        if key not in global_stats:
            global_stats[key] = {
                'company': inc.company.name,
                'customer': customer_name,
                'client_ref_id': inc.client_ref_id,
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
@require_perms('finance:report:read')
def supplier_expense_report(request):
    """供应商支出报表
    【P2-2 修复】识别人名类供应商（刘柏春等员工姓名），自动归入"个人/内部"分组，
    不再和企业供应商混合排名。同时对真实供应商做 counterparty_type 标注。
    """
    params = parse_date_range(request)
    year = params['year']
    month = params['month']
    company_id = params['company_id']
    limit = int(request.query_params.get('limit', 50))

    exp_qs = build_qs(Expense, company_id, year, month)

    # 【P2-2 修复】从 CRM Supplier 拉取真实供应商名单（含 counterparty_type）
    try:
        from apps.crm.models import Supplier as CRMSupplier
        real_suppliers = set(
            CRMSupplier.objects.filter(status='active')
            .values_list('name', flat=True)
        )
        # 个人类型供应商（HR报销等场景）
        individual_suppliers = set(
            CRMSupplier.objects.filter(counterparty_type='individual', status='active')
            .values_list('name', flat=True)
        )
    except Exception:
        real_suppliers = set()
        individual_suppliers = set()

    # 从 Employee 表识别人名（员工报销场景：供应商名是员工姓名）
    try:
        from apps.finance.models import Employee
        employee_names = set(
            Employee.objects.values_list('name', flat=True)
        )
    except Exception:
        employee_names = set()

    enterprise_stats = {}   # 企业供应商
    individual_stats = {}   # 个人/员工供应商
    personal_stats = {'total': 0.0, 'count': 0, 'types': {}}  # 无供应商名（内部转账等）

    for exp in exp_qs.select_related('company', 'project', 'supplier_ref'):
        # CRM 标准化：优先使用关联的 CRM Supplier 名称
        supplier = exp.supplier_ref.name if exp.supplier_ref_id and exp.supplier_ref else (exp.supplier or '').strip()
        supplier_ref_id = exp.supplier_ref_id
        amount = float(exp.amount or 0)
        exp_type = exp.expense_type or '未分类'

        # 无供应商名 → 个人/内部转账
        if not supplier:
            personal_stats['total'] += amount
            personal_stats['count'] += 1
            personal_stats['types'][exp_type] = \
                personal_stats['types'].get(exp_type, 0.0) + amount
            continue

        # 识别人名（员工姓名匹配）或 counterparty_type=individual
        is_individual = (
            supplier in employee_names
            or supplier in individual_suppliers
            or bool(re.match(r'^[\u4e00-\u9fa5]{2,4}$', supplier))  # 纯中文姓名：2-4个汉字
        )

        bucket = individual_stats if is_individual else enterprise_stats
        if supplier not in bucket:
            bucket[supplier] = {
                'company': exp.company.name,
                'supplier': supplier,
                'supplier_ref_id': supplier_ref_id,
                'is_individual': is_individual,
                'total': 0.0, 'count': 0,
                'types': {},
            }
        bucket[supplier]['total'] += amount
        bucket[supplier]['count'] += 1
        bucket[supplier]['types'][exp_type] = \
            bucket[supplier]['types'].get(exp_type, 0.0) + amount

    # 企业供应商排名
    ranked_enterprise = sorted(
        enterprise_stats.items(), key=lambda x: x[1]['total'], reverse=True
    )[:limit]

    # 个人/员工供应商单独列表（不参与企业排名）
    ranked_individual = sorted(
        individual_stats.items(), key=lambda x: x[1]['total'], reverse=True
    )

    results = [
        {'rank': r + 1, **v}
        for r, (k, v) in enumerate(ranked_enterprise)
    ]

    return Response({
        'report': 'supplier_expense',
        'title': '供应商支出报表',
        'params': params,
        'results': results,
        'individual_results': [
            {'rank': r + 1, **v}
            for r, (k, v) in enumerate(ranked_individual)
        ],
        'personal_payments': personal_stats,
        'summary': {
            'total_expense': sum(r['total'] for r in results),
            'supplier_count': len(results),
            'individual_count': len(ranked_individual),
            'personal_count': personal_stats['count'],
        }
    })


# ─── 5. 税费汇总表 ─────────────────────────────────────────────────────
def _parse_tax_type(desc: str, amount: float):
    """根据税单号前缀和金额推断税费类型
    344036 = 个税（龙华区税务局第三税务所）
    625/626 = 增值税（龙华区税务局第二税务所）
    444036 = 企业所得税（龙华区税务局第四税务所），但其中amount<2000为个税代扣
    ── 【P3-1 修复】────────────────────────────────────────────
    原逻辑：vat 判断用 f'{c}{y}'/'{c}1{y}'/'{c}2{y}' 组合，对含'6252'/'6262'等前缀
    的税单号会误判（如626031211被错误匹配）。修复：严格按税单号结构匹配，
    增值税税单号固定为9位数字，'625'开头且第5位为['0','1','2']，'626'同理。
    ──────────────────────────────────────────────────────────────────
    """
    if '344036' in desc:
        return 'personal_income_tax'
    # 增值税：税单号在"税单号:"之后，以前缀 625 或 626 开头
    # ── 【P3-1 修复】────────────────────────────────────────────
    # 原 r'625\d+|626\d+' 会误匹配描述中任意位置的 626（如444036260里的"626"）
    # 改为取"税单号:"后面的实际税单号，再判断其前缀
    import re
    tax_num_match = re.search(r'税单号[：:]([0-9]+)', desc)
    if tax_num_match:
        tax_num = tax_num_match.group(1)
        if tax_num.startswith('625') or tax_num.startswith('626'):
            return 'vat'
    if '444036' in desc:
        # 444036里金额<2000的为个税代扣，>=2000的为企业所得税
        if abs(amount) < 2000:
            return 'personal_income_tax'
        return 'corporate_income_tax'
    # 其他税费归为其他
    return 'other'


@api_view(['GET'])
@require_perms('finance:report:read')
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

        # ── 【P1-1 修复】───────────────────────────────────────────────
        # social_qs = Expense.objects.filter(company=company, expense_type='social')
        # → expense_type='social' 在银行流水中不存在（永远是0），社保数据全在 WageRecord
        # ─────────────────────────────────────────────────────────────────
        # 银行缴税：按税单号前缀拆分为三类（排除含"手续费"的记录——实为银行代发手续费非税款）
        personal_tax = 0.0
        corporate_tax = 0.0
        vat = 0.0
        other_tax = 0.0
        for row in exp_tax_qs.only('amount', 'description'):
            # 排除摘要含"手续费"的行（这是银行收的代发工资/代发款手续费，不是税款）
            if '手续费' in row.description:
                continue
            t = _parse_tax_type(row.description, float(row.amount))
            if t == 'personal_income_tax':
                personal_tax += float(row.amount)
            elif t == 'corporate_income_tax':
                corporate_tax += float(row.amount)
            elif t == 'vat':
                vat += float(row.amount)
            else:
                other_tax += float(row.amount)

        # 社保公积金：统一从 SocialRecord 读取公司缴部分（不再用反推公式）
        # 【P0-3 修复】直接查 SocialRecord.total_company，费率配置差异由导入数据覆盖
        from apps.finance.models import SocialRecord
        sr_q = SocialRecord.objects.filter(company=company)
        if year:
            sr_q = sr_q.filter(year_month__startswith=str(year))
        social_total = float(sr_q.aggregate(total=Sum('total_company'))['total'] or 0)

        # 合计
        company_tax_total = personal_tax + corporate_tax + vat + social_total

        # 应交增值税 = 销项税 - 进项税
        # 【P1-1 修复】区分发票层面的应交增值税（不考虑留抵/减免等复杂情况）
        net_vat = invoice_output_tax - invoice_input_tax

        results.append({
            'company_id': company.id,
            'company_name': company.name,
            'invoice_input_tax': round(invoice_input_tax, 2),
            'invoice_output_tax': round(invoice_output_tax, 2),
            'net_vat': round(net_vat, 2),                            # 应交增值税（销项-进项）
            'personal_income_tax': round(personal_tax, 2),        # 代扣个税
            'corporate_income_tax': round(corporate_tax, 2),       # 企业所得税
            'vat': round(vat, 2),                                  # 增值税（银行实缴）
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

    grand_net_vat = grand_output_tax - grand_input_tax
    grand_company_total = grand_personal_tax + grand_corporate_tax + grand_vat + grand_social

    return Response({
        'report': 'tax_summary',
        'title': f'{year}年 税费汇总表',
        'params': params,
        'results': results,
        'summary': {
            'total_invoice_input_tax': round(grand_input_tax, 2),
            'total_invoice_output_tax': round(grand_output_tax, 2),
            'total_net_vat': round(grand_net_vat, 2),                    # 应交增值税
            'total_personal_income_tax': round(grand_personal_tax, 2),
            'total_corporate_income_tax': round(grand_corporate_tax, 2),
            'total_vat': round(grand_vat, 2),
            'total_social_housing': round(grand_social, 2),
            'grand_company_tax_total': round(grand_company_total, 2),
        }
    })


# ─── 6. 预算执行表 ──────────────────────────────────────────────────────
@api_view(['GET'])
@require_perms('finance:report:read')
def budget_execution_report(request):
    params = parse_date_range(request)
    year = params['year'] or timezone.now().year
    company_id = params['company_id']

    from apps.finance.models import Budget as BudgetModel

    # ─────────────────────────────────────────────────────────────────────────────
    # 【P0-1 修复】expense_type 已废弃，改用 expense_category 过滤
    # bank_import_views.py confirm_bank_import() 中所有支出均写入 expense_type=交易类型字符串
    # 而非 CHOICES 枚举值，导致 expense_type 筛选永远匹配不到，budget_execution 全0
    #
    # 修复策略：
    #   salary / social → 走 WageRecord（已有正确逻辑）
    #   其他类型       → 改为 expense_category__icontains 关键词匹配
    # ─────────────────────────────────────────────────────────────────────────────
    EXPENSE_TYPES = [
        ('salary',        '工资薪酬',    ''),
        ('social',        '社保公积金',  ''),
        ('office',        '办公费用',    '办公'),
        ('travel',        '差旅费用',    '差旅'),
        ('communication', '通讯费用',    '通信'),
        ('entertainment', '业务招待',    '招待'),
        ('marketing',     '市场营销',    '营销'),
        ('rd',            '研发费用',    '研发'),
        ('tax',           '税费',        '税款'),   # 税费走 expense_category='税款'
        ('other',         '其他',        ''),       # 无匹配关键词 → 当作无数据（代发/转账类不归入预算科目）
    ]

    companies = Company.objects.all()
    if company_id:
        companies = companies.filter(id=company_id)

    results = []
    grand_actual = 0
    grand_budget = 0

    for company in companies:
        type_totals = []
        for exp_type, label, cat_kw in EXPENSE_TYPES:
            if exp_type == 'salary':
                total = agg(WageRecord.objects.filter(company=company, year=year), 'gross_salary')
            elif exp_type == 'social':
                # 公司社保成本：统一从 SocialRecord 读取（不再用反推公式）
                # 【P0-3 修复】直接查 SocialRecord.total_company
                from apps.finance.models import SocialRecord
                total = float(
                    SocialRecord.objects.filter(company=company, year_month__startswith=str(year))
                    .aggregate(t=Sum('total_company'))['t'] or 0
                )
            elif cat_kw:
                # 【P0-1 核心修复】改用 expense_category 关键词匹配（icontains）
                total = agg(Expense.objects.filter(
                    company=company, expense_date__year=year,
                    expense_category__icontains=cat_kw), 'amount')
            else:
                total = 0.0

            # 【P2-3 修复】查预算数
            budget = float(
                BudgetModel.objects.filter(
                    company=company, year=year, expense_type=exp_type, month__isnull=True
                ).aggregate(t=Sum('budget_amount'))['t'] or 0
            )
            exec_rate = round((total / budget * 100), 1) if budget > 0 else None

            type_totals.append({
                'type': exp_type, 'label': label,
                'actual': total, 'budget': budget,
                'execution_rate': exec_rate,
            })

        total_actual = sum(t['actual'] for t in type_totals)
        total_budget = sum(t['budget'] for t in type_totals)
        results.append({
            'company_id': company.id,
            'company_name': company.name,
            'year': year,
            'by_type': type_totals,
            'total_actual': total_actual,
            'total_budget': total_budget,
            'total_execution_rate': round((total_actual / total_budget * 100), 1) if total_budget > 0 else None,
        })
        grand_actual += total_actual
        grand_budget += total_budget

    return Response({
        'report': 'budget_execution',
        'title': f'{year}年 预算执行表',
        'params': params,
        'results': results,
        'summary': {
            'total_actual': grand_actual,
            'total_budget': grand_budget,
            'total_execution_rate': round((grand_actual / grand_budget * 100), 1) if grand_budget > 0 else None,
        }
    })


# ─── 6. 发票多维度汇总 ──────────────────────────────────────────────────
@api_view(['GET'])
@require_perms('finance:report:read')
def invoice_dimension_report(request):
    """发票多维度汇总
    按对方公司/发票类型/税率三个维度交叉汇总
    """
    from django.db.models import Sum, Count

    year = request.query_params.get('year')
    company_id = request.query_params.get('company')
    invoice_type = request.query_params.get('type')  # income / expense

    qs = Invoice.objects.all()
    if year:
        qs = qs.filter(issue_date__year=year)
    if invoice_type:
        qs = qs.filter(type=invoice_type)
    if company_id:
        qs = qs.filter(company_id=company_id)

    # 排除作废发票
    qs = qs.exclude(status='cancelled')

    # ── 维度1: 按对方公司汇总 ──────────────────────────────────────────────
    by_counterparty = list(
        qs.values('counterparty')
        .annotate(
            count=Count('id'),
            total_amount=Sum('amount'),
            total_tax=Sum('tax_amount'),
        )
        .order_by('-total_amount')
    )
    for item in by_counterparty:
        item['total_amount'] = float(item['total_amount'] or 0)
        item['total_tax'] = float(item['total_tax'] or 0)
        item['net_amount'] = round(item['total_amount'] + item['total_tax'], 2)
        if not item['counterparty']:
            item['counterparty'] = '（未指定）'

    # ── 维度2: 按发票类型汇总（专票/普票）───────────────────────────────────
    by_invoice_type = list(
        qs.values('invoice_type')
        .annotate(
            count=Count('id'),
            total_amount=Sum('amount'),
            total_tax=Sum('tax_amount'),
        )
        .order_by('-total_amount')
    )
    type_label = {'special': '增值税专用发票', 'normal': '普通发票'}
    for item in by_invoice_type:
        item['invoice_type_display'] = type_label.get(item['invoice_type'], item['invoice_type'])
        item['total_amount'] = float(item['total_amount'] or 0)
        item['total_tax'] = float(item['total_tax'] or 0)
        item['net_amount'] = round(item['total_amount'] + item['total_tax'], 2)

    # ── 维度3: 按税率汇总 ──────────────────────────────────────────────────
    by_tax_rate = list(
        qs.values('tax_rate')
        .annotate(
            count=Count('id'),
            total_amount=Sum('amount'),
            total_tax=Sum('tax_amount'),
        )
        .order_by('-total_amount')
    )
    for item in by_tax_rate:
        item['total_amount'] = float(item['total_amount'] or 0)
        item['total_tax'] = float(item['total_tax'] or 0)
        item['net_amount'] = round(item['total_amount'] + item['total_tax'], 2)

    # ── 汇总 ──────────────────────────────────────────────────────────────
    totals = qs.aggregate(
        count=Count('id'),
        total_amount=Sum('amount'),
        total_tax=Sum('tax_amount'),
    )
    total_amount = float(totals['total_amount'] or 0)
    total_tax = float(totals['total_tax'] or 0)

    return Response({
        'report': 'invoice_dimension',
        'title': f'{year or "全部"}年 发票多维度汇总',
        'params': {
            'year': int(year) if year else None,
            'company_id': int(company_id) if company_id else None,
            'type': invoice_type,
        },
        'summary': {
            'count': totals['count'],
            'total_amount': total_amount,
            'total_tax': total_tax,
            'net_amount': round(total_amount + total_tax, 2),
        },
        'by_counterparty': by_counterparty[:20],  # top 20
        'by_invoice_type': by_invoice_type,
        'by_tax_rate': by_tax_rate,
    })


# ═══════════════════════════════════════════════════════════════════
# P3 会计专业化报表
# ═══════════════════════════════════════════════════════════════════

@api_view(['GET'])
@require_perms('finance:report:read')
def income_statement_report(request):
    """利润表 — P3 新增

    基于科目余额表计算层级利润表
    API: GET /api/finance/reports/p3/income-statement/?company=X&year=2026
    """
    from .classification_rules import compute_trial_balance, get_internal_company_names

    params = parse_date_range(request)
    year = params['year'] or timezone.now().year
    company_id = params['company_id']

    # 如果不指定公司，汇总所有公司
    if not company_id:
        companies = Company.objects.filter(status='active')
    else:
        companies = Company.objects.filter(id=company_id, status='active')

    # 逐公司计算
    company_results = []
    totals = {
        'revenue': 0.0, 'revenue_main': 0.0, 'revenue_other': 0.0,
        'revenue_non_op': 0.0,
        'cost': 0.0,
        'tax_surcharge': 0.0,
        'admin_expense': 0.0,
        'wage_expense': 0.0, 'social_expense': 0.0,
        'office_expense': 0.0, 'travel_expense': 0.0,
        'entertainment_expense': 0.0, 'comm_expense': 0.0,
        'marketing_expense': 0.0, 'rd_expense': 0.0,
        'tax_expense': 0.0, 'other_expense': 0.0,
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
        admin_exp = wage_exp + social_exp + office_exp + travel_exp + ent_exp + comm_exp + mkt_exp + rd_exp + tax_exp + other_exp

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

    return Response({
        'report': 'income_statement',
        'title': f'{year}年 利润表（会计科目版）',
        'params': {'year': year, 'company_id': company_id},
        'summary': totals_row,
        'details': company_results,
    })


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
        companies = Company.objects.filter(status='active')
    else:
        companies = Company.objects.filter(id=company_id, status='active')

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

    return Response({
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
    })
