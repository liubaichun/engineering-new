"""公司上下文中间件 — 为每个请求注入 request.auth_company"""

from django.utils.deprecation import MiddlewareMixin


class CompanyContextMiddleware(MiddlewareMixin):
    """
    为已认证用户注入 request.auth_company。

    多公司经营模式：用户通过 UserCompanyPermission 关联到多个公司，
    当前公司从 session['current_company_id'] 读取，用户可切换。
    """

    def process_request(self, request):
        request.auth_company = None
        request.auth_company_role = None  # 已废弃，始终为 None

        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return

        # 从 session 获取当前公司
        from apps.core.models import UserCompanyPermission
        from apps.finance.models import Company

        company_id = request.session.get('current_company_id')

        if company_id:
            # 验证用户在 session 指定的该公司有 UCP
            if UserCompanyPermission.objects.filter(user=request.user, company_id=company_id, is_granted=True).exists():
                try:
                    company = Company.objects.get(id=company_id)
                    request.auth_company = company
                    return
                except Company.DoesNotExist:
                    pass

        # 无 session 或 session 公司无效：从 UCP 取第一个有权限的公司
        first_ucp = (
            UserCompanyPermission.objects.filter(user=request.user, is_granted=True)
            .select_related('module')
            .order_by('company_id')
            .first()
        )

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
