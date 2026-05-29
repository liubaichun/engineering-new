import logging
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

logger = logging.getLogger(__name__)

from .models import UserCompanyRole
from .serializers import CompanyRoleSerializer
from apps.core.exceptions import api_error, ErrorCode
from apps.core.permissions import RoleRequired


class CompanyRoleViewSet(viewsets.ModelViewSet):
    """
    用户公司角色分配视图集 — 基于 UserCompanyRole。

    提供用户角色分配的 CRUD，分配时自动批量写入 UserCompanyPermission。
    GET  /api/core/company-roles/                    → 所有用户角色分配记录
    GET  /api/core/company-roles/?company_id=X       → 某公司下所有用户角色
    GET  /api/core/company-roles/?user_id=X          → 某用户所有公司角色
    POST /api/core/company-roles/                   → {user_id, company_id, company_role_id, is_primary}
    PATCH /api/core/company-roles/{id}/             → 更新角色
    DELETE /api/core/company-roles/{id}/             → 删除（并清理UCP）
    """

    queryset = UserCompanyRole.objects.select_related('user', 'company', 'assigned_by', 'company_role')
    serializer_class = CompanyRoleSerializer
    permission_classes = [permissions.IsAuthenticated, RoleRequired]

    def get_queryset(self):
        qs = UserCompanyRole.objects.select_related('user', 'company', 'assigned_by', 'company_role')
        company_id = self.request.query_params.get('company_id')
        user_id = self.request.query_params.get('user_id')
        if company_id:
            qs = qs.filter(company_id=company_id)
        if user_id:
            qs = qs.filter(user_id=user_id)
        return qs.order_by('-assigned_at')

    def perform_create(self, serializer):
        obj = serializer.save(assigned_by=self.request.user)
        self._assign_role_to_ucp(obj)

    def perform_update(self, serializer):
        obj = serializer.save()
        self._assign_role_to_ucp(obj)

    def perform_destroy(self, instance):
        self._revoke_role_from_ucp(instance)
        instance.delete()

    def _assign_role_to_ucp(self, ucr):
        """分配角色时：批量写入 UserCompanyPermission"""
        if not ucr.company_role:
            return
        from django.db import transaction
        from apps.core.models import UserCompanyPermission, ModuleAction

        with transaction.atomic():
            # 先删除该角色之前可能存在的UCP记录（避免重复）
            UserCompanyPermission.objects.filter(
                user=ucr.user, company=ucr.company, source=f'role:{ucr.company_role.id}'
            ).delete()
            # 批量写入
            for perm in ucr.company_role.permissions.all():
                # 找到对应的 ModuleAction
                ma = ModuleAction.objects.filter(perm_codes__contains=[perm.code]).first()
                if not ma:
                    continue
                UserCompanyPermission.objects.update_or_create(
                    user=ucr.user,
                    company=ucr.company,
                    module=ma.module,
                    action=ma,
                    defaults={
                        'is_granted': True,
                        'source': f'role:{ucr.company_role.id}',
                        'granted_by': ucr.assigned_by,
                    },
                )

    def _revoke_role_from_ucp(self, ucr):
        """移除角色时：删除该角色来源的 UCP 记录"""
        if not ucr.company_role:
            return
        from apps.core.models import UserCompanyPermission

        UserCompanyPermission.objects.filter(
            user=ucr.user, company=ucr.company, source=f'role:{ucr.company_role.id}'
        ).delete()

    @action(detail=False, methods=['get'])
    def roles_summary(self, request):
        """
        角色统计摘要 — 返回所有公司的角色分布。
        GET /api/core/company-roles/roles_summary/
        """
        from django.db.models import Count

        summary = (
            UserCompanyRole.objects.values('company__id', 'company__name', 'company_role__id', 'company_role__name')
            .annotate(count=Count('id'))
            .order_by('company__name', 'company_role__name')
        )
        result = []
        for item in summary:
            result.append(
                {
                    'company_id': item['company__id'],
                    'company_name': item['company__name'],
                    'company_role_id': item['company_role__id'],
                    'company_role_name': item['company_role__name'] or '未分配',
                    'count': item['count'],
                }
            )
        return Response({'status': 'success', 'summary': result})

    @action(detail=False, methods=['get'])
    def available_roles(self, request):
        """
        可用角色列表 — 返回当前用户在当前公司可分配的角色。
        GET /api/core/company-roles/available_roles/?company_id=X
        """
        from apps.finance.models import Company

        company_id = request.query_params.get('company_id')
        if not company_id:
            return Response({'status': 'success', 'roles': []})
        try:
            company = Company.objects.get(id=company_id)
        except Company.DoesNotExist:
            return api_error(ErrorCode.NOT_FOUND, '公司不存在', status_code=404)
        roles = company.company_roles.filter(is_active=True)
        return Response({'status': 'success', 'roles': [{'id': r.id, 'name': r.name, 'code': r.code} for r in roles]})


# ── 用户公司权限矩阵 ──────────────────────────────────────────────────────────
