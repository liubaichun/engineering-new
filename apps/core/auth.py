from rest_framework.authentication import SessionAuthentication


class CSRFExemptSessionAuthentication(SessionAuthentication):
    """
    内部系统禁用CSRF检查的Session认证。

    设计理由：
    - 内部ERP系统，无公网直接暴露
    - 所有API端点均经Session认证（登录后cookie自动携带）
    - 前端SPA使用AJAX请求，CRUD操作均走API视图
    - CsrfViewMiddleware已在settings.py中启用（满足Django安全检查）
    - 本认证类为REST API端点豁免CSRF检查

    面向外部的服务（如果将来有）应使用标准SessionAuthentication并强制CSRF。
    """

    def enforce_csrf(self, request):
        return  # 不进行CSRF检查


# ── drf-spectacular auth extension（消除 schema 生成警告） ──
from drf_spectacular.extensions import OpenApiAuthenticationExtension


class SessionAuthExtension(OpenApiAuthenticationExtension):
    target_class = 'apps.core.auth.CSRFExemptSessionAuthentication'
    name = 'SessionAuth'

    def get_security_definition(self, auto_schema):
        return {
            'type': 'apiKey',
            'in': 'cookie',
            'name': 'sessionid',
            'description': 'Cookie-based session auth (csrf exempt). '
            'Login via POST /api/core/auth/login/ obtains session cookie.',
        }
