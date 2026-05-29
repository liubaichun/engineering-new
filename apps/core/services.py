from __future__ import annotations

from typing import Any, List, Optional, Tuple

# channels 通知路由所需的公司上下文服务
from apps.core.models import UserCompanyPermission


def get_active_company_id(user: Any, request: Optional[Any] = None) -> Optional[int]:
    """
    获取用户当前操作的默认公司 ID。

    优先级：
    1. request query param ?company=ID（显式指定）
    2. request data company_id（表单 body）
    3. session['current_company_id']
    4. UserCompanyPermission 中 company_id 最小的那条

    不再依赖 UserCompanyRole。

    参数：
        user: User 对象 或 DRF Request 对象（兼容两种调用方式）
        request: 可选，DRF Request 对象（用于取 query_params/data/session）

    返回：
        int | None（None 表示超管未指定，或用户无任何关联公司）
    """
    # 兼容：如果传入的是 DRF Request，取出真正的 user 对象
    if hasattr(user, 'user'):
        if request is None:
            request = user
        user = request.user

    if user.is_superuser:
        if request:
            cid = None
            if hasattr(request, 'query_params'):
                cid = request.query_params.get('company') or request.query_params.get('company_id')
            elif hasattr(request, 'data'):
                cid = request.data.get('company_id')
            if cid:
                try:
                    return int(cid)
                except (ValueError, TypeError):
                    pass
        return None  # 超管：未指定则不过滤

    if request:
        cid = None
        if hasattr(request, 'query_params'):
            cid = request.query_params.get('company') or request.query_params.get('company_id')
        elif hasattr(request, 'data'):
            cid = request.data.get('company_id')
        if cid:
            try:
                cid = int(cid)
                # 验证用户在该公司有 UCP
                if UserCompanyPermission.objects.filter(user=user, company_id=cid, is_granted=True).exists():
                    return cid
            except (ValueError, TypeError):
                pass

    # 从 session 读取
    if request and hasattr(request, 'session'):
        cid = request.session.get('current_company_id')
        if cid:
            try:
                cid = int(cid)
                if UserCompanyPermission.objects.filter(user=user, company_id=cid, is_granted=True).exists():
                    return cid
            except (ValueError, TypeError):
                pass

    # 取用户第一个有权限的公司
    # 优先级：UCP 记录数最多的公司优先（频率最高的公司），其次按 company_id 排序
    from django.db.models import Count

    company_counts = (
        UserCompanyPermission.objects.filter(user=user, is_granted=True)
        .values('company_id')
        .annotate(ucp_count=Count('id'))
        .order_by('-ucp_count', 'company_id')
    )
    if company_counts:
        return company_counts[0]['company_id']

    return None  # 用户没有任何 UCP


def get_user_companies(user: Any) -> List[Tuple[int, str]]:
    """
    获取用户有权限的所有公司列表。

    返回格式：[(company_id, company_name), ...]
    按权限记录数降序（最常用优先）、company_id 升序排序。
    """
    from apps.finance.models import Company
    from django.db.models import Count

    if user.is_superuser:
        return [(c.id, c.name) for c in Company.objects.all()]

    rows = (
        UserCompanyPermission.objects.filter(user=user, is_granted=True)
        .values('company_id', 'company__name')
        .annotate(ucp_count=Count('id'))
        .distinct()
        .order_by('-ucp_count', 'company_id')
    )
    return [(r['company_id'], r['company__name']) for r in rows]


def get_user_module_perm(user: Any, company_id: int, module_name: str, action_name: str) -> bool:
    """
    检查用户在指定公司对指定模块动作是否有权限。

    参数：
        user: User 对象
        company_id: int
        module_name: str（如 'income', 'expense'）
        action_name: str（如 'read', 'create'）

    返回：True（有权限）/ False（无权限）
    """
    if user.is_superuser:
        return True

    return UserCompanyPermission.objects.filter(
        user=user,
        company_id=company_id,
        module__name=module_name,
        action__name=action_name,
        is_granted=True,
    ).exists()
