"""公司上下文中间件 — 为每个请求注入 request.auth_company"""
from django.utils.deprecation import MiddlewareMixin


class CompanyContextMiddleware(MiddlewareMixin):
    """
    为已认证用户注入 request.auth_company。

    买断版（standalone）：所有用户使用 DEFAULT_COMPANY_ID。
    租赁版（subscription）：从 session 或 UserCompanyPermission 解析租户。

    不再依赖 UserCompanyRole。
    """

    def process_request(self, request):
        request.auth_company = None
        request.auth_company_role = None  # 已废弃，始终为 None

        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return

        # 买断版：所有用户使用同一个预设公司
        if self._is_standalone():
            self._apply_standalone_company(request)
            return

        # 租赁版：从 UCP 解析
        from apps.core.models import UserCompanyPermission
        from apps.finance.models import Company

        company_id = request.session.get('current_company_id')

        if company_id:
            # 验证用户在 session 指定的该公司有 UCP
            if UserCompanyPermission.objects.filter(
                user=request.user, company_id=company_id, is_granted=True
            ).exists():
                try:
                    company = Company.objects.get(id=company_id)
                    request.auth_company = company
                    return
                except Company.DoesNotExist:
                    pass

        # 无 session 或 session 公司无效：从 UCP 取第一个有权限的公司
        first_ucp = UserCompanyPermission.objects.filter(
            user=request.user, is_granted=True
        ).select_related('module').order_by('company_id').first()

        if first_ucp:
            try:
                company = Company.objects.get(id=first_ucp.company_id)
                request.auth_company = company
                request.session['current_company_id'] = first_ucp.company_id
            except Company.DoesNotExist:
                pass

        if request.auth_company:
            if hasattr(request.user, 'company_id'):
                request.user.company_id = request.auth_company.id

    def _is_standalone(self):
        from django.conf import settings
        return settings.TENANT_MODE == 'standalone'

    def _apply_standalone_company(self, request):
        """买断版：强制使用 DEFAULT_COMPANY_ID"""
        from django.conf import settings
        from apps.finance.models import Company

        if not settings.DEFAULT_COMPANY_ID:
            return

        try:
            company = Company.objects.get(id=settings.DEFAULT_COMPANY_ID)
            request.auth_company = company
            request.session['current_company_id'] = settings.DEFAULT_COMPANY_ID
        except Company.DoesNotExist:
            pass
