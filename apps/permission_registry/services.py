"""
权限服务层。

提供 user × company × module 权限查询的统一 API，
供 ViewSet.get_queryset() 和 DRF 权限类调用。
"""

from apps.permission_registry.models import Module, UserCompanyPermission


def get_user_companies(user):
    """
    返回用户有权限的全部公司 ID 列表。

    超管 is_superuser=True → 返回 None（不过滤，等于全公司）
    普通用户 → list[company_id]

    用法：
        company_ids = get_user_companies(request.user)
        if company_ids is None:
            queryset = Model.objects.all()
        else:
            queryset = Model.objects.filter(company_id__in=company_ids)
    """
    if user.is_superuser:
        return None  # 超管：不过滤

    return list(
        UserCompanyPermission.objects.filter(
            user=user,
            can_view=True
        )
        .values_list('company_id', flat=True)
        .distinct()
    )


def get_user_module_perm(user, company_id, module_name, action):
    """
    检查用户在特定公司特定模块的特定操作权限。

    参数：
        user         User 实例
        company_id   公司 ID
        module_name  模块代码，如 'income'
        action       权限动作：'view' | 'create' | 'edit' | 'delete' | 'approve'

    返回：
        True / False
    """
    if user.is_superuser:
        return True

    perm_field = f'can_{action}'
    if perm_field not in ['can_view', 'can_create', 'can_edit', 'can_delete', 'can_approve']:
        return False

    return UserCompanyPermission.objects.filter(
        user=user,
        company_id=company_id,
        module__name=module_name,
        **{perm_field: True}
    ).exists()


def get_active_company_id(user, request=None):
    """
    获取用户当前操作的默认公司 ID。

    优先级：
    1. request query param ?company=ID（显式指定）
    2. request data company_id（表单 body）
    3. session['active_company_id']
    4. UserCompanyPermission 中 is_primary=True 的公司
    5. UserCompanyPermission 中第一个公司

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
                # 验证用户有权限
                if UserCompanyPermission.objects.filter(
                    user=user, company_id=cid, can_view=True
                ).exists():
                    return cid
            except (ValueError, TypeError):
                pass

    # 取主公司
    primary = UserCompanyPermission.objects.filter(
        user=user,
        is_primary=True,
        can_view=True
    ).first()
    if primary:
        return primary.company_id

    # 取第一个有权限的公司
    first = UserCompanyPermission.objects.filter(
        user=user,
        can_view=True
    ).first()
    return first.company_id if first else None


def get_user_modules(user, company_id):
    """
    返回用户在某公司下有权限的全部模块列表。

    返回 list of Module 实例。
    """
    if user.is_superuser:
        return list(Module.objects.filter(is_active=True))

    perms = UserCompanyPermission.objects.filter(
        user=user,
        company_id=company_id,
    ).select_related('module').filter(module__is_active=True)

    return [p.module for p in perms if any([p.can_view, p.can_create, p.can_edit, p.can_delete, p.can_approve])]


def get_permission_matrix(user_id):
    """
    返回某用户的完整权限矩阵。

    返回结构：
    {
        'companies': [
            {
                'company_id': 1,
                'company_name': '深圳公司',
                'is_primary': True,
                'modules': {
                    'income': {'can_view': True, 'can_create': True, ...},
                    'expense': {...},
                }
            }
        ]
    }
    """
    from apps.core.models import User
    from apps.finance.models import Company

    user = User.objects.get(id=user_id)
    companies = Company.objects.all()

    matrix = []
    for company in companies:
        if user.is_superuser:
            modules = Module.objects.filter(is_active=True)
            module_perms = {}
            for m in modules:
                module_perms[m.name] = {
                    'can_view': True,
                    'can_create': True,
                    'can_edit': True,
                    'can_delete': True,
                    'can_approve': True,
                }
            matrix.append({
                'company_id': company.id,
                'company_name': company.name,
                'is_primary': False,
                'modules': module_perms,
            })
        else:
            perms = UserCompanyPermission.objects.filter(
                user=user,
                company=company,
            ).select_related('module')

            if not perms.exists():
                continue

            module_perms = {}
            has_any = False
            primary = False
            for p in perms:
                has_any = True
                if p.is_primary:
                    primary = True
                module_perms[p.module.name] = {
                    'can_view': p.can_view,
                    'can_create': p.can_create,
                    'can_edit': p.can_edit,
                    'can_delete': p.can_delete,
                    'can_approve': p.can_approve,
                }

            if has_any:
                matrix.append({
                    'company_id': company.id,
                    'company_name': company.name,
                    'is_primary': primary,
                    'modules': module_perms,
                })

    return {'companies': matrix}
