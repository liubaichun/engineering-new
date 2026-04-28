from rest_framework.authentication import SessionAuthentication

class CSRFExemptSessionAuthentication(SessionAuthentication):
    """
    禁用CSRF检查的Session认证。
    用于内部系统，所有请求已通过session认证。
    """
    def enforce_csrf(self, request):
        return  # 不进行CSRF检查
