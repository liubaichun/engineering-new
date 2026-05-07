from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from .models import User, Role, Permission, RolePermission, UserRole, Notification, PermissionAuditLog, LoginLog, UserCompanyRole, OperationAuditLog, SystemSetting
from apps.finance.models import Company as FinanceCompany


class UserRegisterSerializer(serializers.ModelSerializer):
    """用户注册序列化器"""
    password = serializers.CharField(write_only=True, min_length=8, label='密码')
    password_confirm = serializers.CharField(write_only=True, required=False, label='确认密码')
    
    class Meta:
        model = User
        fields = ['username', 'email', 'phone', 'password', 'password_confirm']
        extra_kwargs = {
            'email': {'required': False},
        }
    
    def validate_password(self, value):
        if len(value) < 8:
            raise serializers.ValidationError('密码至少需要8个字符')
        if not any(c.isupper() for c in value):
            raise serializers.ValidationError('密码必须包含至少一个大写字母')
        if not any(c.islower() for c in value):
            raise serializers.ValidationError('密码必须包含至少一个小写字母')
        if not any(c.isdigit() for c in value):
            raise serializers.ValidationError('密码必须包含至少一个数字')
        return value
    
    def validate(self, attrs):
        password_confirm = attrs.get('password_confirm')
        if password_confirm and attrs['password'] != password_confirm:
            raise serializers.ValidationError({'password_confirm': '两次密码输入不一致'})
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('password_confirm', None)
        password = validated_data.pop('password')
        validated_data['is_active'] = False   # 注册后需管理员审批才能登录
        validated_data['is_staff'] = False
        validated_data['is_superuser'] = False
        validated_data.setdefault('phone', '')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        # 给所有管理员发通知
        from .models import Notification
        admin_users = User.objects.filter(is_superuser=True, is_active=True)
        for admin in admin_users:
            Notification.objects.create(
                user=admin,
                title='新用户注册待审批',
                content=f'用户 "{user.username}"（{user.email or "未填邮箱"}）已提交注册申请，请及时审批。',
                notification_type='approval_pending',
                level='warning',
                related_id=user.id,
                related_type='user_registration',
            )
        return user


class UserLoginSerializer(serializers.Serializer):
    """用户登录序列化器"""
    username = serializers.CharField(label='用户名')
    password = serializers.CharField(label='密码', write_only=True)
    
    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise serializers.ValidationError('用户名或密码错误')

        # 检查账号是否被锁定
        if user.lock_until:
            from django.utils import timezone
            if timezone.now() < user.lock_until:
                remaining = int((user.lock_until - timezone.now()).total_seconds() / 60) + 1
                raise serializers.ValidationError(f'账号已锁定，请 {remaining} 分钟后再试')

        if not user.check_password(password):
            # 密码错误 → 记录失败次数
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= 5:
                from django.utils import timezone
                from datetime import timedelta
                user.lock_until = timezone.now() + timedelta(minutes=30)
                user.save(update_fields=['failed_login_attempts', 'lock_until'])
                raise serializers.ValidationError('密码错误次数过多，账号已锁定30分钟')
            user.save(update_fields=['failed_login_attempts'])
            raise serializers.ValidationError(f'用户名或密码错误（剩余 {5 - user.failed_login_attempts} 次）')

        # 登录成功 → 重置失败计数和锁定
        if user.failed_login_attempts > 0 or user.lock_until:
            user.failed_login_attempts = 0
            user.lock_until = None
            user.save(update_fields=['failed_login_attempts', 'lock_until'])

        if not user.is_active:
            # 有最近登录记录 → 曾激活后被禁用；无登录记录 → 注册后从未激活（待审批）
            has_logged_in = user.last_login is not None
            msg = '账号已被禁用，请联系管理员' if has_logged_in else '账号待审批，请等待管理员审核后再登录'
            raise serializers.ValidationError(msg)

        attrs['user'] = user
        return attrs


class UserCompanyRoleSerializer(serializers.ModelSerializer):
    """用户公司角色序列化器"""
    company_name = serializers.CharField(source='company.name', read_only=True)
    user_name = serializers.CharField(source='user.username', read_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)

    class Meta:
        model = UserCompanyRole
        fields = ['id', 'user', 'user_name', 'company', 'company_name', 'role', 'role_display', 'assigned_by', 'assigned_at']
        read_only_fields = ['id', 'assigned_by', 'assigned_at']


