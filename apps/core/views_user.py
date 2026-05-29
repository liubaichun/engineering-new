import logging
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone

from apps.core.exceptions import api_error, ErrorCode

logger = logging.getLogger(__name__)


from .models import User, Notification, PermissionAuditLog, UserCompanyRole
from .serializers import UserSerializer
from apps.core.permissions import RoleRequired
from apps.core.export_excel import export_to_xlsx, make_export_response
from .views_common import get_client_ip


class UserViewSet(viewsets.ModelViewSet):
    """用户管理视图集"""

    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated, RoleRequired]
    action_perms = {
        None: 'system:user:read',
        'create': 'system:user:create',
        'update': 'system:user:update',
        'partial_update': 'system:user:update',
        'destroy': 'system:user:delete',
    }

    def get_permissions(self):
        return [permissions.IsAuthenticated(), RoleRequired()]

    def get_queryset(self):
        queryset = User.objects.all().prefetch_related(
            'company_roles__company',
            'company_roles__company_role',
        )
        role = self.request.query_params.get('role')
        is_active = self.request.query_params.get('is_active')
        last_login_since = self.request.query_params.get('last_login_since')  # 分钟内登录过

        if role:
            queryset = queryset.filter(role=role)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        if last_login_since:
            from django.utils import timezone
            from datetime import timedelta

            minutes = int(last_login_since)
            since = timezone.now() - timedelta(minutes=minutes)
            queryset = queryset.filter(last_login__gte=since)

        return queryset.order_by('-date_joined')

    @action(detail=True, methods=['post'])
    def reset_password(self, request, pk=None):
        """重置用户密码（管理员操作）"""
        user = self.get_object()
        new_password = request.data.get('new_password')

        if not new_password:
            return api_error(ErrorCode.VALIDATION_ERROR, '新密码不能为空')

        user.set_password(new_password)
        try:
            user.save(update_fields=['password'])
        except Exception as e:
            return Response(
                {'status': 'error', 'message': f'密码重置失败：{str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response({'status': 'success', 'message': '密码重置成功'}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def toggle_active(self, request, pk=None):
        """切换用户启用状态"""
        user = self.get_object()
        user.is_active = not user.is_active
        try:
            user.save(update_fields=['is_active'])
        except Exception as e:
            return Response(
                {'status': 'error', 'message': f'操作失败：{str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(
            {
                'status': 'success',
                'message': f'用户已{"启用" if user.is_active else "禁用"}',
                'user': UserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """批准用户注册 — 将 is_active 设为 True，自动建公司+分配公司管理员角色"""
        user = self.get_object()
        if user.is_active:
            return Response(
                {'status': 'error', 'message': '该用户已经激活，无需重复审批'}, status=status.HTTP_400_BAD_REQUEST
            )

        user.is_active = True
        try:
            user.save(update_fields=['is_active'])
        except Exception as e:
            return Response(
                {'status': 'error', 'message': f'审批失败：{str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # === 注册闭环：自动建公司+分配公司管理员角色 ===
        from apps.finance.models import Company

        # 检查用户是否已有公司（通过 UserCompanyRole 判断）
        existing_link = UserCompanyRole.objects.filter(user=user).first()
        if not existing_link:
            # 自动创建公司（以用户名作为公司名和代码）
            company_code = user.username.replace(' ', '_').replace('/', '_').lower()
            # 防止代码重复
            base_code = company_code
            counter = 1
            while Company.objects.filter(code=company_code).exists():
                company_code = f'{base_code}_{counter}'
                counter += 1
            company = Company.objects.create(
                name=f'{user.username}的公司',
                code=company_code,
                status='active',
                contact_person=user.username,
                contact_phone=user.phone or '',
            )

            # 分配公司管理员角色
            UserCompanyRole.objects.create(
                user=user,
                company=company,
                role='admin',
                assigned_by=request.user if request.user.is_authenticated else None,
            )

            # 审计日志
            PermissionAuditLog.objects.create(
                user=request.user if request.user.is_authenticated else None,
                action='assign_role',
                target_user=user,
                role_name='公司管理员',
                description=f'批准注册并创建公司[{company.name}]，分配公司管理员角色',
                ip_address=get_client_ip(request),
                company=company,
            )
        else:
            # 已有公司，单纯激活
            PermissionAuditLog.objects.create(
                user=request.user if request.user.is_authenticated else None,
                action='activate_user',
                target_user=user,
                description='批准用户注册（账号激活）',
                ip_address=get_client_ip(request),
                company=existing_link.company if existing_link else None,
            )

        # 给用户发通知
        Notification.objects.create(
            user=user,
            title='账号审批通过',
            content=f'您的账号 "{user.username}" 已通过管理员审批，现在可以正常登录了。',
            notification_type='approval',
            level='success',
            company=company if not existing_link else (existing_link.company if existing_link else None),
        )
        return Response(
            {
                'status': 'success',
                'message': f'已批准用户 {user.username} 的注册申请'
                + (f'，已创建公司[{company.name}]并分配公司管理员角色' if not existing_link else ''),
                'user': UserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """拒绝用户注册 — 删除该用户账号"""
        user = self.get_object()
        if user.is_active:
            return Response(
                {'status': 'error', 'message': '已激活账号无法执行拒绝操作'}, status=status.HTTP_400_BAD_REQUEST
            )

        username = user.username
        logger.warning(
            '[账号删除] action=reject_register, user_id=%s, username=%s, operator=%s, ip=%s',
            user.id,
            username,
            getattr(request.user, 'username', 'anonymous'),
            get_client_ip(request),
        )
        user.delete()
        return Response(
            {'status': 'success', 'message': f'已拒绝并删除用户 {username} 的注册申请'}, status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['post'])
    def approve_batch(self, request, pk=None):
        """批量批准用户注册 — 自动建公司+分配公司管理员角色"""
        user_ids = request.data.get('user_ids', [])
        if not user_ids:
            return api_error(ErrorCode.VALIDATION_ERROR, '未提供用户ID列表')

        from apps.finance.models import Company as FinanceCompany

        approved = []
        skipped = []
        for uid in user_ids:
            try:
                user = User.objects.get(id=uid, is_active=False)
            except User.DoesNotExist:
                skipped.append(f'ID:{uid}不存在')
                continue

            user.is_active = True
            try:
                user.save(update_fields=['is_active'])
            except Exception as e:
                logger.exception(f'批量激活用户失败：ID={uid}, error={e}')
                skipped.append(f'ID:{uid}保存失败')
                continue

            # 注册闭环
            existing_link = UserCompanyRole.objects.filter(user=user).first()
            if not existing_link:
                company_code = user.username.replace(' ', '_').replace('/', '_').lower()
                base_code = company_code
                counter = 1
                while FinanceCompany.objects.filter(code=company_code).exists():
                    company_code = f'{base_code}_{counter}'
                    counter += 1
                company = FinanceCompany.objects.create(
                    name=f'{user.username}的公司',
                    code=company_code,
                    status='active',
                    contact_person=user.username,
                    contact_phone=user.phone or '',
                )
                UserCompanyRole.objects.create(
                    user=user,
                    company=company,
                    role='admin',
                    assigned_by=request.user if request.user.is_authenticated else None,
                )
                PermissionAuditLog.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    action='assign_role',
                    target_user=user,
                    role_name='公司管理员',
                    description=f'批量批准注册并创建公司[{company.name}]，分配公司管理员角色',
                    ip_address=get_client_ip(request),
                    company=company,
                )
            else:
                PermissionAuditLog.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    action='activate_user',
                    target_user=user,
                    description='批量批准用户注册（账号激活）',
                    ip_address=get_client_ip(request),
                    company=existing_link.company if existing_link else None,
                )

            Notification.objects.create(
                user=user,
                title='账号审批通过',
                content=f'您的账号 "{user.username}" 已通过管理员审批，现在可以正常登录了。',
                notification_type='approval',
                level='success',
                company=company if not existing_link else (existing_link.company if existing_link else None),
            )
            approved.append(user.username)
        return Response(
            {
                'status': 'success',
                'message': f'批量批准完成：成功 {len(approved)} 个，失败 {len(skipped)} 个',
                'approved': approved,
                'skipped': skipped,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=['get'])
    def export(self, request):
        """导出用户 Excel"""
        records = list(self.get_queryset())
        rows = []
        role_map = {'admin': '管理员', 'manager': '经理', 'staff': '员工'}
        for u in records:
            rows.append(
                [
                    u.username,
                    u.email,
                    u.phone,
                    role_map.get(u.role, u.role or ''),
                    '是' if u.is_active else '否',
                    str(u.date_joined)[:19] if u.date_joined else '',
                    str(u.last_login)[:19] if u.last_login else '',
                ]
            )
        buf = export_to_xlsx(
            [
                {
                    'title': '用户列表',
                    'headers': ['用户名', '邮箱', '电话', '角色', '状态', '加入日期', '最后登录'],
                    'rows': rows,
                }
            ]
        )
        return make_export_response(buf, f'用户_{timezone.now().strftime("%Y%m%d")}.xlsx')
