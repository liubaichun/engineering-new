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
@require_perms('finance:report:read')
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

    for exp in exp_qs.select_related('company', 'project'):
        supplier = (exp.supplier or '').strip()
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
            or len(supplier) <= 4  # 单姓名的简单判断
        )

        bucket = individual_stats if is_individual else enterprise_stats
        if supplier not in bucket:
            bucket[supplier] = {
                'company': exp.company.name,
                'supplier': supplier,
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

        # 社保公积金：走 WageRecord 反推（不走 Expense，因为 expense_type='social' 全为0）
        # ── 【P1-1 修复】───────────────────────────────────────────────
        _EMP_SI_RATE = 10.3
        _COM_SI_RATE = 23.0
        social_wr_q = WageRecord.objects.filter(company=company)
        if year:
            social_wr_q = social_wr_q.filter(year=year)
        if month:
            social_wr_q = social_wr_q.filter(month=month)
        social_total = sum(
            (float(wr.social_insurance) / _EMP_SI_RATE * 100) * (_COM_SI_RATE / 100)
            for wr in social_wr_q if wr.social_insurance > 0
        )

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
@require_perms('finance:report:read')
def budget_execution_report(request):
    params = parse_date_range(request)
    year = params['year'] or timezone.now().year
    company_id = params['company_id']

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

    # 深圳2026社保费率常量（写死，不从CompanySocialConfig读取）
    _EMP_SI_RATE = 10.3   # 个人：养老8% + 医疗2% + 失业0.3%
    _COM_SI_RATE = 23.0   # 公司：养老16% + 医疗6% + 失业0.6% + 工伤0.4%

    results = []
    grand_actual = 0

    for company in companies:
        type_totals = []
        for exp_type, label, cat_kw in EXPENSE_TYPES:
            if exp_type == 'salary':
                total = agg(WageRecord.objects.filter(company=company, year=year), 'gross_salary')
            elif exp_type == 'social':
                # 公司社保成本：逐人从个人扣款反推基数，再乘公司费率23%
                wr_q = WageRecord.objects.filter(company=company, year=year)
                total = sum(
                    (float(wr.social_insurance) / _EMP_SI_RATE * 100) * (_COM_SI_RATE / 100)
                    for wr in wr_q
                    if wr.social_insurance > 0
                )
            elif cat_kw:
                # 【P0-1 核心修复】改用 expense_category 关键词匹配（icontains）
                total = agg(Expense.objects.filter(
                    company=company, expense_date__year=year,
                    expense_category__icontains=cat_kw), 'amount')
            else:
                # 无关键词的类型（salary/social 在上面已处理；other 不应计入预算科目）
                total = 0.0
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
