"""
财务补充报表 - P1增强
"""

from django.db.models import Sum
from django.utils import timezone
from rest_framework.decorators import api_view
from apps.core.permissions import require_perms
from rest_framework.response import Response

from apps.finance.models import Expense, WageRecord
from apps.finance.reports_common import get_user_report_companies, parse_date_range, agg


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
        ('salary', '工资薪酬', ''),
        ('social', '社保公积金', ''),
        ('office', '办公费用', '办公'),
        ('travel', '差旅费用', '差旅'),
        ('communication', '通讯费用', '通信'),
        ('entertainment', '业务招待', '招待'),
        ('marketing', '市场营销', '营销'),
        ('rd', '研发费用', '研发'),
        ('tax', '税费', '税款'),  # 税费走 expense_category='税款'
        ('other', '其他', ''),  # 无匹配关键词 → 当作无数据（代发/转账类不归入预算科目）
    ]

    companies = get_user_report_companies(request)
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
                    SocialRecord.objects.filter(company=company, year_month__startswith=str(year)).aggregate(
                        t=Sum('total_company')
                    )['t']
                    or 0
                )
            elif cat_kw:
                # 【P0-1 核心修复】改用 expense_category 关键词匹配（icontains）
                total = agg(
                    Expense.objects.filter(company=company, date__year=year, expense_category__icontains=cat_kw),
                    'amount',
                )
            else:
                total = 0.0

            # 【P2-3 修复】查预算数
            budget = float(
                BudgetModel.objects.filter(
                    company=company, year=year, expense_type=exp_type, month__isnull=True
                ).aggregate(t=Sum('budget_amount'))['t']
                or 0
            )
            exec_rate = round((total / budget * 100), 1) if budget > 0 else None

            type_totals.append(
                {
                    'type': exp_type,
                    'label': label,
                    'actual': total,
                    'budget': budget,
                    'execution_rate': exec_rate,
                }
            )

        total_actual = sum(t['actual'] for t in type_totals)
        total_budget = sum(t['budget'] for t in type_totals)
        results.append(
            {
                'company_id': company.id,
                'company_name': company.name,
                'year': year,
                'by_type': type_totals,
                'total_actual': total_actual,
                'total_budget': total_budget,
                'total_execution_rate': round((total_actual / total_budget * 100), 1) if total_budget > 0 else None,
            }
        )
        grand_actual += total_actual
        grand_budget += total_budget

    return Response(
        {
            'report': 'budget_execution',
            'title': f'{year}年 预算执行表',
            'params': params,
            'results': results,
            'summary': {
                'total_actual': grand_actual,
                'total_budget': grand_budget,
                'total_execution_rate': round((grand_actual / grand_budget * 100), 1) if grand_budget > 0 else None,
            },
        }
    )


# ─── 6. 发票多维度汇总 ──────────────────────────────────────────────────
