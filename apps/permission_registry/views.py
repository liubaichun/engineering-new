"""
permission_registry API — 用户×公司×模块五档权限矩阵管理

REST API：
  GET  /api/permission-registry/users/<id>/permissions/
       → 该用户所有公司的权限矩阵

  POST /api/permission-registry/users/<id>/permissions/
       → 为用户新增一条权限记录（某个公司×某个模块）

  PATCH /api/permission-registry/users/<id>/permissions/batch/
       → 批量更新权限（一次提交多个模块/公司）

  PUT /api/permission-registry/users/<id>/permissions/<permission_id>/
       → 更新单条权限

  DELETE /api/permission-registry/users/<id>/permissions/<permission_id>/
       → 删除单条权限

  GET /api/permission-registry/modules/
       → 所有可用模块及权限定义

  GET /api/permission-registry/companies/
       → 所有公司列表（用于权限矩阵列）
"""

from rest_framework import viewsets, serializers, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from apps.core.models import User
from apps.finance.models import Company
from apps.permission_registry.models import Module, ModulePermission, UserCompanyPermission


# ─── Serializers ─────────────────────────────────────────────────────────────

class ModuleSerializer(serializers.ModelSerializer):
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = Module
        fields = ['id', 'name', 'label', 'icon', 'description',
                  'sort_order', 'is_active', 'permissions']

    def get_permissions(self, obj):
        return list(
            obj.permissions.order_by('sort_order')
            .values('id', 'name', 'label', 'sort_order')
        )


