from __future__ import annotations

import logging
from rest_framework import viewsets, status, permissions, serializers
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from django.db.models.query import QuerySet

logger = logging.getLogger(__name__)

from .models import SystemSetting, CompanyRole
from .serializers import (
    SystemSettingSerializer,
    FinanceCompanySerializer,
)
from apps.finance.models import Company as FinanceCompany
from apps.core.exceptions import api_error, ErrorCode
from apps.core.permissions import RoleRequired


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
        queryset = FinanceCompany.objects.all()
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


# ── 公司角色定义 CRUD ────────────────────────────────────────────────────────


class CompanyRoleDefViewSet(viewsets.ModelViewSet):
    """
    公司角色定义 — CRUD CompanyRole 本身。

    GET  /api/core/company-role-defs/                       → 所有角色定义
    GET  /api/core/company-role-defs/?company_id=X          → 某公司下角色定义
    POST /api/core/company-role-defs/                        → {company_id, name, code, description}
    PATCH/DELETE /api/core/company-role-defs/{id}/          → 更新/删除
    """

    queryset = CompanyRole.objects.select_related('company')
    permission_classes = [permissions.IsAuthenticated, RoleRequired]
    lookup_field = 'id'

    def get_serializer_class(self) -> type:
        if self.action == 'list':
            return CompanyRoleDefListSerializer
        return CompanyRoleDefSerializer

    def get_queryset(self) -> QuerySet:
        qs = CompanyRole.objects.select_related('company')
        company_id = self.request.query_params.get('company_id')
        if company_id:
            qs = qs.filter(company_id=company_id)
        return qs.order_by('company__name', 'name')

    def perform_create(self, serializer) -> None:
        role = serializer.save()
        # 新建时若同时提交了 permission_ids，同步写入中间表
        perm_ids = self.request.data.get('permission_ids', [])
        if perm_ids:
            self._sync_permissions(role, perm_ids)

    def perform_update(self, serializer) -> None:
        role = serializer.save()
        perm_ids = self.request.data.get('permission_ids', [])
        if perm_ids is not None:  # None=未传，保留原值；[]=显式清空
            self._sync_permissions(role, perm_ids)

    def perform_destroy(self, instance) -> None:
        # 检查是否已有用户分配了这个角色
        from .models import UserCompanyRole

        if UserCompanyRole.objects.filter(company_role=instance).exists():
            raise serializers.ValidationError({'detail': '该角色已有用户分配，无法删除'})
        instance.delete()

    def _sync_permissions(self, role, permission_ids: list) -> None:
        from django.db import transaction
        from .models import CompanyRolePermission, Permission

        with transaction.atomic():
            CompanyRolePermission.objects.filter(company_role=role).delete()
            for perm_id in permission_ids:
                if not Permission.objects.filter(id=perm_id).exists():
                    continue
                CompanyRolePermission.objects.create(
                    company_role=role,
                    permission_id=perm_id,
                )


class CompanyRoleDefListSerializer(serializers.ModelSerializer):
    """角色定义列表序列化器"""

    company_name = serializers.CharField(source='company.name', read_only=True)
    permission_count = serializers.SerializerMethodField()

    class Meta:
        model = CompanyRole
        fields = [
            'id',
            'name',
            'code',
            'description',
            'is_active',
            'company',
            'company_name',
            'permission_count',
            'created_at',
            'updated_at',
        ]

    def get_permission_count(self, obj):
        return obj.permissions.count()


class CompanyRoleDefSerializer(serializers.ModelSerializer):
    """角色定义详情序列化器（包含权限列表）"""

    company_name = serializers.CharField(source='company.name', read_only=True)
    permissions = serializers.SerializerMethodField()
    # permission_ids: 写入时接受 [perm_id, ...]，写入 CompanyRolePermission 中间表
    permission_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False, default=list
    )

    class Meta:
        model = CompanyRole
        fields = [
            'id',
            'name',
            'code',
            'description',
            'is_active',
            'company',
            'company_name',
            'permissions',
            'permission_ids',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_permissions(self, obj):
        return [{'id': p.id, 'code': p.code, 'name': p.name} for p in obj.permissions.all()]

    def update(self, instance, validated_data):
        # permission_ids 的同步由 ViewSet.perform_update 统一处理
        return super().update(instance, validated_data)


# ── 角色管理（基于新权限系统 UserCompanyRole）───────────────────────────────
