"""
权限上下文处理器
每个请求自动注入 user_menu_codes（用户有权限的菜单code列表）
用于 base.html 中 {% if 'finance:wage:read' in user_menu_codes %} 条件渲染菜单项

code 格式：category:resource:action（如 finance:wage:read）
来源：UserModulePermission（位掩码）→ 遍历所有 bit 生成
"""
from .models import UserModulePermission, ACTION_BITS


def menu_permissions(request):
    """注入用户有权限的菜单code列表"""
    menu_codes = []

    if request.user.is_authenticated:
        if request.user.is_superuser:
            # 超级管理员拥有所有模块的所有 action code
            from .models import Module, ModuleAction
            for module in Module.objects.filter(is_active=True):
                for action in ModuleAction.objects.filter(module=module):
                    menu_codes.append(f'{module.category}:{module.name}:{action.name}')
        else:
            # 普通用户：从 UMP 位掩码生成
            # 获取当前公司上下文
            company_id = request.session.get('current_company_id')
            if company_id:
                seen = set()
                for perm in UserModulePermission.objects.filter(
                    user=request.user, company_id=company_id, granted_bits__gt=0
                ).select_related('module'):
                    for action_name, bit in ACTION_BITS.items():
                        if action_name == '_RESERVED':
                            continue
                        if perm.granted_bits & bit:
                            code = f'{perm.module.category}:{perm.module.name}:{action_name}'
                            if code not in seen:
                                seen.add(code)
                                menu_codes.append(code)

    # 判断用户是否有任意分类的权限（用于侧边栏分组显示控制）
    has_finance_perm = any(c.startswith('finance:') for c in menu_codes) if menu_codes else False
    has_approval_perm = any(c.startswith('approval:') for c in menu_codes) if menu_codes else False
    has_crm_perm = any(c.startswith('crm:') for c in menu_codes) if menu_codes else False
    has_project_perm = any(c.startswith('project:') for c in menu_codes) if menu_codes else False
    has_system_perm = any(c.startswith('system:') for c in menu_codes) if menu_codes else False
    has_purchasing_perm = any(c.startswith('purchasing:') for c in menu_codes) if menu_codes else False
    has_operations_perm = any(c.startswith('operations:') for c in menu_codes) if menu_codes else False
    has_files_perm = any(c.startswith('files:') for c in menu_codes) if menu_codes else False

    return {
        'user_menu_codes': menu_codes,
        'user_has_finance_perm': has_finance_perm,
        'user_has_approval_perm': has_approval_perm,
        'user_has_crm_perm': has_crm_perm,
        'user_has_project_perm': has_project_perm,
        'user_has_system_perm': has_system_perm,
        'user_has_purchasing_perm': has_purchasing_perm,
        'user_has_operations_perm': has_operations_perm,
        'user_has_files_perm': has_files_perm,
    }
