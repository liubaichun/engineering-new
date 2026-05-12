"""
角色权限强制校验 — 商业化必备

用法：
    from apps.core.permissions import RoleRequired

    class MyViewSet(viewsets.ModelViewSet):
        permission_classes = [IsAuthenticated, RoleRequired]
        required_roles = ['admin']                    # 需要 admin 角色（任一满足即可）
        required_perms = ['expense:create']            # 需要 expense:create 权限（同时满足）
        optional_perms = ['expense:read', 'expense:list']  # 可选权限（有则附加）
"""

from rest_framework.permissions import BasePermission


class RoleRequired(BasePermission):
    """
    角色+权限两层校验：

    required_roles  — 列表，任一满足即可。为空则不校验角色。
    required_perms  — 列表，全部满足才放行。为空则不校验权限。
    optional_perms  — 列表，有则附加到 request.user 供后续使用。
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        user = request.user

        # 系统级超级用户跳过所有校验
        if user.is_superuser:
            return True

        # ── 角色校验 ──────────────────────────────────────────────────────────
        required_roles = getattr(view, 'required_roles', [])
        if required_roles:
            # 先试系统级角色
            if user.role in required_roles:
                return True
            # 再试公司级角色（取请求中的 company_id）
            company_id = self._get_company_id(request, view)
            if company_id:
                for rc in required_roles:
                    if user.has_role(rc, company_id):
                        return True
            return False

        # ── 权限校验 ──────────────────────────────────────────────────────────
        required_perms = getattr(view, 'required_perms', [])
        optional_perms = getattr(view, 'optional_perms', [])
        all_check_perms = required_perms + optional_perms

        for code in all_check_perms:
            if user.has_perm(code):
                request._checked_perms = getattr(request, '_checked_perms', set())
                request._checked_perms.add(code)

        if required_perms:
            for code in required_perms:
                if not user.has_perm(code):
                    return False

        return True

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


# ─── 常用角色权限预定义 ────────────────────────────────────────────────────

class FinanceOnly(RoleRequired):
    """财务专用：仅 admin 和 finance 角色可访问"""
    required_roles = ['admin', 'finance']


class ManagerOnly(RoleRequired):
    """管理层专用：admin / manager / finance"""
    required_roles = ['admin', 'manager', 'finance']


class AdminOnly(RoleRequired):
    """系统管理员：仅 admin 角色"""
    required_roles = ['admin']
