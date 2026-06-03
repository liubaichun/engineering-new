from rest_framework import serializers
from .models import (
    User,
    Notification,
    PermissionAuditLog,
    LoginLog,
    OperationAuditLog,
    SystemSetting,
    ModuleAction,
)
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
        validated_data['is_active'] = False  # 注册后需管理员审批才能登录
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


class UserSerializer(serializers.ModelSerializer):
    """用户序列化器 — 字段与 core_user 表及 User 模型严格对应"""

    role_name = serializers.SerializerMethodField()
    roles = serializers.SerializerMethodField()
    company_roles = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'first_name',
            'last_name',
            'email',
            'phone',
            'is_active',
            'is_staff',
            'is_superuser',
            'last_login',
            'date_joined',
            'password',
            'password_changed',
            'role_name',
            'roles',
            'company_roles',
        ]
        extra_kwargs = {
            'password': {'write_only': True, 'required': False},
        }

    def get_role_name(self, obj) -> str | None:
        """返回用户角色名称 — 基于UMP权限推断"""
        if obj.is_superuser:
            return '系统管理员'
        # 从UMP判断用户角色：有任一模块write→员工，只有read→只读
        from .models import UserModulePermission

        has_write = UserModulePermission.objects.filter(user=obj, granted_bits__gte=2).exists()
        return '员工' if has_write else '只读用户'

    def get_roles(self, obj) -> list:
        """返回用户的UMP模块权限信息"""
        roles = []
        try:
            for ump in obj.module_permissions.select_related('module', 'company').all():
                roles.append(
                    {
                        'module': ump.module.name,
                        'company_name': ump.company.name if ump.company else '-',
                        'bits': ump.granted_bits,
                    }
                )
        except Exception:
            pass
        return roles

    def get_company_roles(self, obj) -> list:
        """（废弃字段）返回空列表"""
        return []

    def create(self, validated_data):
        """创建用户"""
        password = validated_data.pop('password', None)

        # 使用 create_user 而非 create（自动哈希密码）
        if password:
            user = User.objects.create_user(
                username=validated_data['username'],
                password=password,
                email=validated_data.get('email', ''),
                phone=validated_data.get('phone', ''),
            )
        else:
            user = User.objects.create(**validated_data)

        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        instance = super().update(instance, validated_data)
        if password:
            instance.set_password(password)
            instance.save(update_fields=['password'])
        return instance


class PermissionListSerializer(serializers.ModelSerializer):
    """模块动作列表序列化器（简化版，用于角色配置UI）"""

    module_name = serializers.CharField(source='module.name', read_only=True)

    class Meta:
        model = ModuleAction
        fields = ['id', 'code', 'name', 'module_name']


class ModuleActionSerializer(serializers.ModelSerializer):
    """模块动作序列化器"""

    module_name = serializers.CharField(source='module.name', read_only=True)

    class Meta:
        model = ModuleAction
        fields = ['id', 'code', 'name', 'label', 'module', 'module_name', 'sort_order', 'perm_codes']


class NotificationSerializer(serializers.ModelSerializer):
    """通知消息序列化器"""

    type_display = serializers.CharField(source='get_notification_type_display', read_only=True)
    level_display = serializers.CharField(source='get_level_display', read_only=True)
    # 兼容前端 notifications.html 的字段名
    type = serializers.CharField(source='notification_type', read_only=True)
    message = serializers.CharField(source='content', read_only=True)

    class Meta:
        model = Notification
        fields = [
            'id',
            'user',
            'title',
            'content',
            'notification_type',
            'type_display',
            'level',
            'level_display',
            'is_read',
            'related_id',
            'related_type',
            'created_at',
            'type',
            'message',
        ]
        read_only_fields = ['id', 'user', 'created_at']


class PermissionAuditLogSerializer(serializers.ModelSerializer):
    """权限审计日志序列化器"""

    user_name = serializers.CharField(source='user.username', read_only=True, default='')
    target_user_name = serializers.CharField(source='target_user.username', read_only=True, default='')
    action_display = serializers.CharField(source='get_action_display', read_only=True)

    class Meta:
        model = PermissionAuditLog
        fields = [
            'id',
            'user',
            'user_name',
            'action',
            'action_display',
            'target_user',
            'target_user_name',
            'role_name',
            'permission_code',
            'ip_address',
            'user_agent',
            'details',
            'created_at',
        ]
        read_only_fields = fields  # 只读，仅通过 signals 自动写入


class LoginLogSerializer(serializers.ModelSerializer):
    """登录日志序列化器"""

    user_name = serializers.CharField(source='user.username', read_only=True, default='')
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = LoginLog
        fields = [
            'id',
            'user',
            'user_name',
            'username',
            'status',
            'status_display',
            'ip_address',
            'user_agent',
            'fail_reason',
            'created_at',
        ]
        read_only_fields = fields


class OperationAuditLogSerializer(serializers.ModelSerializer):
    """操作审计日志序列化器"""

    user_name = serializers.CharField(source='user.username', read_only=True, default='')
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    app_label_display = serializers.SerializerMethodField()
    changes_dict = serializers.SerializerMethodField()

    class Meta:
        model = OperationAuditLog
        fields = [
            'id',
            'user',
            'user_name',
            'username',
            'ip_address',
            'user_agent',
            'app_label',
            'app_label_display',
            'model_name',
            'object_id',
            'object_repr',
            'action',
            'action_display',
            'changes',
            'changes_dict',
            'approval_flow_id',
            'created_at',
        ]
        read_only_fields = fields

    def get_app_label_display(self, obj) -> str:
        """将 app_label 转为中文名称"""
        APP_NAMES = {
            'finance': '财务管理',
            'crm': '客户管理',
            'tasks': '任务管理',
            'equipment': '设备管理',
            'approvals': '审批管理',
            'core': '系统核心',
            'notifications': '通知管理',
            'files': '文件管理',
            'material': '物料管理',
        }
        return APP_NAMES.get(obj.app_label, obj.app_label)

    def get_changes_dict(self, obj) -> list:
        return obj.changes_dict


class SystemSettingSerializer(serializers.ModelSerializer):
    """系统参数序列化器"""

    key_display = serializers.SerializerMethodField()
    value_type = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()
    masked_value = serializers.SerializerMethodField()

    class Meta:
        model = SystemSetting
        fields = [
            'id',
            'key',
            'value',
            'key_display',
            'value_type',
            'category',
            'description',
            'masked_value',
            'updated_at',
        ]

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

    def get_key_display(self, obj) -> str:
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

    def get_value_type(self, obj) -> str:
        if obj.key in ('email_smtp_port',):
            return 'number'
        if obj.value.lower() in ('true', 'false'):
            return 'boolean'
        try:
            int(obj.value)
            return 'number'
        except ValueError:
            return 'text'

    def get_category(self, obj) -> str:
        return self.CATEGORY_MAP.get(obj.key, '其他')

    def get_masked_value(self, obj) -> str | None:
        """敏感字段（密码）显示为 ***，其余正常显示"""
        if obj.key in self.SENSITIVE_KEYS and obj.value:
            return '••••••••'
        return obj.value


class FinanceCompanySerializer(serializers.ModelSerializer):
    """公司信息序列化器（finance_company）"""

    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = FinanceCompany
        fields = [
            'id',
            'name',
            'code',
            'address',
            'contact_person',
            'contact_phone',
            'status',
            'status_display',
            'tax_id',
            'bank_name',
            'bank_account',
            'remark',
            'created_at',
        ]
