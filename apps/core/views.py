from rest_framework import viewsets, filters, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from drf_spectacular.utils import extend_schema

from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import default_token_generator
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.conf import settings

from .models import User, Role, Permission, RolePermission, UserRole, Notification, PermissionAuditLog, LoginLog, UserCompanyRole, OperationAuditLog, SystemSetting
from apps.finance.models import Company as FinanceCompany
from .serializers import (
    UserRegisterSerializer,
    UserLoginSerializer,
    UserSerializer,
    UserRoleSerializer,
    RoleSerializer,
    PermissionSerializer,
    RolePermissionSerializer,
    NotificationSerializer,
    PermissionAuditLogSerializer,
    LoginLogSerializer,
    UserCompanyRoleSerializer,
    OperationAuditLogSerializer,
    SystemSettingSerializer,
    FinanceCompanySerializer,
)


def get_csrf_token(request):
    """获取CSRF token"""
    return {'csrf_token': get_token(request)}


def get_client_ip(request):
    """从请求中提取客户端IP"""
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


@method_decorator(csrf_exempt, name='dispatch')
class PasswordResetRequestView(APIView):
    """请求密码重置 - 发送邮件"""
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(tags=['auth'], summary='请求密码重置', description='输入邮箱，发送重置链接（即使邮箱不存在也返回成功，防止暴力探测）')
    def post(self, request):
        email = request.data.get('email', '').strip()
        if not email:
            return Response({'status': 'error', 'message': '邮箱不能为空'}, status=status.HTTP_400_BAD_REQUEST)

        users = User.objects.filter(email=email)
        # 即使邮箱不存在也返回成功，防止暴力猜测试探
        if users.exists():
            user = users.first()
            token = default_token_generator.make_token(user)
            uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
            reset_url = f"http://{request.get_host()}/password-reset/{uidb64}/{token}/"

            try:
                subject = '【企业信息化管理系统】密码重置验证码'
                message = f'''您好！

您申请了密码重置，请点击以下链接重置密码：

{reset_url}

如果这不是您本人操作，请忽略此邮件。

此链接30分钟内有效。'''
                send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=False)
                return Response({
                    'status': 'success',
                    'message': '重置链接已发送到您的邮箱，请查收。'
                })
            except Exception as e:
                return Response({
                    'status': 'error',
                    'message': f'邮件发送失败: {str(e)}'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            'status': 'success',
            'message': '如果该邮箱已注册，重置链接已发送。'
        })


