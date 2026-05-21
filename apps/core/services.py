# channels 通知路由所需的公司上下文服务
from apps.core.models import UserCompanyRole


def get_active_company_id(user, request=None):
    """
    获取用户当前操作的默认公司 ID。

    优先级：
    1. request query param ?company=ID（显式指定）
    2. request data company_id（表单 body）
    3. session['active_company_id']
    4. UserCompanyRole 中 is_primary=True 的公司
    5. UserCompanyRole 中第一个公司

    返回：
        int | None（None 表示超管未指定，或用户无任何关联公司）
    """
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
                # 验证用户确实关联了这个公司
                if UserCompanyRole.objects.filter(user=user, company_id=cid).exists():
                    return cid
            except (ValueError, TypeError):
                pass

    # 取主公司
    primary = UserCompanyRole.objects.filter(
        user=user,
        is_primary=True
    ).first()
    if primary:
        return primary.company_id

    # 取第一个关联的公司
    first = UserCompanyRole.objects.filter(user=user).first()
    return first.company_id if first else None
