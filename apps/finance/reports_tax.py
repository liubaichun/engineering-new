"""
财务补充报表 - P1增强
"""

import re

from django.db.models import Sum
from rest_framework.decorators import api_view
from apps.core.permissions import require_perms
from rest_framework.response import Response

from apps.finance.models import Company, Expense, Invoice
from apps.finance.reports_common import get_user_report_companies, parse_date_range, agg


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

    companies = get_user_report_companies(request)
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
            exp_tax_qs = exp_tax_qs.filter(date__year=year)
            social_qs = social_qs.filter(date__year=year)
        if month:
            inv_qs = inv_qs.filter(issue_date__month=month)
            exp_tax_qs = exp_tax_qs.filter(date__month=month)
            social_qs = social_qs.filter(date__month=month)

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

        results.append(
            {
                'company_id': company.id,
                'company_name': company.name,
                'invoice_input_tax': round(invoice_input_tax, 2),
                'invoice_output_tax': round(invoice_output_tax, 2),
                'net_vat': round(net_vat, 2),  # 应交增值税（销项-进项）
                'personal_income_tax': round(personal_tax, 2),  # 代扣个税
                'corporate_income_tax': round(corporate_tax, 2),  # 企业所得税
                'vat': round(vat, 2),  # 增值税（银行实缴）
                'social_housing_total': round(social_total, 2),  # 社保公积金
                'other_tax': round(other_tax, 2),  # 其他税费
                'company_tax_total': round(company_tax_total, 2),
            }
        )
        grand_input_tax += invoice_input_tax
        grand_output_tax += invoice_output_tax
        grand_personal_tax += personal_tax
        grand_corporate_tax += corporate_tax
        grand_vat += vat
        grand_social += social_total

    grand_net_vat = grand_output_tax - grand_input_tax
    grand_company_total = grand_personal_tax + grand_corporate_tax + grand_vat + grand_social

    return Response(
        {
            'report': 'tax_summary',
            'title': f'{year}年 税费汇总表',
            'params': params,
            'results': results,
            'summary': {
                'total_invoice_input_tax': round(grand_input_tax, 2),
                'total_invoice_output_tax': round(grand_output_tax, 2),
                'total_net_vat': round(grand_net_vat, 2),  # 应交增值税
                'total_personal_income_tax': round(grand_personal_tax, 2),
                'total_corporate_income_tax': round(grand_corporate_tax, 2),
                'total_vat': round(grand_vat, 2),
                'total_social_housing': round(grand_social, 2),
                'grand_company_tax_total': round(grand_company_total, 2),
            },
        }
    )


# ─── 6. 预算执行表 ──────────────────────────────────────────────────────