class UserSerializer(serializers.ModelSerializer):
    """用户序列化器 — 字段与 core_user 表及 User 模型严格对应"""
    role_name = serializers.SerializerMethodField()
    roles = serializers.SerializerMethodField()
    role_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False,
        label='角色ID列表'
    )
    company_roles = UserCompanyRoleSerializer(many=True, read_only=True)
    company_role_ids = serializers.ListField(
        child=serializers.DictField(), write_only=True, required=False,
        label='公司角色列表 [{company_id, role}]'
    )

    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'phone', 'password',
                  'is_active', 'is_staff', 'is_superuser', 'last_login', 'date_joined',
                  'role_name', 'roles', 'role_ids', 'company_roles', 'company_role_ids']
        extra_kwargs = {'password': {'write_only': True}}
        read_only_fields = ['id', 'is_staff', 'is_superuser', 'last_login', 'date_joined']

    def create(self, validated_data):
        role_ids = validated_data.pop('role_ids', None)
        company_role_ids = validated_data.pop('company_role_ids', None)

        # 处理 is_superuser
        is_superuser = validated_data.pop('is_superuser', False)

        # 创建用户
        password = validated_data.pop('password', None)
        if password:
            validated_data['password'] = make_password(password)

        user = User.objects.create(**validated_data)
        if is_superuser:
            user.is_superuser = True
            user.save(update_fields=['is_superuser'])

        # 处理角色关联
        if role_ids is not None:
            for rid in role_ids:
                UserRole.objects.create(user=user, role_id=rid)

        # 处理公司角色关联
        if company_role_ids is not None:
            for cr in company_role_ids:
                UserCompanyRole.objects.create(
                    user=user,
                    company_id=cr.get('company_id'),
                    role=cr.get('role', 'staff')
                )

        return user

    def get_role_name(self, obj):
        """返回用户角色名称 — 优先用 UserCompanyRole 的角色，否则用 User.role 字段"""
        if obj.is_superuser:
            return '系统管理员'
        # 优先取第一个公司角色
        link = obj.company_roles.first()
        if link:
            return dict(UserCompanyRole.ROLE_CHOICES).get(link.role, link.role)
        # 兜底 User.role 字段（系统级角色代码）
        role_map = {
            'admin': '系统管理员',
            'manager': '经理',
            'staff': '员工',
        }
        return role_map.get(obj.role, obj.role) if obj.role else ''

    def get_roles(self, obj):
        """返回用户通过UserRole关联的所有角色"""
        return list(obj.user_roles.all().values(
            'role_id', 'role__name', 'role__code', 'assigned_at'
        ))

    def update(self, instance, validated_data):
        role_ids = validated_data.pop('role_ids', None)
        company_role_ids = validated_data.pop('company_role_ids', None)
        request = self.context.get('request')
        old_role_ids = set(instance.user_roles.values_list('role_id', flat=True))
        instance = super().update(instance, validated_data)
        if role_ids is not None:
            new_role_ids = set(role_ids)
            added = new_role_ids - old_role_ids
            removed = old_role_ids - new_role_ids
            # 重建 UserRole 关联
            UserRole.objects.filter(user=instance).delete()
            for rid in role_ids:
                UserRole.objects.create(user=instance, role_id=rid)
            # 写审计日志
            if request and (added or removed):
                    try:
                        from .models import PermissionAuditLog
                        ip = request.META.get('REMOTE_ADDR', '') if request else ''
                        ua = request.META.get('HTTP_USER_AGENT', '')[:500] if request else ''
                        req = self.context.get('request')
                        auth_company = getattr(req, 'auth_company', None) if req else None
                        for rid in added:
                            PermissionAuditLog.objects.create(
                                user=request.user if request and hasattr(request, 'user') else None,
                                action='assign_role',
                                target_user=instance,
                                role_id=rid,
                                ip_address=ip,
                                user_agent=ua,
                                details=f'分配角色 {rid}',
                                company=auth_company,
                            )
                        for rid in removed:
                            PermissionAuditLog.objects.create(
                                user=request.user if request and hasattr(request, 'user') else None,
                                action='remove_role',
                                target_user=instance,
                                role_id=rid,
                                ip_address=ip,
                                user_agent=ua,
                                details=f'移除角色 {rid}',
                                company=auth_company,
                            )
                    except Exception:
                        pass
        # 处理公司角色分配（批量覆盖）
        if company_role_ids is not None:
            existing = {ucr.company_id: ucr for ucr in instance.company_roles.all()}
            incoming = {item['company_id']: item for item in company_role_ids}
            # 删除不在新列表中的
            removed_company_ids = set(existing.keys()) - set(incoming.keys())
            UserCompanyRole.objects.filter(user=instance, company_id__in=removed_company_ids).delete()
            # 创建或更新
            for company_id, item in incoming.items():
                UserCompanyRole.objects.update_or_create(
                    user=instance, company_id=company_id,
                    defaults={'role': item.get('role', 'staff')}
                )
        return instance


