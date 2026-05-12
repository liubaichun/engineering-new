from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """用户模型 — 字段与 core_user 表严格对应"""
    id = models.AutoField(primary_key=True)
    # AbstractUser 提供: username, password, first_name, last_name, email,
    # is_active, is_staff, is_superuser, last_login, date_joined
    phone = models.CharField(max_length=20, blank=True, default='', verbose_name='手机号')
    email = models.EmailField(blank=True, default='', verbose_name='邮箱')
    role = models.CharField(max_length=20, blank=True, default='', verbose_name='角色代码')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    failed_login_attempts = models.IntegerField(default=0, verbose_name='失败登录次数')
    lock_until = models.DateTimeField(null=True, blank=True, verbose_name='锁定截止时间')
    password_changed = models.BooleanField(default=False, verbose_name='密码是否已修改')
    # 所属公司（兼容旧数据，建议优先通过 UserCompanyRole 配置多公司访问）
    company = models.ForeignKey(
        'finance.Company', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='users',
        verbose_name='所属公司（兼容字段）'
    )

    def get_company_role(self, company_id):
        """获取用户在指定公司的角色，找不到返回 None"""
        link = self.company_roles.filter(company_id=company_id).first()
        return link.role if link else None

    def is_company_admin(self, company_id):
        return self.get_company_role(company_id) == 'admin'

    def is_company_staff(self, company_id):
        role = self.get_company_role(company_id)
        return role in ('admin', 'staff')

    def is_superadmin(self):
        """系统超级管理员（is_superuser）拥有所有权限"""
        return self.is_superuser

    def has_role(self, role_code, company_id=None):
        """检查用户是否拥有指定角色（支持系统级角色和公司级角色）"""
        if self.is_superuser:
            return True
        # 系统级角色：User.role 字段
        if self.role == role_code:
            return True
        # 公司级角色
        if company_id:
            link = self.company_roles.filter(company_id=company_id, role=role_code).exists()
            if link:
                return True
        return False

    def has_perm(self, perm_code):
        """检查用户是否拥有指定权限码（精确匹配）"""
        if self.is_superuser:
            return True
        role_ids = list(self.user_roles.values_list('role_id', flat=True))
        # 精确匹配
        if Permission.objects.filter(
            code=perm_code,
            roles__id__in=role_ids,
            is_active=True
        ).exists():
            return True
        return False

    def get_permissions(self):
        """Get all permission codes for this user"""
        role_ids = list(self.user_roles.values_list('role_id', flat=True))
        return list(Permission.objects.filter(
            roles__id__in=role_ids,
            is_active=True
        ).values_list('code', flat=True).distinct())

    def get_roles(self):
        """获取用户所有角色名称列表"""
        return list(self.user_roles.select_related('role').values_list('role__name', flat=True).distinct())

    def get_companies(self):
        return [ucr.company_id for ucr in self.company_roles.all()]

    class Meta:
        db_table = 'core_user'
        verbose_name = '用户'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.username


class UserCompanyRole(models.Model):
    """用户在公司内的角色 — 支持多公司多角色"""
    ROLE_CHOICES = [
        ('admin', '公司管理员'),
        ('staff', '普通员工'),
    ]
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='company_roles')
    company = models.ForeignKey('finance.Company', on_delete=models.CASCADE, related_name='user_roles')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='staff', verbose_name='角色')
    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    class Meta:
        db_table = 'core_user_company_role'
        unique_together = [['user', 'company']]
        verbose_name = '用户公司角色'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.user.username}@{self.company.name}({self.get_role_display()})"


class Role(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, unique=True, verbose_name='角色名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='角色代码')
    description = models.TextField(blank=True, verbose_name='描述')
    is_active = models.BooleanField(default=True, verbose_name='是否激活')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    permissions = models.ManyToManyField('Permission', through='RolePermission', related_name='roles')

    class Meta:
        db_table = 'core_role'
        verbose_name = '角色'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name

    def get_user_count(self):
        return UserRole.objects.filter(role=self).count()
    get_user_count.short_description = '用户数'


class Permission(models.Model):
    id = models.AutoField(primary_key=True)
    resource = models.CharField(max_length=50, verbose_name='资源')
    action = models.CharField(max_length=50, verbose_name='操作')
    name = models.CharField(max_length=100, verbose_name='权限名称')
    code = models.CharField(max_length=100, unique=True, verbose_name='权限代码')
    description = models.TextField(blank=True, verbose_name='描述')
    category = models.CharField(max_length=50, default='general', verbose_name='分类')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    menu_code = models.CharField(max_length=50, default='', verbose_name='菜单代码')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'core_permission'
        verbose_name = '权限'
        verbose_name_plural = verbose_name
        unique_together = [['resource', 'action']]

    def __str__(self):
        return f"{self.resource}:{self.action}"


class RolePermission(models.Model):
    id = models.AutoField(primary_key=True)
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE)
    granted_by = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, related_name='granted_roles')
    granted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'core_role_permission'
        unique_together = [['role', 'permission']]


