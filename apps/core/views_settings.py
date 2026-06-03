from __future__ import annotations

import logging
from rest_framework import viewsets, status, permissions, serializers
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from django.db.models.query import QuerySet
from .models import SystemSetting, CodingRule
from .serializers import (
    SystemSettingSerializer,
    FinanceCompanySerializer,
)
from apps.finance.models import Company as FinanceCompany
from apps.core.exceptions import api_error, ErrorCode
from apps.core.permissions import RoleRequired

logger = logging.getLogger(__name__)


class SystemSettingViewSet(viewsets.ModelViewSet):
    """系统参数管理视图集"""

    queryset = SystemSetting.objects.all()
    serializer_class = SystemSettingSerializer
    permission_classes = [permissions.IsAuthenticated, RoleRequired]
    lookup_field = 'key'

    def get_queryset(self) -> QuerySet:
        queryset = SystemSetting.objects.all()
        category = self.request.query_params.get('category')
        if category == 'approval':
            queryset = queryset.filter(key__startswith='approval')
        elif category == 'wage':
            queryset = queryset.filter(key__startswith='wage')
        elif category == 'email':
            queryset = queryset.filter(key__startswith='email')
        elif category == 'domain':
            queryset = queryset.filter(key__startswith='site_') | queryset.filter(key__startswith='ssl_')
        return queryset.order_by('key')

    @action(detail=False, methods=['get'])
    def all_settings(self, request: Request) -> Response:
        """获取所有系统参数的键值对字典 — GET /api/core/settings/all_settings/"""
        settings = {s.key: s.value for s in SystemSetting.objects.all()}
        return Response({'status': 'success', 'settings': settings}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def health_check(self, request: Request) -> Response:
        """外部依赖健康检查 — GET /api/core/settings/health_check/"""
        try:
            # 逐步测试每个方法
            count = SystemSetting.objects.count()
            domain = SystemSetting.get_value('site_domain')
            email_ok = SystemSetting.is_email_configured()
            https_ok = SystemSetting.is_https_ready()

            missing = []
            if not email_ok:
                missing.append('邮件服务（SMTP）')
            if not domain:
                missing.append('系统域名（site_domain）')
            elif not https_ok:
                missing.append('SSL证书')

            return Response(
                {
                    'status': 'ok' if not missing else 'incomplete',
                    'setting_count': count,
                    'domain': domain or '(未配置)',
                    'email_ok': email_ok,
                    'https_ok': https_ok,
                    'missing': missing,
                    'message': '所有外部依赖已就绪 ✓' if not missing else f'还需配置: {", ".join(missing)}',
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            import traceback

            return Response(
                {
                    'error': str(e),
                    'type': type(e).__name__,
                    'tb': traceback.format_exc(),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def update(self, request: Request, *args, **kwargs) -> Response:
        instance = self.get_object()
        new_value = request.data.get('value')
        if new_value is None:
            return api_error(ErrorCode.VALIDATION_ERROR, 'value 不能为空')
        instance.value = new_value
        try:
            instance.save(update_fields=['value', 'updated_at'])
        except Exception as e:
            return Response(
                {'status': 'error', 'message': f'保存设置失败：{str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        return Response(
            {'status': 'success', 'message': '设置已更新', 'data': SystemSettingSerializer(instance).data},
            status=status.HTTP_200_OK,
        )

    def partial_update(self, request: Request, *args, **kwargs) -> Response:
        return self.update(request, *args, **kwargs)


class FinanceCompanyViewSet(viewsets.ModelViewSet):
    """公司信息管理视图集"""

    queryset = FinanceCompany.objects.all()
    serializer_class = FinanceCompanySerializer
    permission_classes = [permissions.IsAuthenticated, RoleRequired]

    def get_queryset(self) -> QuerySet:
        if not self.request.user.is_authenticated:
            return FinanceCompany.objects.none()
        from apps.core.permissions import get_module_companies

        companies = get_module_companies(self.request.user, 'company', 'read')
        if companies is None:
            queryset = FinanceCompany.objects.all()
        else:
            queryset = FinanceCompany.objects.filter(id__in=companies)
        status = self.request.query_params.get('status')
        if status:
            queryset = queryset.filter(status=status)
        return queryset.order_by('-created_at')

    @action(detail=False, methods=['get'])
    def active(self, request: Request) -> Response:
        """获取所有启用状态的公司"""
        companies = FinanceCompany.objects.filter(status='active').order_by('name')
        return Response(
            {'status': 'success', 'companies': FinanceCompanySerializer(companies, many=True).data},
            status=status.HTTP_200_OK,
        )


class CodingRuleSerializer(serializers.ModelSerializer):
    model_name_display = serializers.CharField(source='get_model_name_display', read_only=True)

    class Meta:
        model = CodingRule
        fields = '__all__'
        read_only_fields = ['created_at']


class CodingRuleViewSet(viewsets.ModelViewSet):
    """编码规则配置 — 各模块自动编号规则可自定义"""

    queryset = CodingRule.objects.all()
    serializer_class = CodingRuleSerializer
    permission_classes = [permissions.IsAuthenticated, RoleRequired]
    action_perms = {
        None: 'core:system:read',
        'create': 'core:system:update',
        'update': 'core:system:update',
        'partial_update': 'core:system:update',
        'destroy': 'core:system:update',
    }
