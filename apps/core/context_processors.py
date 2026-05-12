"""
权限上下文处理器
每个请求自动注入 user_menu_codes（用户有权限的菜单code列表）
用于 base.html 中 {% if 'menu_code' in user_menu_codes %} 条件渲染菜单项

Permission.code 字段格式: 'app/model/action' 如 'finance/invoice/view'
其中 app 部分作为菜单分类，model.action 作为操作码
"""
from .models import Permission, RolePermission, UserRole


def menu_permissions(request):
    """注入用户有权限的菜单code列表"""
    menu_codes = []

    if request.user.is_authenticated:
        if request.user.is_superuser:
            # 超级管理员拥有所有非空code的权限
            menu_codes = list(
                Permission.objects.exclude(code='').values_list('code', flat=True).distinct()
            )
        else:
            # 普通用户：根据角色聚合权限
            user_roles = UserRole.objects.filter(user=request.user)
            if user_roles.exists():
                role_ids = list(user_roles.values_list('role_id', flat=True))
                # 找到这些角色关联的所有permission中非空的code
                perm_ids = list(
                    RolePermission.objects.filter(role_id__in=role_ids)
                    .values_list('permission_id', flat=True)
                    .distinct()
                )
                menu_codes = list(
                    Permission.objects.filter(id__in=perm_ids, is_active=True)
                    .exclude(code='')
                    .values_list('code', flat=True)
                    .distinct()
                )

    # 判断用户是否有任意财务相关权限（用于侧边栏"财务"分组显示控制）
    has_finance_perm = any(
        code.startswith('finance:')
        for code in menu_codes
    ) if menu_codes else False

    # 判断用户是否有任意审批相关权限（用于侧边栏"审批"分组显示控制）
    has_approval_perm = any(
        code.startswith('approval:')
        for code in menu_codes
    ) if menu_codes else False

    return {'user_menu_codes': menu_codes, 'user_has_finance_perm': has_finance_perm, 'user_has_approval_perm': has_approval_perm}
