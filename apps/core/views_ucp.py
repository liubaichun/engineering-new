import logging
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

logger = logging.getLogger(__name__)

from .models import Module, ModuleAction, UserModulePermission, ACTION_BITS
from apps.finance.models import Company as FinanceCompany
from apps.core.exceptions import api_error, ErrorCode
from apps.core.permissions import RoleRequired


class UserCompanyPermissionViewSet(viewsets.ViewSet):
    """
    用户公司权限矩阵 — 读写 UMP 位掩码。

    权限矩阵页面调用：
    GET  /api/core/user-company-permissions/matrix/?user_id=X  → 矩阵数据
    POST /api/core/user-company-permissions/matrix_bulk_update/ → 批量更新

    2026-06-02: 移除旧UCP CRUD，统一使用UMP位掩码
    """

    permission_classes = [permissions.IsAuthenticated, RoleRequired]
    # 矩阵管理需要 admin 角色
    required_roles = ['admin']

    @action(detail=False, methods=['get'])
    def matrix(self, request):
        """
        权限矩阵页核心接口（从 UMP 位掩码读取）。

        GET /api/core/user-company-permissions/matrix/?user_id=X

        返回：
        {
          modules: [{id, name, label, category, actions: [{id, name, label}]}],
          companies: [{id, name}],
          matrix: [{user_id, company_id, module_id, action_id, is_granted, has_record}]
        }
        为兼容旧 UI，matrix 数据按 action 展开为 flat 格式。
        """
        user_id = request.query_params.get('user_id')
        if not user_id:
            return Response({'detail': 'user_id 是必填参数'}, status=status.HTTP_400_BAD_REQUEST)

        # 所有模块 + 动作（按 sort_order 排序）
        modules = Module.objects.filter(is_active=True).prefetch_related('actions').order_by('sort_order')
        module_data = []
        for m in modules:
            module_data.append(
                {
                    'id': m.id,
                    'name': m.name,
                    'label': m.label,
                    'icon': m.icon,
                    'category': m.category,
                    'sort_order': m.sort_order,
                    'actions': [
                        {'id': a.id, 'name': a.name, 'label': a.label, 'action_group': a.action_group}
                        for a in m.actions.all().order_by('action_group', 'sort_order')
                    ],
                }
            )

        # 所有公司 — 非超管只显示有权限的公司
        user = self.request.user
        companies_qs = FinanceCompany.objects.filter(status='active').order_by('name')
        if not user.is_superuser:
            from apps.core.permissions import get_module_companies

            company_ids = get_module_companies(user, 'permission_matrix', 'read')
            if company_ids:
                companies_qs = companies_qs.filter(id__in=company_ids)
            else:
                companies_qs = companies_qs.none()
        companies = list(companies_qs.values('id', 'name'))

        # 从 UMP 位掩码展开为 flat 格式（兼容旧 UI）
        matrix_records = []
        ump_records = UserModulePermission.objects.filter(user_id=user_id).select_related('module')

        for ump in ump_records:
            for action_name, bit in ACTION_BITS.items():
                if action_name == '_RESERVED':
                    continue
                # 找到对应的 ModuleAction id
                try:
                    action_obj = ModuleAction.objects.get(module=ump.module, name=action_name)
                    is_granted = bool(ump.granted_bits & bit)
                    matrix_records.append(
                        {
                            'user_id': int(user_id),
                            'company_id': ump.company_id,
                            'module_id': ump.module_id,
                            'action_id': action_obj.id,
                            'is_granted': is_granted,
                            'has_record': True,
                        }
                    )
                except ModuleAction.DoesNotExist:
                    pass

        return Response(
            {
                'modules': module_data,
                'companies': companies,
                'matrix': matrix_records,
            }
        )

    @action(detail=False, methods=['post'])
    def matrix_bulk_update(self, request):
        """
        批量更新权限矩阵（写入 UMP 位掩码）。

        POST /api/core/user-company-permissions/matrix_bulk_update/
        Body: {
          user_id: int,
          updates: [
            {company_id, module_name, action_name, is_granted: bool},
            ...
          ]
        }
        """
        user_id = request.data.get('user_id')
        updates = request.data.get('updates', [])
        if not user_id or not updates:
            return Response({'detail': 'user_id 和 updates 是必填参数'}, status=status.HTTP_400_BAD_REQUEST)

        # 权限校验
        if not request.user.is_superuser and request.user.id != int(user_id):
            return Response({'detail': '您没有权限修改他人的权限'}, status=status.HTTP_403_FORBIDDEN)

        # 预加载所有 Module/Action
        modules = {m.name: m.id for m in Module.objects.all()}
        # 反向映射：id → name
        module_names = {v: k for k, v in modules.items()}
        action_names = {a.id: a.name for a in ModuleAction.objects.all()}

        updated = []
        for upd in updates:
            company_id = upd['company_id']
            if 'module_name' in upd:
                module_id = modules.get(upd['module_name'])
            else:
                module_id = upd.get('module_id')
            if 'action_name' in upd:
                module_for_action = upd.get('module_name') or module_names.get(upd.get('module_id'))
                if module_for_action:
                    action_id = (
                        ModuleAction.objects.filter(module__name=module_for_action, name=upd['action_name'])
                        .values_list('id', flat=True)
                        .first()
                    )
                else:
                    action_id = None
            else:
                action_id = upd.get('action_id')

            if not module_id or not action_id:
                return Response(
                    {
                        'detail': f'找不到模块或动作: module={upd.get("module_name", upd.get("module_id"))}, action={upd.get("action_name", upd.get("action_id"))}'
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # 获取 action_name 和对应的 bit
            action_name = action_names[action_id]
            bit = ACTION_BITS.get(action_name)
            if not bit:
                return Response({'detail': f'未知动作: {action_name}'}, status=status.HTTP_400_BAD_REQUEST)

            # 使用 UMP 位掩码
            ump, ump_created = UserModulePermission.objects.get_or_create(
                user_id=user_id,
                company_id=company_id,
                module_id=module_id,
                defaults={'granted_bits': 0},
            )

            if upd['is_granted']:
                ump.granted_bits |= bit  # 设置 bit
            else:
                ump.granted_bits &= ~bit  # 清除 bit

            if ump.granted_bits == 0:
                ump.delete()  # 全空 → 删记录
            else:
                try:
                    ump.save()
                except Exception as e:
                    return api_error(ErrorCode.INTERNAL_ERROR, f'保存权限失败：{str(e)}', status_code=500)

            updated.append(
                {
                    'company_id': company_id,
                    'module_id': module_id,
                    'action_id': action_id,
                    'is_granted': upd['is_granted'],
                }
            )

        return Response(
            {
                'updated': len(updated),
                'records': updated,
            }
        )
