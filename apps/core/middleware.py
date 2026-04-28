"""公司上下文中间件 — 为每个请求注入 request.auth_company"""
from django.utils.deprecation import MiddlewareMixin


class CompanyContextMiddleware(MiddlewareMixin):
    """
    为已认证用户注入 request.auth_company。
    逻辑：从 session['current_company_id'] 读取当前公司ID，
    若无则以用户第一个可访问公司作为默认（登录后自动落在第一个公司）。
    """

    def process_request(self, request):
        request.auth_company = None
        request.auth_company_role = None

        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return

        from apps.core.models import UserCompanyRole

        # 优先取 session 中已选公司
        company_id = request.session.get('current_company_id')
        if company_id:
            link = UserCompanyRole.objects.filter(
                user=request.user, company_id=company_id
            ).select_related('company').first()
        else:
            # 无 session → 取用户的第一个公司作为默认值
            link = UserCompanyRole.objects.filter(
                user=request.user
            ).select_related('company').first()

        if link:
            request.auth_company = link.company
            request.auth_company_role = link.role
            # 同步 session
            request.session['current_company_id'] = link.company_id
