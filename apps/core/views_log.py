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

logger = logging.getLogger(__name__)

from .models import LoginLog, OperationAuditLog
from .serializers import (
    LoginLogSerializer,
    OperationAuditLogSerializer,
)
from apps.core.permissions import RoleRequired
from apps.core.export_excel import export_audit_logs, make_export_response


class LoginLogViewSet(viewsets.ReadOnlyModelViewSet):
    """登录日志视图集（仅读）"""
    queryset = LoginLog.objects.all()
    serializer_class = LoginLogSerializer
    permission_classes = [permissions.IsAuthenticated, RoleRequired]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['created_at', 'status']
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = LoginLog.objects.select_related('user')
        # 管理员看全部，普通用户只看自己的
        if not self.request.user.is_superuser:
            queryset = queryset.filter(user=self.request.user)
        username = self.request.query_params.get('username')
        status_filter = self.request.query_params.get('status')
        if username:
            queryset = queryset.filter(username__icontains=username)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset


    @action(detail=False, methods=['get'])
    def export(self, request):
        """导出登录日志 Excel"""
        from apps.core.export_excel import export_audit_logs, make_export_response
        queryset = self.get_queryset()
        records = queryset[:5000]
        buf = export_audit_logs(list(records))
        return make_export_response(buf, f'登录日志_{timezone.now().strftime("%Y%m%d")}.xlsx')


class OperationAuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    操作审计日志视图集（仅读）
    支持按 app_label / action / username / date_from / date_to 筛选
    """
    queryset = OperationAuditLog.objects.all()
    serializer_class = OperationAuditLogSerializer
    permission_classes = [permissions.IsAuthenticated, RoleRequired]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['username', 'object_repr', 'app_label', 'model_name']
    ordering_fields = ['created_at', 'action']
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = OperationAuditLog.objects.select_related('user')
        user = self.request.user

        # 超级管理员：跨公司查看全部；普通管理员：仅本公司
        if user.is_superuser:
            pass  # 不过滤
        elif hasattr(user, 'company_id') and user.company_id:
            queryset = queryset.filter(company_id=user.company_id)
        else:
            queryset = queryset.filter(company_id__isnull=True)

        app_label = self.request.query_params.get('app_label')
        if app_label:
            queryset = queryset.filter(app_label=app_label)

        model_name = self.request.query_params.get('model_name')
        if model_name:
            queryset = queryset.filter(model_name=model_name)

        action = self.request.query_params.get('action')
        if action:
            queryset = queryset.filter(action=action)

        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)

        username = self.request.query_params.get('username')
        if username:
            queryset = queryset.filter(username__icontains=username)

        return queryset

    @action(detail=False, methods=['get'])
    def export(self, request):
        """导出审计日志 Excel"""
        from apps.core.export_excel import export_audit_logs, make_export_response
        queryset = self.get_queryset()
        records = queryset[:5000]  # 最多导出5000条
        buf = export_audit_logs(list(records))
        return make_export_response(buf, f'审计日志_{timezone.now().strftime("%Y%m%d")}.xlsx')
