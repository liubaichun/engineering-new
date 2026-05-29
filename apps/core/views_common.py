import logging
from rest_framework import viewsets, filters, status, permissions, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from apps.core.auth import CSRFExemptSessionAuthentication
from drf_spectacular.utils import extend_schema
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.conf import settings
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
