"""
权限上下文处理器
每个请求自动注入 user_menu_codes（用户有权限的菜单code列表）
用于 base.html 中 {% if 'finance:wage:read' in user_menu_codes %} 条件渲染菜单项

menu_codes 格式：Permission.code 格式，如 'finance:wage:read'
来源：UserCompanyPermission → ModuleAction.perm_codes（由 M1 迁移填充）
"""
from .models import UserCompanyPermission


def menu_permissions(request):
    """注入用户有权限的菜单code列表"""
    menu_codes = []

    if request.user.is_authenticated:
        if request.user.is_superuser:
            # 超级管理员拥有所有 ModuleAction.perm_codes（非空）
            from .models import ModuleAction
            qs = ModuleAction.objects.exclude(perm_codes=[]).exclude(perm_codes__isnull=True)
            menu_codes = []
            for ma in qs:
                for code in (ma.perm_codes or []):
                    if code:
                        menu_codes.append(code)
        else:
            # 普通用户：从 UCP 记录重建菜单 code
            # 查该用户所有 UCP，取 (module, action) 对应的 perm_codes
            ucp_qs = UserCompanyPermission.objects.filter(
                user=request.user,
                is_granted=True
            ).select_related('module', 'action')

            # 按 (module, action) 分组，取出 perm_codes
            seen_codes = set()
            for ucp in ucp_qs:
                for code in (ucp.action.perm_codes or []):
                    if code and code not in seen_codes:
                        seen_codes.add(code)
                        menu_codes.append(code)

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

    return {
        'user_menu_codes': menu_codes,
        'user_has_finance_perm': has_finance_perm,
        'user_has_approval_perm': has_approval_perm,
    }
