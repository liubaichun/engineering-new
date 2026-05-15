"""
角色权限强制校验 — 商业化必备

用法：
    from apps.core.permissions import RoleRequired

    # 方式一：类级统一权限（所有 action 共用同一个权限码）
    class MyViewSet(viewsets.ModelViewSet):
        permission_classes = [IsAuthenticated, RoleRequired]
        required_perms = ['expense:create']            # 所有 action 共用

    # 方式二：action 级精细权限（推荐，按 action 映射权限码）
    class MyViewSet(viewsets.ModelViewSet):
        permission_classes = [IsAuthenticated, RoleRequired]
        # 格式: {action_name: required_permission_code}
        # action_name 为 None 表示该权限适用于所有未单独声明的 action
        # action_name 为标准 DRF action 名（list/retrieve/create/update/destroy/...）
        action_perms = {
            None: 'material:stock:read',          # 默认权限（兜底）
            'list': 'material:stock:read',
            'retrieve': 'material:stock:read',
            'create': 'material:stock:update',
            'update': 'material:stock:update',
            'partial_update': 'material:stock:update',
            'destroy': 'material:stock:update',
            'record_usage': 'material:usage:create',
        }

    # 方式三：角色级校验（与权限二选一，角色校验优先）
    class MyViewSet(viewsets.ModelViewSet):
        permission_classes = [IsAuthenticated, RoleRequired]
        required_roles = ['admin']                    # 需要 admin 角色（任一满足即可）
"""

from rest_framework.permissions import BasePermission


class RoleRequired(BasePermission):
    """
    角色 + 权限两层校验：

    required_roles  — 列表，任一满足即可。为空则不校验角色。
    required_perms  — 列表，全部满足才放行。为空则不校验权限（配合 action_perms 使用）。
    optional_perms  — 列表，有则附加到 request.user 供后续使用。
    action_perms    — dict，格式 {action_name: perm_code} 或 {None: default_perm_code}。
                      自动按当前请求的 action 查找对应权限码，None 作为兜底。
                      与 required_perms 配合：先查 action_perms，未命中则用 required_perms。
    """

    # None 的 key 用于 action_perms 中表示未声明 action 的默认权限
    _wildcard = None

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        user = request.user

        # 系统级超级用户跳过所有校验
        if user.is_superuser:
            return True

        # ── 角色校验（优先于权限校验）─────────────────────────────────────────
        required_roles = getattr(view, 'required_roles', [])
        if required_roles:
            # 先试系统级角色
            if user.role in required_roles:
                return True
            # 再试公司级角色
            company_id = self._get_company_id(request, view)
            if company_id:
                for rc in required_roles:
                    if user.has_role(rc, company_id):
                        return True
            return False

        # ── 权限校验 ──────────────────────────────────────────────────────────
        # 确定当前 action 对应的权限码
        perm_code = self._resolve_action_perm(request, view)

        if perm_code:
            if not user.has_perm(perm_code):
                return False
            # 记录已检查的权限
            request._checked_perms = getattr(request, '_checked_perms', set())
            request._checked_perms.add(perm_code)

        return True

    def _resolve_action_perm(self, request, view):
        """
        解析当前 action 对应的权限码。

        查找顺序：
        1. action_perms[action_name]  — 精确匹配当前 action
        2. action_perms[None]        — 兜底默认权限
        3. required_perms             — 类级统一权限（向后兼容）
        """
        action_perms = getattr(view, 'action_perms', {})
        required_perms = getattr(view, 'required_perms', [])

        # 当前 action 名（如 'list', 'retrieve', 'create', 'destroy', 'record_usage'）
        action_name = getattr(view, 'action', None)

        # 1. 精确匹配
        if action_perms and action_name in action_perms:
            return action_perms[action_name]

        # 2. 兜底默认
        if action_perms and self._wildcard in action_perms:
            return action_perms[self._wildcard]

        # 3. 类级统一权限（向后兼容原始用法）
        if required_perms:
            return required_perms[0] if isinstance(required_perms, list) else required_perms

        return None

    def _get_company_id(self, request, view):
        """从请求中提取 company_id"""
        # URL query param ?company=1
        company_id = request.query_params.get('company')
        if company_id:
            return int(company_id)
        # URL path kwarg {pk}
        if hasattr(view, 'kwargs') and 'pk' in view.kwargs:
            return view.kwargs.get('pk')
        # request.data POST body
        company_id = request.data.get('company_id') if hasattr(request, 'data') else None
        if company_id:
            return int(company_id)
        return None


# ─── 常用角色权限预定义 ──────────────────────────────────────────────────────

class FinanceOnly(RoleRequired):
    """财务专用：仅 admin 和 finance 角色可访问"""
    required_roles = ['admin', 'finance']


class ManagerOnly(RoleRequired):
    """管理层专用：admin / manager / finance"""
    required_roles = ['admin', 'manager', 'finance']


class AdminOnly(RoleRequired):
    """系统管理员：仅 admin 角色"""
    required_roles = ['admin']
