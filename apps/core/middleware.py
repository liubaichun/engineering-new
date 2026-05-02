"""公司上下文中间件 — 为每个请求注入 request.auth_company"""
from django.utils.deprecation import MiddlewareMixin


class CompanyContextMiddleware(MiddlewareMixin):
    """
    为已认证用户注入 request.auth_company。

    买断版（standalone）：所有用户共享 DEFAULT_COMPANY_ID，无视 UserCompanyRole。
    租赁版（subscription）：从 session 或 UserCompanyRole 解析租户。
    """

    def process_request(self, request):
        request.auth_company = None
        request.auth_company_role = None

        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return

        # 买断版：所有用户使用同一个预设公司
        if self._is_standalone():
            self._apply_standalone_company(request)
            return

        # 租赁版：从 UserCompanyRole 解析
        from apps.core.models import UserCompanyRole

        company_id = request.session.get('current_company_id')
        if company_id:
            link = UserCompanyRole.objects.filter(
                user=request.user, company_id=company_id
            ).select_related('company').first()
        else:
            link = UserCompanyRole.objects.filter(
                user=request.user
            ).select_related('company').first()

        if link:
            request.auth_company = link.company
            request.auth_company_role = link.role
            request.session['current_company_id'] = link.company_id

    def _is_standalone(self):
        from django.conf import settings
        return settings.TENANT_MODE == 'standalone'

    def _apply_standalone_company(self, request):
        """买断版：强制使用 DEFAULT_COMPANY_ID"""
        from django.conf import settings
        from apps.finance.models import Company

        if not settings.DEFAULT_COMPANY_ID:
            # 未配置则跳过，不阻断请求
            return

        try:
            company = Company.objects.get(id=settings.DEFAULT_COMPANY_ID)
            request.auth_company = company
            request.session['current_company_id'] = settings.DEFAULT_COMPANY_ID
        except Company.DoesNotExist:
            pass
