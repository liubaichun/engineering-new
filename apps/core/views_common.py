import logging
from django.middleware.csrf import get_token

logger = logging.getLogger(__name__)


def get_csrf_token(request):
    """获取CSRF token"""
    return {'csrf_token': get_token(request)}


def get_client_ip(request):
    """从请求中提取客户端IP"""
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')
