import logging
from rest_framework import viewsets, filters, status, permissions, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from apps.core.auth import CSRFExemptSessionAuthentication
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

from .models import User, Notification, Permission, PermissionAuditLog, LoginLog, UserCompanyRole, OperationAuditLog, SystemSetting, UserCompanyPermission, Module, ModuleAction, CompanyRole, Role, RolePermission
from .permissions import RoleRequired
from apps.finance.models import Company as FinanceCompany

logger = logging.getLogger(__name__)

from .serializers import (
    UserRegisterSerializer,
    UserLoginSerializer,
    UserSerializer,
    NotificationSerializer,
    PermissionSerializer,
    PermissionListSerializer,
    ModuleActionSerializer,
    PermissionAuditLogSerializer,
    LoginLogSerializer,
    UserCompanyRoleSerializer,
    OperationAuditLogSerializer,
    SystemSettingSerializer,
    FinanceCompanySerializer,
    UserCompanyPermissionSerializer,
    CompanyRoleSerializer,
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
        # 登录时从用户公司角色取默认公司（传 FK 实例而非 _id）
        company = None
        if user:
            link = user.company_roles.all().first()
            if link:
                company = link.company
        LoginLog.objects.create(
            user=user,
            username=username,
            status=status,
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
            fail_reason=fail_reason,
            company=company,
        )

    def post(self, request):
        serializer = UserLoginSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            user = serializer.validated_data['user']
            login(request, user)
            # 登录时设置当前公司上下文
            link = user.company_roles.all().first()
            if link:
                request.session['current_company_id'] = link.company_id
            # 支持"30天内自动登录"记住我
            remember = request.data.get('remember', False)
            if remember in (True, 'true', '1', 'on'):
                request.session.set_expiry(60 * 60 * 24 * 30)  # 30天
            else:
                request.session.set_expiry(0)  # 浏览器关闭失效
            self._log_login(request, user.username, 'success', user=user)
            user_data = UserSerializer(user).data
            user_data['require_password_change'] = not user.password_changed
            response = JsonResponse({
                'status': 'success',
                'message': '登录成功',
                'user': user_data,
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
    permission_classes = [permissions.IsAuthenticated, RoleRequired]

    @extend_schema(tags=['auth'], summary='用户登出', description='清除会话Cookie')
    def post(self, request):
        logout(request)
        return Response({
            'status': 'success',
            'message': '已退出登录'
        }, status=status.HTTP_200_OK)


class ChangePasswordView(APIView):
    """修改密码视图 - POST /api/core/auth/password/"""
    permission_classes = [permissions.IsAuthenticated, RoleRequired]

    def post(self, request):
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
        user.password_changed = True
        user.save(update_fields=['password', 'password_changed'])

        # 再刷新 session auth hash（用新密码哈希更新 session，否则后续请求 session 验证失败）
        from django.contrib.auth import update_session_auth_hash
        update_session_auth_hash(request, user)

        return Response({
            'status': 'success',
            'message': '密码修改成功'
        }, status=status.HTTP_200_OK)


class CurrentUserView(APIView):
    """当前用户信息视图"""
    permission_classes = [permissions.IsAuthenticated, RoleRequired]

    @extend_schema(tags=['auth'], summary='获取当前用户信息', description='返回当前登录用户的信息，包括用户名/邮箱/角色/公司/权限码列表')
    def get(self, request):
        """GET /api/core/auth/user/ - 返回当前用户信息"""
        serializer = UserSerializer(request.user)
        return Response({
            'status': 'success',
            'user': serializer.data,
            'user_id': request.user.id,
            'is_superuser': request.user.is_superuser,
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
    permission_classes = [permissions.IsAuthenticated, RoleRequired]

    # action 映射：UCP标准action → 前端权限码格式
    _ACTION_MAP = {'create': 'add', 'update': 'change', 'delete': 'delete', 'read': 'view'}
    # DRF权限码的 category→module 映射（DRF格式用 category:resource:action）
    # UCP的module名 → 对应的DRF category前缀
    _CATEGORY_MODULE_MAP = {
        'material': 'material',  # stock模块 → material前缀（资源名=stock）
        'crm': 'crm',            # customer模块 → crm前缀（资源名=customer）
        'approval': 'approval',   # flow模块 → approval前缀（资源名=flow）
        'customer': 'crm',        # customer模块在finance/crm app → crm category
        'stock': 'material',     # stock模块在material app → material category
        'flow': 'approval',       # flow模块在approvals app → approval category
    }

    def _generate_codes_from_ucp(self, user, company_id):
        """从 UserCompanyPermission 生成前端权限码（两种格式）"""
        from apps.core.models import UserCompanyPermission
        ucp_qs = UserCompanyPermission.objects.filter(
            user=user, company_id=company_id, is_granted=True
        ).select_related('module', 'action')

        codes = set()
        for r in ucp_qs:
            action_name = r.action.name
            mapped = self._ACTION_MAP.get(action_name)
            if mapped:
                # 格式1: module.action （如 equipment.add）
                codes.add(f'{r.module.name}.{mapped}')
                # 格式2: category:resource:action （如 crm:customer:create）
                # resource 名 = _CATEGORY_MODULE_MAP.get(module_name, module_name)
                resource = self._CATEGORY_MODULE_MAP.get(r.module.name, r.module.name)
                codes.add(f'{r.module.name}:{resource}:{action_name}')
        return codes

    def get(self, request):
        user = request.user
        # 获取公司ID：优先从session，其次从UserCompanyRole第一笔
        company_id = request.session.get('current_company_id')
        if not company_id:
            from apps.core.models import UserCompanyRole
            first_link = UserCompanyRole.objects.filter(user=user).first()
            company_id = first_link.company_id if first_link else None

        if user.is_superuser:
            from apps.core.models import ModuleAction
            codes = list(ModuleAction.objects.values_list('code', flat=True).distinct())
        elif company_id:
            codes = list(self._generate_codes_from_ucp(user, company_id))
        else:
            codes = []

        return Response({
            'status': 'success',
            'codes': codes,
            'user_id': user.id,
            'is_superuser': user.is_superuser,
        }, status=status.HTTP_200_OK)


class UserViewSet(viewsets.ModelViewSet):
    """用户管理视图集"""
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated(), RoleRequired()]

    def get_queryset(self):
        from django.db.models import Prefetch
        from apps.finance.models import Company
        queryset = User.objects.all().prefetch_related(
            'company_roles__company',
            'user_roles__role',
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
        logger.warning(
            "[账号删除] action=reject_register, user_id=%s, username=%s, "
            "operator=%s, ip=%s",
            user.id, username,
            getattr(request.user, 'username', 'anonymous'),
            get_client_ip(request)
        )
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
                    company=company,
                )
            else:
                PermissionAuditLog.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    action='activate_user', target_user=user,
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
        return Response({
            'status': 'success',
            'message': f'批量批准完成：成功 {len(approved)} 个，失败 {len(skipped)} 个',
            'approved': approved,
            'skipped': skipped,
        }, status=status.HTTP_200_OK)


    @action(detail=False, methods=['get'])
    def export(self, request):
        """导出用户 Excel"""
        from apps.core.export_excel import export_to_xlsx, make_export_response
        from django.contrib.auth import get_user_model
        User = get_user_model()
        records = list(self.get_queryset())
        rows = []
        role_map = {'admin': '管理员', 'manager': '经理', 'staff': '员工'}
        for u in records:
            rows.append([
                u.username,
                u.email,
                u.phone,
                role_map.get(u.role, u.role or ''),
                '是' if u.is_active else '否',
                str(u.date_joined)[:19] if u.date_joined else '',
                str(u.last_login)[:19] if u.last_login else '',
            ])
        buf = export_to_xlsx([{
            'title': '用户列表',
            'headers': ['用户名', '邮箱', '电话', '角色', '状态', '加入日期', '最后登录'],
            'rows': rows,
        }])
        return make_export_response(buf, f'用户_{timezone.now().strftime("%Y%m%d")}.xlsx')


# ── 旧权限系统（已废弃，RolePermission/UserRole 表无数据）──────────────────
# class RoleViewSet(viewsets.ModelViewSet): ...      # 废弃
# class PermissionViewSet(viewsets.ModelViewSet): ... # 废弃
# class RolePermissionViewSet(viewsets.ModelViewSet): ... # 废弃
# class UserRoleViewSet(viewsets.ModelViewSet): ... # 废弃


class NotificationViewSet(viewsets.ModelViewSet):
    """通知消息视图集"""
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated, RoleRequired]
    
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


class PermissionViewSet(viewsets.ReadOnlyModelViewSet):
    """权限码列表（仅读，用于角色配置UI）"""
    queryset = ModuleAction.objects.select_related('module').all().order_by('module__name', 'sort_order')
    permission_classes = [permissions.IsAuthenticated, RoleRequired]

    def get_serializer_class(self):
        if self.action == 'list':
            return PermissionListSerializer
        return ModuleActionSerializer


class PermissionAuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """权限审计日志视图集（仅读）"""
    queryset = PermissionAuditLog.objects.all()
    serializer_class = PermissionAuditLogSerializer
    permission_classes = [permissions.IsAuthenticated, RoleRequired]

    def get_queryset(self):
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
    def export(self, request):
        """导出权限审计日志 Excel"""
        from apps.core.export_excel import export_audit_logs, make_export_response
        queryset = self.get_queryset()
        records = queryset[:5000]
        buf = export_audit_logs(list(records))
        return make_export_response(buf, f'权限审计日志_{timezone.now().strftime("%Y%m%d")}.xlsx')
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
        """导出权限审计日志 Excel"""
        from apps.core.export_excel import export_audit_logs, make_export_response
        queryset = self.get_queryset()
        records = queryset[:5000]
        buf = export_audit_logs(list(records))
        return make_export_response(buf, f'权限审计日志_{timezone.now().strftime("%Y%m%d")}.xlsx')


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


class SystemSettingViewSet(viewsets.ModelViewSet):
    """系统参数管理视图集"""
    queryset = SystemSetting.objects.all()
    serializer_class = SystemSettingSerializer
    permission_classes = [permissions.IsAuthenticated, RoleRequired]
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

            return Response({
                'status': 'ok' if not missing else 'incomplete',
                'setting_count': count,
                'domain': domain or '(未配置)',
                'email_ok': email_ok,
                'https_ok': https_ok,
                'missing': missing,
                'message': '所有外部依赖已就绪 ✓' if not missing else f'还需配置: {", ".join(missing)}'
            }, status=status.HTTP_200_OK)
        except Exception as e:
            import traceback
            return Response({
                'error': str(e),
                'type': type(e).__name__,
                'tb': traceback.format_exc(),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
    permission_classes = [permissions.IsAuthenticated, RoleRequired]

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

    def get_serializer_class(self):
        if self.action == 'list':
            return CompanyRoleDefListSerializer
        return CompanyRoleDefSerializer

    def get_queryset(self):
        qs = CompanyRole.objects.select_related('company')
        company_id = self.request.query_params.get('company_id')
        if company_id:
            qs = qs.filter(company_id=company_id)
        return qs.order_by('company__name', 'name')

    def perform_create(self, serializer):
        role = serializer.save()
        # 新建时若同时提交了 permission_ids，同步写入中间表
        perm_ids = self.request.data.get('permission_ids', [])
        if perm_ids:
            self._sync_permissions(role, perm_ids)

    def perform_update(self, serializer):
        role = serializer.save()
        perm_ids = self.request.data.get('permission_ids', [])
        if perm_ids is not None:  # None=未传，保留原值；[]=显式清空
            self._sync_permissions(role, perm_ids)

    def perform_destroy(self, instance):
        # 检查是否已有用户分配了这个角色
        from .models import UserCompanyRole
        if UserCompanyRole.objects.filter(company_role=instance).exists():
            raise serializers.ValidationError({'detail': '该角色已有用户分配，无法删除'})
        instance.delete()

    def _sync_permissions(self, role, permission_ids):
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
        fields = ['id', 'name', 'code', 'description', 'is_active',
                  'company', 'company_name', 'permission_count',
                  'created_at', 'updated_at']

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
        fields = ['id', 'name', 'code', 'description', 'is_active',
                  'company', 'company_name', 'permissions', 'permission_ids',
                  'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

    def get_permissions(self, obj):
        return [{'id': p.id, 'code': p.code, 'name': p.name} for p in obj.permissions.all()]

    def update(self, instance, validated_data):
        # permission_ids 的同步由 ViewSet.perform_update 统一处理
        return super().update(instance, validated_data)


# ── 角色管理（基于新权限系统 UserCompanyRole）───────────────────────────────

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
                user=ucr.user, company=ucr.company,
                source=f'role:{ucr.company_role.id}'
            ).delete()
            # 批量写入
            for perm in ucr.company_role.permissions.all():
                # 找到对应的 ModuleAction
                ma = ModuleAction.objects.filter(perm_codes__contains=[perm.code]).first()
                if not ma:
                    continue
                UserCompanyPermission.objects.update_or_create(
                    user=ucr.user, company=ucr.company,
                    module=ma.module, action=ma,
                    defaults={
                        'is_granted': True,
                        'source': f'role:{ucr.company_role.id}',
                        'granted_by': ucr.assigned_by,
                    }
                )

    def _revoke_role_from_ucp(self, ucr):
        """移除角色时：删除该角色来源的 UCP 记录"""
        if not ucr.company_role:
            return
        from apps.core.models import UserCompanyPermission
        UserCompanyPermission.objects.filter(
            user=ucr.user, company=ucr.company,
            source=f'role:{ucr.company_role.id}'
        ).delete()

    @action(detail=False, methods=['get'])
    def roles_summary(self, request):
        """
        角色统计摘要 — 返回所有公司的角色分布。
        GET /api/core/company-roles/roles_summary/
        """
        from django.db.models import Count
        summary = (
            UserCompanyRole.objects
            .values('company__id', 'company__name', 'company_role__id', 'company_role__name')
            .annotate(count=Count('id'))
            .order_by('company__name', 'company_role__name')
        )
        result = []
        for item in summary:
            result.append({
                'company_id': item['company__id'],
                'company_name': item['company__name'],
                'company_role_id': item['company_role__id'],
                'company_role_name': item['company_role__name'] or '未分配',
                'count': item['count'],
            })
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
            return Response({'status': 'error', 'message': '公司不存在'}, status=404)
        roles = company.company_roles.filter(is_active=True)
        return Response({
            'status': 'success',
            'roles': [{'id': r.id, 'name': r.name, 'code': r.code} for r in roles]
        })


# ── 用户公司权限矩阵 ──────────────────────────────────────────────────────────

class UserCompanyPermissionViewSet(viewsets.ModelViewSet):
    """
    用户公司权限矩阵 CRUD。

    权限矩阵页面调用 /api/core/user-company-permissions/
    GET  ?user_id=X                                    → 获取某用户在所有公司的所有权限
    POST   {user_id, company_id, module_id, action_id, is_granted} → 写入/更新一条记录
    PUT/DELETE 批量操作由 matrix_bulk_update 处理
    """
    queryset = UserCompanyPermission.objects.all()
    permission_classes = [permissions.IsAuthenticated, RoleRequired]
    serializer_class = UserCompanyPermissionSerializer
    # 矩阵管理需要 admin 角色
    required_roles = ['admin']

    def get_queryset(self):
        qs = UserCompanyPermission.objects.select_related(
            'user', 'company', 'module', 'action'
        ).order_by('user__username', 'company__name', 'module__name', 'action__name')
        user_id = self.request.query_params.get('user_id')
        if user_id:
            qs = qs.filter(user_id=user_id)
        company_id = self.request.query_params.get('company_id')
        if company_id:
            qs = qs.filter(company_id=company_id)
        return qs

    @action(detail=False, methods=['get'])
    def matrix(self, request):
        """
        权限矩阵页核心接口。

        GET /api/core/user-company-permissions/matrix/?user_id=X

        返回：
        {
          modules: [{id, name, label, actions: [{id, name, label}]}],
          companies: [{id, name}],
          matrix: [{user_id, company_id, module_id, action_id, is_granted, has_record}]
        }
        """
        user_id = request.query_params.get('user_id')
        if not user_id:
            return Response({'detail': 'user_id 是必填参数'}, status=status.HTTP_400_BAD_REQUEST)

        # 所有模块 + 动作（按 sort_order 排序）
        modules = Module.objects.filter(is_active=True).prefetch_related('actions').order_by('sort_order')
        module_data = []
        for m in modules:
            module_data.append({
                'id': m.id,
                'name': m.name,
                'label': m.label,
                'icon': m.icon,
                'actions': [
                    {'id': a.id, 'name': a.name, 'label': a.label}
                    for a in m.actions.all().order_by('sort_order')
                ]
            })

        # 所有公司
        companies = list(FinanceCompany.objects.filter(status='active').order_by('name').values('id', 'name'))

        # 已有权限记录
        records = UserCompanyPermission.objects.filter(user_id=user_id).values(
            'user_id', 'company_id', 'module_id', 'action_id', 'is_granted'
        )

        return Response({
            'modules': module_data,
            'companies': companies,
            'matrix': list(records),
        })

    @action(detail=False, methods=['post'])
    def matrix_bulk_update(self, request):
        """
        批量更新权限矩阵。

        POST /api/core/user-company-permissions/matrix_bulk_update/
        Body: {
          user_id: int,
          updates: [
            {company_id, module_name, action_name, is_granted: bool},
            {company_id, module_id, action_id, is_granted: bool},
            ...
          ]
        }
        支持 name 或 id 两种方式传入模块/动作，优先用 name（可混用）。
        """
        user_id = request.data.get('user_id')
        updates = request.data.get('updates', [])
        if not user_id or not updates:
            return Response({'detail': 'user_id 和 updates 是必填参数'}, status=status.HTTP_400_BAD_REQUEST)

        # 权限校验：只有 superuser 或修改自己的权限
        if not request.user.is_superuser and request.user.id != int(user_id):
            return Response({'detail': '您没有权限修改他人的权限'}, status=status.HTTP_403_FORBIDDEN)

        # 预加载所有 Module/Action 用于 name→id 转换
        modules = {m.name: m.id for m in Module.objects.all()}
        actions = {a.name: a.id for a in ModuleAction.objects.all()}
        module_ids = {m.id: m.name for m in Module.objects.all()}
        action_ids = {a.id: a.name for a in ModuleAction.objects.all()}

        updated = []
        for upd in updates:
            # 支持 name 方式或 id 方式，name 优先
            company_id = upd['company_id']
            if 'module_name' in upd:
                module_id = modules.get(upd['module_name'])
            else:
                module_id = upd.get('module_id')
            if 'action_name' in upd:
                action_id = actions.get(upd['action_name'])
            else:
                action_id = upd.get('action_id')

            if not module_id or not action_id:
                return Response(
                    {'detail': f"找不到模块或动作: module={upd.get('module_name',upd.get('module_id'))}, action={upd.get('action_name',upd.get('action_id'))}"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            obj, created = UserCompanyPermission.objects.update_or_create(
                user_id=user_id,
                company_id=company_id,
                module_id=module_id,
                action_id=action_id,
                defaults={
                    'is_granted': upd['is_granted'],
                    'granted_by': request.user,
                }
            )
            updated.append({
                'id': obj.id,
                'company_id': obj.company_id,
                'module_id': obj.module_id,
                'action_id': obj.action_id,
                'is_granted': obj.is_granted,
                'created': created,
            })

        return Response({
            'updated': len(updated),
            'records': updated,
        })


# ── Health Check ────────────────────────────────────────
from django.http import JsonResponse
from django.db import connection

def health_check(request):
    """健康检查：验证数据库连接，返回服务状态"""
    try:
        connection.ensure_connection()
        return JsonResponse({'status': 'ok', 'database': 'connected'}, status=200)
    except Exception as e:
        return JsonResponse({'status': 'error', 'database': str(e)}, status=503)
