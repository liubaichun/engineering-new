from __future__ import annotations

import logging
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from django.utils import timezone
from django.db.models.query import QuerySet

logger = logging.getLogger(__name__)

from .models import PermissionAuditLog, ModuleAction
from .serializers import (
    PermissionListSerializer,
    ModuleActionSerializer,
    PermissionAuditLogSerializer,
)
from apps.core.permissions import RoleRequired


class PermissionViewSet(viewsets.ReadOnlyModelViewSet):
    """权限码列表（仅读，用于角色配置UI）"""

    queryset = ModuleAction.objects.select_related('module').all().order_by('module__name', 'sort_order')
    permission_classes = [permissions.IsAuthenticated, RoleRequired]

    def get_serializer_class(self) -> type:
        if self.action == 'list':
            return PermissionListSerializer
        return ModuleActionSerializer


class PermissionAuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """权限审计日志视图集（仅读）"""

    queryset = PermissionAuditLog.objects.all()
    serializer_class = PermissionAuditLogSerializer
    permission_classes = [permissions.IsAuthenticated, RoleRequired]

    def get_queryset(self) -> QuerySet:
        queryset = PermissionAuditLog.objects.select_related('user', 'target_user')
        # 过滤：操作人/目标用户/操作类型/角色
        target_user_id = self.request.query_params.get('target_user')
        action = self.request.query_params.get('action')
        if target_user_id:
            queryset = queryset.filter(target_user_id=target_user_id)
        if action:
            queryset = queryset.filter(action=action)
        return queryset

    @action(detail=False, methods=['get'])
    def export(self, request: Request) -> Response:
        """导出权限审计日志 Excel"""
        from apps.core.export_excel import export_audit_logs, make_export_response

        queryset = self.get_queryset()
        records = queryset[:5000]
        buf = export_audit_logs(list(records))
        return make_export_response(buf, f'权限审计日志_{timezone.now().strftime("%Y%m%d")}.xlsx')