class UserRole(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_roles')
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='+')

    class Meta:
        db_table = 'core_user_role'
        unique_together = [['user', 'role']]


class Notification(models.Model):
    LEVEL_CHOICES = [
        ('info', '通知'), ('warning', '预警'), ('error', '错误'), ('success', '成功'),
    ]
    TYPE_CHOICES = [
        ('task_overdue', '任务超时'), ('approval_timeout', '审批超时'),
        ('approval', '待审批'), ('approval_pending', '审批待处理'),
        ('contract_expiring', '合同到期'), ('large_expense', '大额支出'),
        ('project_overdue', '项目超时'), ('wage_pending', '工资待发放'),
    ]
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200, verbose_name='标题')
    content = models.TextField(blank=True, verbose_name='内容')
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='info')
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='info')
    is_read = models.BooleanField(default=False, verbose_name='已读')
    related_id = models.IntegerField(null=True, blank=True, verbose_name='关联ID')
    related_type = models.CharField(max_length=50, blank=True, verbose_name='关联类型')
    company = models.ForeignKey(
        'finance.Company', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='notifications',
        verbose_name='公司'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'core_notification'
        ordering = ['-created_at']
        verbose_name = '通知'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.title


class PermissionAuditLog(models.Model):
    ACTION_CHOICES = [
        ('assign_role', '分配角色'), ('remove_role', '移除角色'),
        ('grant_permission', '授予权限'), ('revoke_permission', '撤销权限'),
    ]
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='permission_logs')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, verbose_name='操作类型')
    target_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='+', verbose_name='目标用户')
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='角色')
    permission = models.ForeignKey(Permission, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='权限')
    company = models.ForeignKey('finance.Company', on_delete=models.SET_NULL, null=True, blank=True, related_name='+', verbose_name='公司')
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP地址')
    user_agent = models.TextField(blank=True, verbose_name='User Agent')
    details = models.TextField(blank=True, verbose_name='变更详情')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='操作时间')

    class Meta:
        db_table = 'core_permission_audit_log'
        ordering = ['-created_at']
        verbose_name = '权限审计日志'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.get_action_display()} - {self.target_user}"


