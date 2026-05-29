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

from django.contrib.auth import authenticate, login, logout
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import default_token_generator
from django.template.loader import render_to_string
from django.core.mail import send_mail

from django.middleware.csrf import get_token

from .models import User, LoginLog
from .serializers import (
    UserRegisterSerializer,
    UserLoginSerializer,
    UserSerializer,
)
from apps.core.permissions import RoleRequired, get_module_companies
from .views_common import get_csrf_token, get_client_ip

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
        try:
            user.save()
        except Exception as e:
            return Response({'status': 'error', 'message': f'密码重置失败：{str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({'status': 'success', 'message': '密码重置成功，请使用新密码登录。'})


class RegisterView(APIView):
    """用户注册视图"""
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(tags=['auth'], summary='用户注册', description='提交注册信息，管理员审批后账号生效')
    def post(self, request):
        # 关闭自助注册入口
        return Response(
            {'status': 'error', 'message': '注册入口已关闭，请联系系统管理员。'},
            status=status.HTTP_403_FORBIDDEN
        )


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
        try:
            user.save(update_fields=['password', 'password_changed'])
        except Exception as e:
            return Response({
                'status': 'error',
                'message': f'密码修改失败：{str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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

    def post(self, request):
        """
        POST /api/core/auth/user/ - 切换公司
        请求体: {action: 'switch_company', company_id: int}
        或兼容旧格式直接发 {company_id: int}
        """
        action = request.data.get('action', '')
        company_id = request.data.get('company_id')

        if action == 'switch_company' or company_id:
            return self._switch_company(request, company_id)
        elif action == 'my_companies':
            return self._my_companies(request)

        return Response({'status': 'error', 'message': '不支持的操作。使用 action=switch_company+company_id 或 action=my_companies'},
                        status=status.HTTP_400_BAD_REQUEST)

    def _switch_company(self, request, company_id):
        """切换当前活跃公司"""
        if not company_id:
            return Response({'status': 'error', 'message': 'company_id 不能为空'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            company_id = int(company_id)
        except (ValueError, TypeError):
            return Response({'status': 'error', 'message': 'company_id 必须是整数'}, status=status.HTTP_400_BAD_REQUEST)

        from apps.core.models import UserCompanyPermission
        # 使用 UCP（新权限系统）验证用户是否属于该公司
        has_access = UserCompanyPermission.objects.filter(
            user=request.user, company_id=company_id, is_granted=True
        ).exists()
        if not has_access:
            return Response({'status': 'error', 'message': '您不属于该公司，无权访问'}, status=status.HTTP_403_FORBIDDEN)

        request.session['current_company_id'] = company_id
        from apps.finance.models import Company
        try:
            company = Company.objects.get(id=company_id)
            company_name = company.name
        except Company.DoesNotExist:
            company_name = '未知'

        return Response({
            'status': 'success',
            'message': '已切换到公司',
            'current_company_id': company_id,
            'company_name': company_name,
        }, status=status.HTTP_200_OK)

    def _my_companies(self, request):
        """获取当前用户可访问的公司列表"""
        from apps.core.models import UserCompanyPermission
        from apps.finance.models import Company
        ucp_companies = UserCompanyPermission.objects.filter(
            user=request.user, is_granted=True
        ).values_list('company_id', flat=True).distinct()
        companies = Company.objects.filter(id__in=list(ucp_companies))
        current_company_id = request.session.get('current_company_id')
        data = []
        for c in companies:
            data.append({
                'company_id': c.id,
                'company_name': c.name,
                'is_current': c.id == current_company_id,
            })
        return Response({'status': 'success', 'companies': data}, status=status.HTTP_200_OK)


class SwitchCompanyView(APIView):
    """兼容旧版：POST /api/core/switch_company/"""
    permission_classes = [permissions.IsAuthenticated, RoleRequired]

    def post(self, request):
        company_id = request.data.get('company_id')
        if not company_id:
            return Response({'status': 'error', 'message': 'company_id 不能为空'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            company_id = int(company_id)
        except (ValueError, TypeError):
            return Response({'status': 'error', 'message': 'company_id 必须是整数'}, status=status.HTTP_400_BAD_REQUEST)

        from apps.core.models import UserCompanyPermission
        has_access = UserCompanyPermission.objects.filter(
            user=request.user, company_id=company_id, is_granted=True
        ).exists()
        if not has_access:
            return Response({'status': 'error', 'message': '您不属于该公司，无权访问'}, status=status.HTTP_403_FORBIDDEN)

        request.session['current_company_id'] = company_id
        from apps.finance.models import Company
        try:
            company = Company.objects.get(id=company_id)
            company_name = company.name
        except Company.DoesNotExist:
            company_name = '未知'

        return Response({
            'status': 'success',
            'message': '已切换到公司',
            'current_company_id': company_id,
            'company_name': company_name,
        }, status=status.HTTP_200_OK)


class MyPermissionsView(APIView):
    """当前用户权限列表（用于前端按钮级权限控制）
    
    返回统一格式的权限码：category:resource:action
    超级用户返回 ['*']，前端 hasPermission('*') 放行所有。
    """
    permission_classes = [permissions.IsAuthenticated, RoleRequired]

    def _generate_codes_from_ump(self, user, company_id):
        """从 UserModulePermission 生成前端权限码（统一格式）"""
        from apps.core.models import UserModulePermission, ACTION_BITS
        
        codes = set()
        for perm in UserModulePermission.objects.filter(
            user=user, company_id=company_id, granted_bits__gt=0
        ).select_related('module'):
            # 遍历所有 action bit
            for action_name, bit in ACTION_BITS.items():
                if action_name == '_RESERVED':
                    continue
                if perm.granted_bits & bit:
                    codes.add(f'{perm.module.category}:{perm.module.name}:{action_name}')
        return codes

    def get(self, request):
        user = request.user
        company_id = request.session.get('current_company_id')
        if not company_id:
            from apps.core.models import UserCompanyRole
            first_link = UserCompanyRole.objects.filter(user=user).first()
            company_id = first_link.company_id if first_link else None

        if user.is_superuser:
            codes = ['*']  # 超级用户特殊标记
        elif company_id:
            codes = list(self._generate_codes_from_ump(user, company_id))
        else:
            codes = []

        return Response({
            'status': 'success',
            'codes': codes,
            'user_id': user.id,
            'is_superuser': user.is_superuser,
        }, status=status.HTTP_200_OK)