class UserRoleSerializer(serializers.ModelSerializer):
    """用户角色序列化器"""
    class Meta:
        model = UserRole
        fields = ['id', 'user', 'role', 'assigned_by', 'assigned_at']
        read_only_fields = ['id', 'assigned_at']


class RoleSerializer(serializers.ModelSerializer):
    """角色序列化器"""
    permissions = serializers.SerializerMethodField()
    user_count = serializers.SerializerMethodField()
    # 支持创建/更新时传入 permission_ids 直接分配权限
    permission_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False)

    class Meta:
        model = Role
        fields = ['id', 'name', 'code', 'description', 'is_active', 'created_at', 'updated_at',
                  'permissions', 'user_count', 'permission_ids']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_permissions(self, obj):
        """返回角色关联的权限ID列表"""
        return list(RolePermission.objects.filter(role=obj).values_list('permission_id', flat=True))

    def get_user_count(self, obj):
        """返回拥有该角色的用户数量（通过UserRole关联表）"""
        from apps.core.models import UserRole
        return UserRole.objects.filter(role_id=obj.id, user__is_active=True).count()

    def create(self, validated_data):
        permission_ids = validated_data.pop('permission_ids', [])
        role = super().create(validated_data)
        self._update_permissions(role, permission_ids)
        return role

    def update(self, instance, validated_data):
        permission_ids = validated_data.pop('permission_ids', None)
        role = super().update(instance, validated_data)
        if permission_ids is not None:
            self._update_permissions(role, permission_ids)
        return role

    def _update_permissions(self, role, permission_ids):
        RolePermission.objects.filter(role=role).delete()
        for perm_id in permission_ids:
            RolePermission.objects.create(role=role, permission_id=perm_id)


class PermissionSerializer(serializers.ModelSerializer):
    """权限序列化器"""

    class Meta:
        model = Permission
        fields = ['id', 'name', 'code', 'resource', 'action',
                  'category', 'description', 'created_at']
        read_only_fields = ['id', 'created_at']


class RolePermissionSerializer(serializers.ModelSerializer):
    """角色权限序列化器"""
    role_name = serializers.CharField(source='role.name', read_only=True)
    permission_name = serializers.CharField(source='permission.name', read_only=True)

    class Meta:
        model = RolePermission
        fields = ['id', 'role', 'role_name', 'permission', 'permission_name',
                  'granted_by', 'granted_at']
        read_only_fields = ['id', 'granted_by', 'granted_at']


class NotificationSerializer(serializers.ModelSerializer):
    """通知消息序列化器"""
    type_display = serializers.CharField(source='get_notification_type_display', read_only=True)
    level_display = serializers.CharField(source='get_level_display', read_only=True)
    # 兼容前端 notifications.html 的字段名
    type = serializers.CharField(source='notification_type', read_only=True)
    message = serializers.CharField(source='content', read_only=True)

    class Meta:
        model = Notification
        fields = ['id', 'user', 'title', 'content', 'notification_type', 'type_display',
                  'level', 'level_display', 'is_read', 'related_id', 'related_type',
                  'created_at', 'type', 'message']
        read_only_fields = ['id', 'user', 'created_at']


class PermissionAuditLogSerializer(serializers.ModelSerializer):
    """权限审计日志序列化器"""
    user_name = serializers.CharField(source='user.username', read_only=True, default='')
    target_user_name = serializers.CharField(source='target_user.username', read_only=True, default='')
    role_name = serializers.CharField(source='role.name', read_only=True, default='')
    action_display = serializers.CharField(source='get_action_display', read_only=True)

    class Meta:
        model = PermissionAuditLog
        fields = ['id', 'user', 'user_name', 'action', 'action_display',
                  'target_user', 'target_user_name', 'role', 'role_name',
                  'permission', 'ip_address', 'user_agent', 'details', 'created_at']
        read_only_fields = fields  # 只读，仅通过 signals 自动写入


