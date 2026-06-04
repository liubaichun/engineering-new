"""
财务补充报表 - P1增强
"""

from django.db.models import Sum
from django.utils import timezone

from apps.finance.models import Company


# 内部公司名称（同一集团内各公司互转不算外部收入）
# ── 【P2-1 修复】从 Company 表动态读取（排除所有公司名，避免硬编码）────
def get_internal_company_names():
    """从 Company 表获取所有公司名称，用于排除内部转账收入"""
    return set(Company.objects.values_list('name', flat=True))


def get_internal_company_names_cached():
    # 惰性加载，避免模块加载时查数据库（空库时无法migrate）
    if not hasattr(get_internal_company_names_cached, '_cache'):
        get_internal_company_names_cached._cache = get_internal_company_names()
    return get_internal_company_names_cached._cache


def get_user_report_companies(request):
    """
    获取当前用户有 report 模块读取权限的公司列表。
    超级用户返回所有公司，普通用户返回有 UMP report:read 权限的公司。
    """
    from apps.core.permissions import get_module_companies

    user = request.user
    if user.is_superuser:
        return Company.objects.filter(status='active')
    company_ids = get_module_companies(user, 'report', 'read')
    if not company_ids:
        return Company.objects.none()
    return Company.objects.filter(id__in=company_ids, status='active')


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
    if company_id:
        qs = qs.filter(company_id=company_id)
    # 不同模型使用不同日期字段
    date_field = 'date'
    if model.__name__ == 'Expense':
        date_field = 'date'
    elif model.__name__ == 'Income':
        date_field = 'date'
    if year:
        qs = qs.filter(**{f'{date_field}__year': year})
    if month:
        qs = qs.filter(**{f'{date_field}__month': month})
    return qs