class UserCompanyPermissionSerializer(serializers.ModelSerializer):
    module_name = serializers.CharField(source='module.name', read_only=True)
    module_label = serializers.CharField(source='module.label', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = UserCompanyPermission
        fields = [
            'id', 'user', 'username',
            'company', 'company_name',
            'module', 'module_name', 'module_label',
            'is_primary', 'can_view', 'can_create',
            'can_edit', 'can_delete', 'can_approve',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class BatchPermissionSerializer(serializers.Serializer):
    """批量权限更新请求体"""
    permissions = serializers.ListField(child=serializers.DictField(), allow_empty=True)

    def validate_permissions(self, value):
        if not value:
            return value  # 空数组由 view 层提前返回 200
        required_fields = {'company_id', 'module_id'}
        bool_fields = {'can_view', 'can_create', 'can_edit', 'can_delete', 'can_approve', 'is_primary'}
        for item in value:
            if not required_fields.issubset(item.keys()):
                raise serializers.ValidationError(
                    f"每条权限必须包含 company_id 和 module_id，当前: {item}"
                )
            # 强制类型转换
            for f in bool_fields:
                if f in item and not isinstance(item[f], bool):
                    item[f] = bool(item[f])
        return value


# ─── ViewSets ───────────────────────────────────────────────────────────────

class PermissionMatrixViewSet(viewsets.ViewSet):
    """
    权限矩阵 API。

    GET /api/permission-registry/users/<user_id>/permissions/
      → 返回该用户所有公司的完整权限矩阵

    POST /api/permission-registry/users/<user_id>/permissions/
      → 新增一条权限记录（某个公司×某个模块的五档设置）

    PATCH /api/permission-registry/users/<user_id>/permissions/batch/
      → 批量更新（推荐：一次提交某用户所有公司的所有模块权限）

    DELETE /api/permission-registry/users/<id>/permissions/<permission_id>/
      → 删除单条
    """
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request, user_pk=None):
        """返回某用户所有公司的所有模块权限（矩阵形式）"""
        user = get_object_or_404(User, pk=user_pk)

        # 返回所有公司的所有模块（作为列）
        modules = Module.objects.filter(is_active=True).order_by('sort_order', 'name')
        companies = list(Company.objects.all().order_by('id'))

        # 当前用户的实际权限数据
        user_perms = UserCompanyPermission.objects.filter(user=user).select_related('module', 'company')

        # 构建矩阵 dict {(company_id, module_id): permission_obj}
        perm_map = {
            (p.company_id, p.module_id): p
            for p in user_perms
        }

        # 构建结果：每条记录 = company × module 交叉格
        rows = []
        for company in companies:
            for module in modules:
                key = (company.id, module.id)
                perm = perm_map.get(key)
                rows.append({
                    'company_id': company.id,
                    'company_name': company.name,
                    'module_id': module.id,
                    'module_name': module.name,
                    'module_label': module.label,
                    'permission_id': perm.id if perm else None,
                    'is_primary': perm.is_primary if perm else False,
                    'can_view': perm.can_view if perm else False,
                    'can_create': perm.can_create if perm else False,
                    'can_edit': perm.can_edit if perm else False,
                    'can_delete': perm.can_delete if perm else False,
                    'can_approve': perm.can_approve if perm else False,
                    'has_record': perm is not None,
                })

        return Response({
            'user_id': user.id,
            'username': user.username,
            'is_superuser': user.is_superuser,
            'modules': list(modules.values('id', 'name', 'label', 'sort_order')),
            'companies': [{'id': c.id, 'name': c.name} for c in companies],
            'matrix': rows,
        })

    def create(self, request, user_pk=None):
        """为用户新增一条权限（company × module）"""
        user = get_object_or_404(User, pk=user_pk)
        serializer = UserCompanyPermissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        company_id = serializer.validated_data['company_id']
        module_id = serializer.validated_data['module']

        # 同一用户 × 公司 × 模块只允许一条记录
        existing = UserCompanyPermission.objects.filter(
            user=user, company_id=company_id, module_id=module_id
        ).first()
        if existing:
            return Response(
                {'detail': '该用户在该公司的该模块已有权限记录，请使用 PATCH 更新。'},
                status=400
            )

        # 如果设置了 is_primary=True，先取消该公司在该用户下的其他 primary
        if serializer.validated_data.get('is_primary'):
            UserCompanyPermission.objects.filter(
                user=user, company_id=company_id
            ).update(is_primary=False)

        serializer.save(user=user)
        return Response(serializer.data, status=201)

    @action(detail=False, methods=['patch'], url_path='batch')
    def batch_update(self, request, user_pk=None):
        """
        批量更新权限。
        请求体：{"permissions": [{"company_id": 1, "module_id": 1, "can_view": true, ...}, ...]}
        超管调用视为无操作（权限矩阵为只读，权限由系统自动授予）。
        """
        user = get_object_or_404(User, pk=user_pk)

        # 超管：权限由系统自动授予，batch_update 无意义
        if user.is_superuser:
            return Response({'detail': '超管拥有全部权限，无需通过矩阵配置。'}, status=200)

        serializer = BatchPermissionSerializer(data=request.data)
        if not serializer.is_valid():
            import sys; print(f'SERIALIZER ERRORS: {serializer.errors}', file=sys.stderr)
        serializer.is_valid(raise_exception=True)

        permissions = serializer.validated_data['permissions']

        # 空数组：视为无操作
        if not permissions:
            return Response({'detail': '没有需要保存的权限变更。'}, status=200)

        updated_ids = []
        for item in permissions:
            company_id = item['company_id']
            module_id = item['module_id']
            is_primary = item.get('is_primary', False)

            # 同一个 company × module 下只允许一条
            defaults = {
                'is_primary': is_primary,
                'can_view': item.get('can_view', False),
                'can_create': item.get('can_create', False),
                'can_edit': item.get('can_edit', False),
                'can_delete': item.get('can_delete', False),
                'can_approve': item.get('can_approve', False),
            }

            # 如果设置了 is_primary，先取消该公司下其他模块的 primary（同一公司只能有一个主体企业）
            if is_primary:
                UserCompanyPermission.objects.filter(
                    user=user, company_id=company_id
                ).exclude(module_id=module_id).update(is_primary=False)

            obj, created = UserCompanyPermission.objects.update_or_create(
                user=user,
                company_id=company_id,
                module_id=module_id,
                defaults=defaults,
            )
            updated_ids.append(obj.id)

        return Response({
            'detail': f'更新了 {len(updated_ids)} 条权限记录',
            'ids': updated_ids,
        })

    def partial_update(self, request, user_pk=None, pk=None):
        """更新单条权限"""
        perm = get_object_or_404(UserCompanyPermission, pk=pk, user_id=user_pk)

        # 如果设置了 is_primary，先取消该公司下其他 primary
        if request.data.get('is_primary'):
            UserCompanyPermission.objects.filter(
                user_id=user_pk, company_id=perm.company_id
            ).exclude(pk=pk).update(is_primary=False)

        for field in ['is_primary', 'can_view', 'can_create',
                      'can_edit', 'can_delete', 'can_approve']:
            if field in request.data:
                setattr(perm, field, request.data[field])
        perm.save()
        return Response(UserCompanyPermissionSerializer(perm).data)

    def destroy(self, request, user_pk=None, pk=None):
        """删除单条权限"""
        perm = get_object_or_404(UserCompanyPermission, pk=pk, user_id=user_pk)
        perm.delete()
        return Response(status=204)


class ModuleViewSet(viewsets.ReadOnlyModelViewSet):
    """
    模块列表 API（只读）。

    GET /api/permission-registry/modules/
    """
    queryset = Module.objects.filter(is_active=True).order_by('sort_order', 'name')
    serializer_class = ModuleSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=True, methods=['get'])
    def permissions(self, request, pk=None):
        module = self.get_object()
        perms = module.permissions.order_by('sort_order').values('id', 'name', 'label', 'sort_order')
        return Response({'module': ModuleSerializer(module).data, 'permissions': list(perms)})