class LoginLogSerializer(serializers.ModelSerializer):
    """登录日志序列化器"""
    user_name = serializers.CharField(source='user.username', read_only=True, default='')
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = LoginLog
        fields = ['id', 'user', 'user_name', 'username', 'status', 'status_display',
                  'ip_address', 'user_agent', 'fail_reason', 'created_at']
        read_only_fields = fields


class OperationAuditLogSerializer(serializers.ModelSerializer):
    """操作审计日志序列化器"""
    user_name = serializers.CharField(source='user.username', read_only=True, default='')
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    app_label_display = serializers.SerializerMethodField()
    changes_dict = serializers.SerializerMethodField()

    class Meta:
        model = OperationAuditLog
        fields = ['id', 'user', 'user_name', 'username', 'ip_address', 'user_agent',
                  'app_label', 'app_label_display', 'model_name', 'object_id', 'object_repr',
                  'action', 'action_display', 'changes', 'changes_dict',
                  'approval_flow_id', 'created_at']
        read_only_fields = fields

    def get_app_label_display(self, obj):
        """将 app_label 转为中文名称"""
        APP_NAMES = {
            'finance': '财务管理', 'crm': '客户管理', 'tasks': '任务管理',
            'equipment': '设备管理', 'approvals': '审批管理', 'core': '系统核心',
            'notifications': '通知管理', 'files': '文件管理', 'material': '物料管理',
        }
        return APP_NAMES.get(obj.app_label, obj.app_label)

    def get_changes_dict(self, obj):
        return obj.changes_dict


class SystemSettingSerializer(serializers.ModelSerializer):
    """系统参数序列化器"""
    key_display = serializers.SerializerMethodField()
    value_type = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()
    masked_value = serializers.SerializerMethodField()

    class Meta:
        model = SystemSetting
        fields = ['id', 'key', 'value', 'key_display', 'value_type',
                  'category', 'description', 'masked_value', 'updated_at']

    CATEGORY_MAP = {
        'approval_auto_enabled': '审批',
        'approval_timeout_hours': '审批',
        'approval_escalate_enabled': '审批',
        'wage_submit_creates_approval': '审批',
        'multi_level_approval_enabled': '审批',
        'email_smtp_host': '邮件服务',
        'email_smtp_port': '邮件服务',
        'email_smtp_user': '邮件服务',
        'email_smtp_password': '邮件服务',
        'email_use_tls': '邮件服务',
        'email_from': '邮件服务',
        'site_domain': '域名/HTTPS',
        'site_https_enabled': '域名/HTTPS',
        'ssl_cert_path': '域名/HTTPS',
        'ssl_key_path': '域名/HTTPS',
        'ssl_auto_renew': '域名/HTTPS',
    }
    SENSITIVE_KEYS = {'email_smtp_password'}

    def get_key_display(self, obj):
        DISPLAY_NAMES = {
            'approval_auto_enabled': '审批自动化',
            'approval_timeout_hours': '审批超时小时数',
            'approval_escalate_enabled': '超时自动升级',
            'wage_submit_creates_approval': '工资提交触发审批',
            'multi_level_approval_enabled': '多级审批',
            'email_smtp_host': 'SMTP主机',
            'email_smtp_port': 'SMTP端口',
            'email_smtp_user': 'SMTP用户名',
            'email_smtp_password': 'SMTP密码',
            'email_use_tls': '启用TLS',
            'email_from': '发件人地址',
            'site_domain': '系统域名',
            'site_https_enabled': '启用HTTPS',
            'ssl_cert_path': 'SSL证书路径',
            'ssl_key_path': 'SSL私钥路径',
            'ssl_auto_renew': '自动续期',
        }
        return DISPLAY_NAMES.get(obj.key, obj.key)

    def get_value_type(self, obj):
        if obj.key in ('email_smtp_port',):
            return 'number'
        if obj.value.lower() in ('true', 'false'):
            return 'boolean'
        try:
            int(obj.value)
            return 'number'
        except ValueError:
            return 'text'

    def get_category(self, obj):
        return self.CATEGORY_MAP.get(obj.key, '其他')

    def get_masked_value(self, obj):
        """敏感字段（密码）显示为 ***，其余正常显示"""
        if obj.key in self.SENSITIVE_KEYS and obj.value:
            return '••••••••'
        return obj.value


class FinanceCompanySerializer(serializers.ModelSerializer):
    """公司信息序列化器（finance_company）"""
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = FinanceCompany
        fields = ['id', 'name', 'code', 'address', 'contact_person',
                  'contact_phone', 'status', 'status_display',
                  'tax_id', 'bank_name', 'bank_account', 'remark',
                  'created_at']
