"""
财务补充报表 - P1增强
"""

import re

from rest_framework.decorators import api_view
from apps.core.permissions import require_perms
from rest_framework.response import Response

from apps.finance.models import Income, Expense
from apps.finance.reports_common import get_user_report_companies, parse_date_range, build_qs, get_internal_company_names_cached


@api_view(['GET'])
@require_perms('finance:report:read')
def customer_revenue_report(request):
    params = parse_date_range(request)
    year = params['year']
    month = params['month']
    company_id = params['company_id']
    limit = int(request.query_params.get('limit', 50))

    inc_qs = build_qs(Income, company_id, year, month)
    # 公司隔离：只查用户有权限的公司
    user_companies = get_user_report_companies(request)
    if company_id:
        user_companies = user_companies.filter(id=company_id)
    inc_qs = inc_qs.filter(company__in=user_companies)

    global_stats = {}
    internal_stats = {'total': 0.0, 'count': 0}
    for inc in inc_qs.select_related('company', 'client_ref'):
        # 内部公司转账不计入外部客户收入
        if inc.customer in get_internal_company_names_cached():
            internal_stats['total'] += float(inc.amount or 0)
            internal_stats['count'] += 1
            continue
        # CRM 标准化：优先使用关联的 CRM Client 名称
        customer_name = inc.client_ref.name if inc.client_ref_id and inc.client_ref else (inc.customer or '（未指定）')
        key = f'{inc.company.name} / {customer_name}'
        if key not in global_stats:
            global_stats[key] = {
                'company': inc.company.name,
                'customer': customer_name,
                'client_ref_id': inc.client_ref_id,
                'total': 0.0,
                'count': 0,
            }
        global_stats[key]['total'] += float(inc.amount or 0)
        global_stats[key]['count'] += 1

    ranked = sorted(global_stats.items(), key=lambda x: x[1]['total'], reverse=True)[:limit]
    results = [{'rank': r + 1, 'key': k, **v} for r, (k, v) in enumerate(ranked)]

    return Response(
        {
            'report': 'customer_revenue',
            'title': '客户收入排行',
            'params': params,
            'global_ranking': results,
            'internal_transfers': internal_stats,
            'summary': {
                'total_revenue': sum(x['total'] for x in results),
                'customer_count': len(results),
            },
        }
    )


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
    # 公司隔离：只查用户有权限的公司
    user_companies = get_user_report_companies(request)
    if company_id:
        user_companies = user_companies.filter(id=company_id)
    exp_qs = exp_qs.filter(company__in=user_companies)

    # 【P2-2 修复】从 CRM Supplier 拉取真实供应商名单（含 counterparty_type）
    try:
        from apps.crm.models import Supplier as CRMSupplier

        real_suppliers = set(CRMSupplier.objects.filter(status='active').values_list('name', flat=True))
        # 个人类型供应商（HR报销等场景）
        individual_suppliers = set(
            CRMSupplier.objects.filter(counterparty_type='individual', status='active').values_list('name', flat=True)
        )
    except Exception:
        real_suppliers = set()
        individual_suppliers = set()

    # 从 Employee 表识别人名（员工报销场景：供应商名是员工姓名）
    try:
        from apps.finance.models import Employee

        employee_names = set(Employee.objects.values_list('name', flat=True))
    except Exception:
        employee_names = set()

    enterprise_stats = {}  # 企业供应商
    individual_stats = {}  # 个人/员工供应商
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
            personal_stats['types'][exp_type] = personal_stats['types'].get(exp_type, 0.0) + amount
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
                'total': 0.0,
                'count': 0,
                'types': {},
            }
        bucket[supplier]['total'] += amount
        bucket[supplier]['count'] += 1
        bucket[supplier]['types'][exp_type] = bucket[supplier]['types'].get(exp_type, 0.0) + amount

    # 企业供应商排名
    ranked_enterprise = sorted(enterprise_stats.items(), key=lambda x: x[1]['total'], reverse=True)[:limit]

    # 个人/员工供应商单独列表（不参与企业排名）
    ranked_individual = sorted(individual_stats.items(), key=lambda x: x[1]['total'], reverse=True)

    results = [{'rank': r + 1, **v} for r, (k, v) in enumerate(ranked_enterprise)]

    return Response(
        {
            'report': 'supplier_expense',
            'title': '供应商支出报表',
            'params': params,
            'results': results,
            'individual_results': [{'rank': r + 1, **v} for r, (k, v) in enumerate(ranked_individual)],
            'personal_payments': personal_stats,
            'summary': {
                'total_expense': sum(r['total'] for r in results),
                'supplier_count': len(results),
                'individual_count': len(ranked_individual),
                'personal_count': personal_stats['count'],
            },
        }
    )


# ─── 5. 税费汇总表 ─────────────────────────────────────────────────────