class PasswordResetConfirmView(APIView):
    """确认密码重置 - 设置新密码"""
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(tags=['auth'], summary='确认密码重置', description='使用 uidb64/token 验证链接，设置新密码')
    def post(self, request, uidb64, token):
        new_password = request.data.get('new_password', '')
        confirm_password = request.data.get('confirm_password', '')

        if not new_password or not confirm_password:
            return Response({'status': 'error', 'message': '密码不能为空'}, status=status.HTTP_400_BAD_REQUEST)

        if new_password != confirm_password:
            return Response({'status': 'error', 'message': '两次密码不一致'}, status=status.HTTP_400_BAD_REQUEST)

        if len(new_password) < 8:
            return Response({'status': 'error', 'message': '密码至少8个字符'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response({'status': 'error', 'message': '无效的重置链接'}, status=status.HTTP_400_BAD_REQUEST)

        if not default_token_generator.check_token(user, token):
            return Response({'status': 'error', 'message': '链接已过期，请重新申请'}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()
        return Response({'status': 'success', 'message': '密码重置成功，请使用新密码登录。'})


class RegisterView(APIView):
    """用户注册视图"""
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(tags=['auth'], summary='用户注册', description='提交注册信息（买断版默认关闭注册入口），管理员审批后账号生效')
    def post(self, request):
        # 买断版关闭注册
        from django.conf import settings
        if getattr(settings, 'TENANT_MODE', 'subscription') == 'standalone':
            return Response(
                {'status': 'error', 'message': '注册入口已关闭，请联系系统管理员。'},
                status=status.HTTP_403_FORBIDDEN
            )
        serializer = UserRegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({
                'status': 'pending',
                'message': '注册成功，您的账号正在等待管理员审批，审批通过后即可登录。',
                'user': UserSerializer(user).data,
            }, status=status.HTTP_201_CREATED)
        return Response({
            'status': 'error',
            'message': '注册失败',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


@method_decorator(csrf_exempt, name='dispatch')
@extend_schema(tags=['auth'], summary='用户登录', description='用户名+密码登录，返回会话Cookie')
class LoginView(APIView):
    """用户登录视图"""
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(tags=['auth'], summary='用户登录', description='POST username/password，返回会话Cookie')
    def post(self, request):
        x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded:
            return x_forwarded.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')

    def _log_login(self, request, username, status, user=None, fail_reason=''):
        LoginLog.objects.create(
            user=user,
            username=username,
            status=status,
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
            fail_reason=fail_reason,
        )

    def post(self, request):
        serializer = UserLoginSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            user = serializer.validated_data['user']
            login(request, user)
            # 支持"30天内自动登录"记住我
            remember = request.data.get('remember', False)
            if remember in (True, 'true', '1', 'on'):
                request.session.set_expiry(60 * 60 * 24 * 30)  # 30天
            else:
                request.session.set_expiry(0)  # 浏览器关闭失效
            self._log_login(request, user.username, 'success', user=user)
            response = JsonResponse({
                'status': 'success',
                'message': '登录成功',
                'user': UserSerializer(user).data,
            })
            # 设置 csrftoken cookie，后续POST请求需要
            response.set_cookie('csrftoken', get_token(request))
            return response
        # 登录失败
        username = request.data.get('username', '')
        errors = serializer.errors
        if 'non_field_errors' in errors:
            fail_reason = str(errors['non_field_errors'][0])
        else:
            fail_reason = '用户名或密码错误'
        self._log_login(request, username, 'failed', fail_reason=fail_reason)
        return Response({
            'status': 'error',
            'message': '登录失败',
            'errors': errors
        }, status=status.HTTP_400_BAD_REQUEST)


class LogoutView(APIView):
    """用户登出视图"""
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=['auth'], summary='用户登出', description='清除会话Cookie')
    def post(self, request):
        logout(request)
        return Response({
            'status': 'success',
            'message': '已退出登录'
        }, status=status.HTTP_200_OK)


class ChangePasswordView(APIView):
    """修改密码视图 - POST /api/core/auth/password/"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        # DEBUG
        import sys
        print(f"DEBUG request.data = {dict(request.data)}", flush=True)
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password') or request.data.get('new_password1')
        confirm_password = request.data.get('new_password2')

        if not old_password or not new_password:
            return Response({
                'status': 'error',
                'message': '旧密码和新密码都不能为空'
            }, status=status.HTTP_400_BAD_REQUEST)

        if confirm_password and new_password != confirm_password:
            return Response({
                'status': 'error',
                'message': '两次输入的新密码不一致'
            }, status=status.HTTP_400_BAD_REQUEST)

        # 密码强度校验
        pwd = new_password
        if len(pwd) < 8:
            return Response({'status': 'error', 'message': '密码至少需要8个字符'}, status=status.HTTP_400_BAD_REQUEST)
        if not any(c.isupper() for c in pwd):
            return Response({'status': 'error', 'message': '密码必须包含至少一个大写字母'}, status=status.HTTP_400_BAD_REQUEST)
        if not any(c.islower() for c in pwd):
            return Response({'status': 'error', 'message': '密码必须包含至少一个小写字母'}, status=status.HTTP_400_BAD_REQUEST)
        if not any(c.isdigit() for c in pwd):
            return Response({'status': 'error', 'message': '密码必须包含至少一个数字'}, status=status.HTTP_400_BAD_REQUEST)

        user = request.user

        if not user.check_password(old_password):
            return Response({
                'status': 'error',
                'message': '旧密码不正确'
            }, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save(update_fields=['password'])

        # 重新登录保持会话
        login(request, user)

        return Response({
            'status': 'success',
            'message': '密码修改成功'
        }, status=status.HTTP_200_OK)


class CurrentUserView(APIView):
    """当前用户信息视图"""
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=['auth'], summary='获取当前用户信息', description='返回当前登录用户的信息，包括用户名/邮箱/角色/公司/权限码列表')
    def get(self, request):
        """GET /api/core/auth/user/ - 返回当前用户信息"""
        serializer = UserSerializer(request.user)
        return Response({
            'status': 'success',
            'user': serializer.data
        }, status=status.HTTP_200_OK)

    def put(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({
                'status': 'success',
                'message': '更新成功',
                'user': serializer.data
            }, status=status.HTTP_200_OK)
        return Response({
            'status': 'error',
            'message': '更新失败',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def switch_company(self, request):
        """切换当前活跃公司 — POST /api/core/auth/user/switch_company/
        请求体: {company_id: int}
        """
        company_id = request.data.get('company_id')
        if not company_id:
            return Response({'status': 'error', 'message': 'company_id 不能为空'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            company_id = int(company_id)
        except (ValueError, TypeError):
            return Response({'status': 'error', 'message': 'company_id 必须是整数'}, status=status.HTTP_400_BAD_REQUEST)

        # 验证用户是否属于该公司
        link = UserCompanyRole.objects.filter(user=request.user, company_id=company_id).first()
        if not link:
            return Response({'status': 'error', 'message': '您不属于该公司，无权访问'}, status=status.HTTP_403_FORBIDDEN)

        # 切换成功（这里把当前公司ID存在 session 中）
        request.session['current_company_id'] = company_id
        return Response({
            'status': 'success',
            'message': '已切换到公司',
            'current_company_id': company_id,
            'company_name': link.company.name,
            'role': link.role,
            'role_display': link.get_role_display(),
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def my_companies(self, request):
        """获取当前用户可访问的公司列表 — GET /api/core/auth/user/my_companies/"""
        links = UserCompanyRole.objects.filter(user=request.user)
        current_company_id = request.session.get('current_company_id')
        data = []
        for link in links:
            data.append({
                'company_id': link.company_id,
                'company_name': link.company.name,
                'role': link.role,
                'role_display': link.get_role_display(),
                'is_current': link.company_id == current_company_id,
            })
        return Response({'status': 'success', 'companies': data}, status=status.HTTP_200_OK)


class MyPermissionsView(APIView):
    """当前用户权限列表（用于前端按钮级权限控制）"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.is_superuser:
            perms = Permission.objects.all()
        else:
            user_roles = UserRole.objects.filter(user=user, user__is_active=True)
            role_ids = list(user_roles.values_list('role_id', flat=True))
            role_perms = RolePermission.objects.filter(role_id__in=role_ids)
            perm_ids = list(set(role_perms.values_list('permission_id', flat=True)))
            perms = Permission.objects.filter(id__in=perm_ids)
        codes = list(perms.values_list('code', flat=True))
        return Response({
            'status': 'success',
            'codes': codes,
        }, status=status.HTTP_200_OK)


class UserViewSet(viewsets.ModelViewSet):
    """用户管理视图集"""
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = User.objects.all()
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
            return Response({
                'status': 'error',
                'message': '新密码不能为空'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        user.set_password(new_password)
        user.save(update_fields=['password'])
        
        return Response({
            'status': 'success',
            'message': '密码重置成功'
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def toggle_active(self, request, pk=None):
        """切换用户启用状态"""
        user = self.get_object()
        user.is_active = not user.is_active
        user.save(update_fields=['is_active'])

        return Response({
            'status': 'success',
            'message': f'用户已{"启用" if user.is_active else "禁用"}',
            'user': UserSerializer(user).data
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """批准用户注册 — 将 is_active 设为 True，自动建公司+分配公司管理员角色"""
        user = self.get_object()
        if user.is_active:
            return Response({
                'status': 'error',
                'message': '该用户已经激活，无需重复审批'
            }, status=status.HTTP_400_BAD_REQUEST)

        user.is_active = True
        user.save(update_fields=['is_active'])

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
            )
        else:
            # 已有公司，单纯激活
            PermissionAuditLog.objects.create(
                user=request.user if request.user.is_authenticated else None,
                action='activate_user',
                target_user=user,
                description='批准用户注册（账号激活）',
                ip_address=get_client_ip(request),
            )

        # 给用户发通知
        Notification.objects.create(
            user=user,
            title='账号审批通过',
            content=f'您的账号 "{user.username}" 已通过管理员审批，现在可以正常登录了。',
            notification_type='approval',
            level='success',
        )
        return Response({
            'status': 'success',
            'message': f'已批准用户 {user.username} 的注册申请' + (f'，已创建公司[{company.name}]并分配公司管理员角色' if not existing_link else ''),
            'user': UserSerializer(user).data
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """拒绝用户注册 — 删除该用户账号"""
        user = self.get_object()
        if user.is_active:
            return Response({
                'status': 'error',
                'message': '已激活账号无法执行拒绝操作'
            }, status=status.HTTP_400_BAD_REQUEST)

        username = user.username
        user.delete()
        return Response({
            'status': 'success',
            'message': f'已拒绝并删除用户 {username} 的注册申请'
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def approve_batch(self, request, pk=None):
        """批量批准用户注册 — 自动建公司+分配公司管理员角色"""
        user_ids = request.data.get('user_ids', [])
        if not user_ids:
            return Response({'status': 'error', 'message': '未提供用户ID列表'}, status=status.HTTP_400_BAD_REQUEST)

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
            user.save(update_fields=['is_active'])

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
                    user=user, company=company, role='admin',
                    assigned_by=request.user if request.user.is_authenticated else None,
                )
                PermissionAuditLog.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    action='assign_role', target_user=user, role_name='公司管理员',
                    description=f'批量批准注册并创建公司[{company.name}]，分配公司管理员角色',
                    ip_address=get_client_ip(request),
                )
            else:
                PermissionAuditLog.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    action='activate_user', target_user=user,
                    description='批量批准用户注册（账号激活）',
                    ip_address=get_client_ip(request),
                )

            Notification.objects.create(
                user=user,
                title='账号审批通过',
                content=f'您的账号 "{user.username}" 已通过管理员审批，现在可以正常登录了。',
                notification_type='approval',
                level='success',
            )
            approved.append(user.username)
        return Response({
            'status': 'success',
            'message': f'批量批准完成：成功 {len(approved)} 个，失败 {len(skipped)} 个',
            'approved': approved,
            'skipped': skipped,
        }, status=status.HTTP_200_OK)


class RoleViewSet(viewsets.ModelViewSet):
    """角色管理视图集"""
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = Role.objects.all()
        is_active = self.request.query_params.get('is_active')
        
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        return queryset.order_by('-created_at')
    
    @action(detail=True, methods=['get'])
    def permissions(self, request, pk=None):
        """获取角色的所有权限"""
        role = self.get_object()
        role_permissions = RolePermission.objects.filter(role=role)
        serializer = RolePermissionSerializer(role_permissions, many=True)
        return Response({
            'status': 'success',
            'permissions': serializer.data
        }, status=status.HTTP_200_OK)


class PermissionViewSet(viewsets.ModelViewSet):
    """权限管理视图集"""
    queryset = Permission.objects.all()
    serializer_class = PermissionSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = Permission.objects.all()
        resource = self.request.query_params.get('resource')
        action = self.request.query_params.get('action')
        is_active = self.request.query_params.get('is_active')
        
        if resource:
            queryset = queryset.filter(resource=resource)
        if action:
            queryset = queryset.filter(action=action)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        return queryset.order_by('resource', 'action')
    
    @action(detail=False, methods=['get'])
    def resources(self, request):
        """获取所有资源路径"""
        resources = Permission.objects.values_list('resource', flat=True).distinct()
        return Response({
            'status': 'success',
            'resources': list(resources)
        }, status=status.HTTP_200_OK)


class RolePermissionViewSet(viewsets.ModelViewSet):
    """角色权限关联视图集"""
    queryset = RolePermission.objects.all()
    serializer_class = RolePermissionSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = RolePermission.objects.all()
        role_id = self.request.query_params.get('role')
        permission_id = self.request.query_params.get('permission')
        
        if role_id:
            queryset = queryset.filter(role_id=role_id)
        if permission_id:
            queryset = queryset.filter(permission_id=permission_id)
        
        return queryset.select_related('role', 'permission')
    
    def create(self, request, *args, **kwargs):
        """创建角色权限关联"""
        role_id = request.data.get('role')
        permission_id = request.data.get('permission')

        if RolePermission.objects.filter(role_id=role_id, permission_id=permission_id).exists():
            return Response({
                'status': 'error',
                'message': '该角色已有此权限'
            }, status=status.HTTP_400_BAD_REQUEST)

        return super().create(request, *args, **kwargs)

    @action(detail=False, methods=['post'], url_path='toggle')
    def toggle(self, request):
        """切换角色权限（添加或移除）"""
        role_id = request.data.get('role_id')
        permission_id = request.data.get('permission_id')
        granted = request.data.get('granted', True)

        if not role_id or not permission_id:
            return Response({'status': 'error', 'message': 'role_id和permission_id必填'},
                          status=status.HTTP_400_BAD_REQUEST)

        if granted:
            obj, created = RolePermission.objects.get_or_create(
                role_id=role_id,
                permission_id=permission_id,
                defaults={'permission_type': 'allow'}
            )
            return Response({
                'status': 'success',
                'action': 'added' if created else 'already_exists'
            })
        else:
            deleted, _ = RolePermission.objects.filter(
                role_id=role_id,
                permission_id=permission_id
            ).delete()
            return Response({
                'status': 'success',
                'action': 'removed' if deleted else 'not_found'
            })

    @action(detail=False, methods=['post'], url_path='assign_permissions')
    def assign_permissions(self, request):
        """批量分配权限到角色"""
        role_id = request.data.get('role_id')
        permission_ids = request.data.get('permission_ids', [])
        permission_type = request.data.get('permission_type', 'allow')

        if not role_id:
            return Response({'status': 'error', 'message': 'role_id必填'},
                          status=status.HTTP_400_BAD_REQUEST)

        if not permission_ids:
            return Response({'status': 'error', 'message': 'permission_ids必填'},
                          status=status.HTTP_400_BAD_REQUEST)

        created_count = 0
        for perm_id in permission_ids:
            obj, created = RolePermission.objects.get_or_create(
                role_id=role_id,
                permission_id=perm_id,
                defaults={'permission_type': permission_type}
            )
            if created:
                created_count += 1

        return Response({
            'status': 'success',
            'created': created_count,
            'total': len(permission_ids)
        })


class UserRoleViewSet(viewsets.ModelViewSet):
    """用户角色关联视图集"""
    queryset = UserRole.objects.all()
    serializer_class = UserRoleSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = UserRole.objects.all()
        user_id = self.request.query_params.get('user')
        role_id = self.request.query_params.get('role')
        
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        if role_id:
            queryset = queryset.filter(role_id=role_id)
        
        return queryset.select_related('user', 'role', 'assigned_by')
    
    def create(self, request, *args, **kwargs):
        """创建用户角色关联"""
        user_id = request.data.get('user')
        role_id = request.data.get('role')
        
        if UserRole.objects.filter(user_id=user_id, role_id=role_id).exists():
            return Response({
                'status': 'error',
                'message': '该用户已有此角色'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not request.data.get('assigned_by'):
            request.data['assigned_by'] = request.user.id
        
        return super().create(request, *args, **kwargs)
    
    @action(detail=False, methods=['get'], url_path='by-user/(?P<user_id>[^/.]+)')
    def by_user(self, request, user_id=None):
        """获取指定用户的所有角色"""
        user_roles = UserRole.objects.filter(user_id=user_id).select_related('role')
        serializer = self.get_serializer(user_roles, many=True)
        return Response({
            'status': 'success',
            'user_roles': serializer.data
        }, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'], url_path='by-role/(?P<role_id>[^/.]+)')
    def by_role(self, request, role_id=None):
        """获取指定角色的所有用户"""
        role_users = UserRole.objects.filter(role_id=role_id).select_related('user')
        serializer = self.get_serializer(role_users, many=True)
        return Response({
            'status': 'success',
            'role_users': serializer.data
        }, status=status.HTTP_200_OK)


class NotificationViewSet(viewsets.ModelViewSet):
    """通知消息视图集"""
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = Notification.objects.filter(user=self.request.user)
        is_read = self.request.query_params.get('is_read')
        notification_type = self.request.query_params.get('type')
        
        if is_read is not None:
            queryset = queryset.filter(is_read=is_read.lower() == 'true')
        if notification_type:
            queryset = queryset.filter(notification_type=notification_type)
        
        return queryset.select_related('user')
    
    @action(detail=True, methods=['post'], url_path='mark-read')
    def mark_read(self, request, pk=None):
        """标记单条通知为已读"""
        notification = self.get_object()
        notification.is_read = True
        notification.save(update_fields=['is_read'])
        return Response({'status': 'success'})
    
    @action(detail=False, methods=['post'], url_path='mark-all-read')
    def mark_all_read(self, request):
        """标记所有通知为已读"""
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({'status': 'success', 'message': '所有通知已标记为已读'})
    
    @action(detail=False, methods=['get'], url_path='unread-count')
    def unread_count(self, request):
        """获取未读通知数量"""
        count = Notification.objects.filter(user=request.user, is_read=False).count()
        return Response({'unread_count': count})
    
    @action(detail=False, methods=['delete'], url_path='clear-read')
    def clear_read(self, request):
        """清除所有已读通知"""
        deleted, _ = Notification.objects.filter(user=request.user, is_read=True).delete()
        return Response({'status': 'success', 'deleted': deleted})


class PermissionAuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """权限审计日志视图集（仅读）"""
    queryset = PermissionAuditLog.objects.all()
    serializer_class = PermissionAuditLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = PermissionAuditLog.objects.select_related('user', 'target_user', 'role', 'permission')
        # 过滤：操作人/目标用户/操作类型/角色
        target_user_id = self.request.query_params.get('target_user')
        action = self.request.query_params.get('action')
        role_id = self.request.query_params.get('role')
        if target_user_id:
            queryset = queryset.filter(target_user_id=target_user_id)
        if action:
            queryset = queryset.filter(action=action)
        if role_id:
            queryset = queryset.filter(role_id=role_id)
        return queryset


class LoginLogViewSet(viewsets.ReadOnlyModelViewSet):
    """登录日志视图集（仅读）"""
    queryset = LoginLog.objects.all()
    serializer_class = LoginLogSerializer
    permission_classes = [permissions.IsAuthenticated]
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


class OperationAuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    操作审计日志视图集（仅读）
    支持按 app_label / action / username / date_from / date_to 筛选
    """
    queryset = OperationAuditLog.objects.all()
    serializer_class = OperationAuditLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['username', 'object_repr', 'app_label', 'model_name']
    ordering_fields = ['created_at', 'action']
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = OperationAuditLog.objects.select_related('user')
        # 仅管理员可查看全部审计日志
        if not self.request.user.is_superuser:
            return queryset.none()

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


class SystemSettingViewSet(viewsets.ModelViewSet):
    """系统参数管理视图集"""
    queryset = SystemSetting.objects.all()
    serializer_class = SystemSettingSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'key'

    def get_queryset(self):
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
    def all_settings(self, request):
        """获取所有系统参数的键值对字典 — GET /api/core/settings/all_settings/"""
        settings = {s.key: s.value for s in SystemSetting.objects.all()}
        return Response({'status': 'success', 'settings': settings}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def health_check(self, request):
        """外部依赖健康检查 — GET /api/core/settings/health_check/"""
        return Response({'status': 'ok', 'test': True})

    def update(self, request, *args, **kwargs):
        """PATCH /api/core/settings/{key}/ — 更新单个参数"""
        instance = self.get_object()
        new_value = request.data.get('value')
        if new_value is None:
            return Response({'status': 'error', 'message': 'value 不能为空'},
                          status=status.HTTP_400_BAD_REQUEST)
        instance.value = new_value
        instance.save(update_fields=['value', 'updated_at'])
        return Response({
            'status': 'success',
            'message': '设置已更新',
            'data': SystemSettingSerializer(instance).data
        }, status=status.HTTP_200_OK)

    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)


class FinanceCompanyViewSet(viewsets.ModelViewSet):
    """公司信息管理视图集"""
    queryset = FinanceCompany.objects.all()
    serializer_class = FinanceCompanySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = FinanceCompany.objects.all()
        status = self.request.query_params.get('status')
        if status:
            queryset = queryset.filter(status=status)
        return queryset.order_by('-created_at')

    @action(detail=False, methods=['get'])
    def active(self, request):
        """获取所有启用状态的公司"""
        companies = FinanceCompany.objects.filter(status='active').order_by('name')
        return Response({
            'status': 'success',
            'companies': FinanceCompanySerializer(companies, many=True).data
        }, status=status.HTTP_200_OK)