class SystemSetting(models.Model):
    """系统全局设置 — 支持邮件服务、域名、HTTPS 等外部依赖配置"""
    KEY_CHOICES = [
        # ── 审批配置 ──
        ('approval_auto_enabled', '审批自动化', '是否启用智能审批（金额路由+超时升级）'),
        ('approval_timeout_hours', '审批超时小时数', '超时多少小时后触发升级通知'),
        ('approval_escalate_enabled', '超时升级', '审批节点超时时是否自动升级'),
        ('wage_submit_creates_approval', '工资提交触发审批', '工资单提交审核时是否自动创建审批流'),
        ('multi_level_approval_enabled', '多级审批', '是否启用按金额自动选择审批层级'),
        # ── 邮件服务（用户可自行配置）──
        ('email_smtp_host', 'SMTP主机', '邮件发送服务器地址，如 smtp.qq.com'),
        ('email_smtp_port', 'SMTP端口', '邮件服务器端口，默认587'),
        ('email_smtp_user', 'SMTP用户名', '邮件发送账号'),
        ('email_smtp_password', 'SMTP密码', '邮件发送密码（请勿泄露）'),
        ('email_use_tls', '启用TLS', '是否启用TLS加密，true或false'),
        ('email_from', '发件人地址', '系统发件邮箱地址'),
        # ── 站点域名 ──
        ('site_domain', '系统域名', '访问域名，如 example.com，不含https://'),
        ('site_https_enabled', '启用HTTPS', '是否启用HTTPS，true或false'),
        # ── SSL证书（Let's Encrypt 自动申请后填入）──
        ('ssl_cert_path', 'SSL证书路径', '/etc/letsencrypt/live/域名/fullchain.pem'),
        ('ssl_key_path', 'SSL私钥路径', '/etc/letsencrypt/live/域名/privkey.pem'),
        ('ssl_auto_renew', '自动续期', '是否启用certbot自动续期，true或false'),
    ]
    SENSITIVE_KEYS = {'email_smtp_password'}

    key = models.CharField('设置键', max_length=100, unique=True, choices=[(k, k) for k, *_ in KEY_CHOICES])
    value = models.CharField('设置值', max_length=500)
    description = models.CharField('说明', max_length=255, blank=True, default='')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'core_system_setting'
        verbose_name = '系统设置'

    def __str__(self):
        label = next((desc for k, *desc in self.KEY_CHOICES if k == self.key), self.key)
        return f'{label}={self.value}'

    @property
    def is_sensitive(self):
        """敏感字段（如密码）在列表中脱敏显示"""
        return self.key in self.SENSITIVE_KEYS

    @classmethod
    def get_value(cls, key, default=None):
        """快速读取单个配置值"""
        inst = cls.objects.filter(key=key).first()
        return inst.value if inst else default

    @classmethod
    def is_email_configured(cls):
        """检查邮件服务是否已完整配置"""
        host = cls.get_value('email_smtp_host')
        user = cls.get_value('email_smtp_user')
        password = cls.get_value('email_smtp_password')
        return bool(host and user and password)

    @classmethod
    def is_https_ready(cls):
        """检查HTTPS是否已就绪（域名+证书路径均已配置）"""
        domain = cls.get_value('site_domain')
        cert = cls.get_value('ssl_cert_path')
        key = cls.get_value('ssl_key_path')
        return bool(domain and cert and key)


class LoginLog(models.Model):
    """登录日志"""
    STATUS_CHOICES = [
        ('success', '登录成功'),
        ('failed', '登录失败'),
    ]
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='login_logs', verbose_name='用户'
    )
    username = models.CharField(max_length=150, verbose_name='用户名')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, verbose_name='登录状态')
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP地址')
    user_agent = models.TextField(blank=True, verbose_name='User Agent')
    fail_reason = models.CharField(max_length=200, blank=True, default='', verbose_name='失败原因')
    company = models.ForeignKey(
        'finance.Company', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='login_logs',
        verbose_name='公司'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='登录时间')

    class Meta:
        db_table = 'core_login_log'
        ordering = ['-created_at']
        verbose_name = '登录日志'
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=['username', '-created_at']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f"{self.username} - {self.get_status_display()} - {self.created_at}"


class OperationAuditLog(models.Model):
    """
    通用操作审计日志 — 覆盖所有写操作（增/删/改）
    通过 Django 信号自动记录，无需在每个视图手动调用
    """
    ACTION_CHOICES = [
        ('create', '新增'), ('update', '修改'), ('delete', '删除'),
    ]
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='operation_logs')
    username = models.CharField(max_length=150, db_index=True, verbose_name='操作用户')
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP地址')
    user_agent = models.TextField(blank=True, verbose_name='User Agent')
    app_label = models.CharField(max_length=50, db_index=True, verbose_name='应用')
    model_name = models.CharField(max_length=100, db_index=True, verbose_name='模型')
    object_id = models.PositiveIntegerField(null=True, db_index=True, verbose_name='对象ID')
    object_repr = models.CharField(max_length=500, blank=True, verbose_name='对象摘要')
    action = models.CharField(max_length=10, choices=ACTION_CHOICES, verbose_name='操作类型')
    changes = models.TextField(blank=True, verbose_name='变更内容')
    approval_flow_id = models.PositiveIntegerField(null=True, blank=True, db_index=True, verbose_name='关联审批流')
    company_id = models.PositiveIntegerField(null=True, blank=True, db_index=True, verbose_name='所属公司')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='操作时间')

    class Meta:
        db_table = 'core_operation_audit_log'
        ordering = ['-created_at']
        verbose_name = '操作审计日志'
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=['app_label', 'model_name', '-created_at']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['-created_at']),
            models.Index(fields=['approval_flow_id', '-created_at']),
        ]

    def __str__(self):
        return f"{self.username} {self.get_action_display()} {self.app_label}.{self.model_name} #{self.object_id}"

    @property
    def changes_dict(self):
        import json
        try:
            return json.loads(self.changes)
        except Exception:
            return {}
