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
    # 所属公司（兼容旧数据）
    company = models.ForeignKey(
        'finance.Company',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
        verbose_name='所属公司（兼容字段）',
    )

    def is_superadmin(self):
        """系统超级管理员（is_superuser）拥有所有权限"""
        return self.is_superuser

    def has_role(self, role_code, company_id=None):
        """检查用户是否拥有指定角色（仅限系统级角色，已废弃）"""
        if self.is_superuser:
            return True
        return False

    def has_perm(self, perm_code):
        """检查用户是否拥有指定权限码（已废弃，统一走 UCP 校验）"""
        return False

    def get_permissions(self):
        """Get all permission codes for this user（已废弃）"""
        return []

    def get_roles(self):
        """获取用户所有角色名称列表（已废弃）"""
        return []

    class Meta:
        db_table = 'core_user'
        verbose_name = '用户'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.username


class Notification(models.Model):
    LEVEL_CHOICES = [
        ('info', '通知'),
        ('warning', '预警'),
        ('error', '错误'),
        ('success', '成功'),
    ]
    TYPE_CHOICES = [
        ('task_overdue', '任务超时'),
        ('approval_timeout', '审批超时'),
        ('approval', '待审批'),
        ('approval_pending', '审批待处理'),
        ('contract_expiring', '合同到期'),
        ('large_expense', '大额支出'),
        ('project_overdue', '项目超时'),
        ('wage_pending', '工资待发放'),
        ('invoice_expiry', '发票到期'),
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
        'finance.Company',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notifications',
        verbose_name='公司',
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
        ('assign_role', '分配角色'),
        ('remove_role', '移除角色'),
        ('grant_permission', '授予权限'),
        ('revoke_permission', '撤销权限'),
    ]
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='permission_logs')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, verbose_name='操作类型')
    target_user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='+', verbose_name='目标用户'
    )
    role_name = models.CharField(max_length=100, blank=True, default='', verbose_name='角色名称')
    permission_code = models.CharField(max_length=100, blank=True, default='', verbose_name='权限码')
    company = models.ForeignKey(
        'finance.Company', on_delete=models.SET_NULL, null=True, blank=True, related_name='+', verbose_name='公司'
    )
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
        return f'{self.get_action_display()} - {self.target_user}'


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


class CodingRule(models.Model):
    """编码规则配置 — 各模块自定义自动编号规则"""

    MODEL_CHOICES = [
        ('material', '物料'),
        ('client', '客户'),
        ('supplier', '供应商'),
        ('employee', '员工'),
        ('equipment', '设备'),
    ]
    model_name = models.CharField('模块', max_length=50, choices=MODEL_CHOICES, unique=True)
    prefix = models.CharField('前缀', max_length=20, default='', help_text='如 WL-, KH-, GYS-, YG-, SB-')
    include_year = models.BooleanField('包含年份', default=False, help_text='编号中加入年份')
    year_format = models.CharField('年份格式', max_length=10, default='%Y', help_text='%Y=四位数, %y=两位数')
    digit_count = models.PositiveIntegerField('流水号位数', default=4, help_text='如4位=0001')
    separator = models.CharField('分隔符', max_length=5, default='-')
    description = models.CharField('说明', max_length=200, blank=True, default='')
    company_id = models.PositiveIntegerField('所属公司', null=True, blank=True, db_index=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        db_table = 'core_coding_rule'
        verbose_name = '编码规则'
        verbose_name_plural = '编码规则'

    def __str__(self):
        return f'{self.get_model_name_display()}: {self.prefix}...'


def generate_code(model_name: str, model_class) -> str:
    """根据编码规则自动生成编号"""
    from django.utils import timezone

    try:
        rule = CodingRule.objects.get(model_name=model_name)
    except CodingRule.DoesNotExist:
        defaults = {
            'material': ('WL-', False, 4),
            'client': ('KH-', True, 4),
            'supplier': ('GYS-', True, 4),
            'employee': ('YG-', True, 4),
            'equipment': ('SB-', False, 4),
        }
        prefix, include_year, digit_count = defaults.get(model_name, ('', False, 4))
        rule = CodingRule.objects.create(
            model_name=model_name,
            prefix=prefix,
            include_year=include_year,
            digit_count=digit_count,
        )

    now = timezone.now()
    year_part = now.strftime(rule.year_format) if rule.include_year else ''
    search_prefix = f'{rule.prefix}{year_part}{rule.separator}' if year_part else rule.prefix

    last = model_class.objects.filter(code__startswith=search_prefix).order_by('-code').first()
    seq = 1
    if last and last.code:
        try:
            parts = last.code.split(rule.separator)
            last_part = parts[-1]
            if last_part.isdigit():
                seq = int(last_part) + 1
        except (ValueError, IndexError):
            seq = 1

    if year_part:
        return f'{rule.prefix}{year_part}{rule.separator}{seq:0{rule.digit_count}d}'
    return f'{rule.prefix}{seq:0{rule.digit_count}d}'


class LoginLog(models.Model):
    """登录日志"""

    STATUS_CHOICES = [
        ('success', '登录成功'),
        ('failed', '登录失败'),
    ]
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='login_logs', verbose_name='用户'
    )
    username = models.CharField(max_length=150, verbose_name='用户名')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, verbose_name='登录状态')
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP地址')
    user_agent = models.TextField(blank=True, verbose_name='User Agent')
    fail_reason = models.CharField(max_length=200, blank=True, default='', verbose_name='失败原因')
    company = models.ForeignKey(
        'finance.Company',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='login_logs',
        verbose_name='公司',
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
        return f'{self.username} - {self.get_status_display()} - {self.created_at}'


class OperationAuditLog(models.Model):
    """
    通用操作审计日志 — 覆盖所有写操作（增/删/改）
    通过 Django 信号自动记录，无需在每个视图手动调用
    """

    ACTION_CHOICES = [
        ('create', '新增'),
        ('update', '修改'),
        ('delete', '删除'),
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
        return f'{self.username} {self.get_action_display()} {self.app_label}.{self.model_name} #{self.object_id}'

    @property
    def changes_dict(self):
        import json

        try:
            return json.loads(self.changes)
        except Exception:
            return {}


# ─────────────────────────────────────────────────────────────
# Phase 2 权限矩阵：自适应模块 + 动作自注册 + 用户公司动作级授权
# ─────────────────────────────────────────────────────────────


class Module(models.Model):
    """
    模块注册表 — 每个 app 模块（如 income/wage/expense）在这里注册。
    由 register_module() 自注册写入，app 无需手动维护。
    """

    name = models.CharField(max_length=50, unique=True, verbose_name='模块名')
    label = models.CharField(max_length=100, verbose_name='显示名称')
    icon = models.CharField(max_length=50, blank=True, default='', verbose_name='图标')
    category = models.CharField(max_length=50, blank=True, default='', verbose_name='分类')
    description = models.TextField(blank=True, default='', verbose_name='描述')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'core_module'
        ordering = ['category', 'sort_order']
        verbose_name = '模块'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'{self.name} ({self.label})'


class ModuleAction(models.Model):
    """
    模块的动作定义 — 每个模块有哪些动作（read/create/update/delete/submit/pay...）。
    由 register_module() 自注册写入，完全自适应数量。
    """

    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='actions')
    name = models.CharField(max_length=50, verbose_name='动作名')
    label = models.CharField(max_length=100, verbose_name='显示名称')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    action_group = models.CharField(max_length=20, default='basic', verbose_name='动作分组')
    # 关联到系统权限码（桥接到 RoleRequired 的权限码体系）
    perm_codes = models.JSONField(default=list, verbose_name='对应权限码列表')
    bit_position = models.IntegerField(default=0, verbose_name='位掩码位置')

    ACTION_GROUP_CHOICES = [
        ('basic', '基础'),  # 查看/新建
        ('data', '数据'),  # 编辑/删除/作废
        ('flow', '流程'),  # 提交/审批/发放
        ('operation', '操作'),  # 导入/导出/核销/匹配/管理
    ]

    class Meta:
        db_table = 'core_module_action'
        unique_together = ('module', 'name')
        verbose_name = '模块动作'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'{self.module.name}.{self.name}'

    @property
    def code(self):
        """兼容旧权限码格式：module.action"""
        return f'{self.module.name}.{self.name}'


# ─────────────────────────────────────────────────────────────
# ACTION_BITS（位掩码定义）
# ─────────────────────────────────────────────────────────────

# 标准 CRUD 动作（bit 0-3）
ACTION_BITS = {
    'read': 0b0000000000000001,
    'create': 0b0000000000000010,
    'update': 0b0000000000000100,
    'delete': 0b0000000000001000,
    'approve': 0b0000000000010000,  # 审批
    'submit': 0b0000000000100000,  # 提交（工资审批流）
    'pay': 0b0000000001000000,  # 发放（工资）
    'export': 0b0000000010000000,  # 导出
    'import': 0b0000000100000000,  # 导入
    'use': 0b0000001000000000,  # 使用（设备）
    'return': 0b0000010000000000,  # 归还（设备）
    'repair': 0b0000100000000000,  # 维修（设备）
    'manage': 0b0001000000000000,  # 管理（角色/设置/配置）
    'reject': 0b0010000000000000,  # 驳回（采购审批）
    'read_log': 0b0100000000000000,  # 查看日志（通知渠道）
    '_RESERVED': 0b1000000000000000,  # 预留
}

ACTION_LABELS = {
    'read': '查看',
    'create': '新建',
    'update': '编辑',
    'delete': '删除',
    'approve': '审批',
    'submit': '提交',
    'pay': '发放',
    'export': '导出',
    'import': '导入',
    'use': '使用',
    'return': '归还',
    'repair': '维修',
    'manage': '管理',
    'reject': '驳回',
    'read_log': '查看日志',
}

# 标准 CRUD 动作列表（作为权限矩阵 UI 的默认列）
STANDARD_ACTIONS = ['read', 'create', 'update', 'delete', 'approve']


class UserModulePermission(models.Model):
    """
    用户 × 公司 × 模块 权限记录（位掩码存储）

    与旧 UserCompanyPermission 的区别：
      - 一条记录 = 一个用户在一个公司对一个模块的所有动作权限
      - 使用 granted_bits 位掩码存储所有动作（取代 1 行/动作）
      - 记录量：用户数 × 公司数 × 模块数（~300 条 vs ~16,000 条）
    """

    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name='module_permissions')
    company = models.ForeignKey('finance.Company', on_delete=models.PROTECT, related_name='module_permissions')
    module = models.ForeignKey(Module, on_delete=models.PROTECT, related_name='user_permissions')
    granted_bits = models.BigIntegerField(default=0, verbose_name='授权位掩码')

    class Meta:
        db_table = 'core_user_module_permission'
        unique_together = ('user', 'company', 'module')
        verbose_name = '用户模块权限'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'{self.user.username}@{self.company.name}/{self.module.name} bits={self.granted_bits:b}'

    def has_action(self, action_name):
        """检查是否拥有某动作的权限"""
        bit = ACTION_BITS.get(action_name)
        return bool(self.granted_bits & bit) if bit else False

    def grant(self, action_name):
        """授予某动作权限"""
        bit = ACTION_BITS.get(action_name)
        if bit:
            self.granted_bits |= bit
            self.save(update_fields=['granted_bits'])

    def revoke(self, action_name):
        """撤销某动作权限"""
        bit = ACTION_BITS.get(action_name)
        if bit:
            self.granted_bits &= ~bit
            self.save(update_fields=['granted_bits'])

    @property
    def granted_actions(self):
        """返回已授予的动作名列表"""
        return [name for name, bit in ACTION_BITS.items() if name != '_RESERVED' and (self.granted_bits & bit)]

    @property
    def is_full(self):
        """是否所有可用动作都已授权（用于侧边栏 ☑ 三态指示）"""
        return self.granted_bits == self._available_bits()

    def _available_bits(self):
        """该模块所有可用动作的位掩码"""
        bits = 0
        for act in ModuleAction.objects.filter(module=self.module):
            bit = ACTION_BITS.get(act.name)
            if bit:
                bits |= bit
        return bits


# ─────────────────────────────────────────────────────────────
# 注册表（内存缓存，App.ready() 时写入）
# ─────────────────────────────────────────────────────────────

# _MODULE_REGISTRY（内存缓存）— 仅收集，不写 DB
# finance modules.py 加载时调用 register_module() 只是往这里注册
# 真正写入 DB 由 core.apps.CoreConfig.ready() 触发 post_migrate 信号来做

_MODULE_REGISTRY = {}  # name -> {name, label, icon, category, description, sort_order, actions}


def register_module(name, label, icon='', category='', description='', sort_order=0, actions=None):
    """
    自注册收集函数。只往内存缓存_REGISTRY写，不写DB。
    finance modules.py 末尾调用此函数，只是把模块定义注册到内存。
    真正写入DB在 post_migrate 信号中（表创建好之后）。
    """
    _MODULE_REGISTRY[name] = {
        'name': name,
        'label': label,
        'icon': icon,
        'category': category,
        'description': description,
        'sort_order': sort_order,
        'actions': actions or [],
    }


def sync_modules_to_db():
    """
    将内存中的模块注册表写入 DB，并清理已废弃的旧模块。
    只在 post_migrate 信号或启动时调用，此时表已存在。
    """
    from django.db import transaction

    registered_names = set()

    for name, data in _MODULE_REGISTRY.items():
        registered_names.add(name)
        defaults = {
            'label': data['label'],
            'icon': data.get('icon', ''),
            'category': data.get('category', ''),
            'description': data.get('description', ''),
            'sort_order': data.get('sort_order', 0),
        }
        module_obj, _ = Module.objects.update_or_create(name=name, defaults=defaults)

        if data.get('actions'):
            # 收集当前注册的动作名
            current_action_names = {act['name'] for act in data['actions']}
            with transaction.atomic():
                for act in data['actions']:
                    act_name = act['name']
                    perm_codes = act.get('perm_codes', [])
                    ModuleAction.objects.update_or_create(
                        module=module_obj,
                        name=act_name,
                        defaults={
                            'label': act.get('label', act_name),
                            'sort_order': act.get('sort_order', 0),
                            'perm_codes': perm_codes,
                            'bit_position': act.get('bit_position', 0),
                        },
                    )
                # 清理：删除该模块中已废弃的动作
                stale_actions = module_obj.actions.exclude(name__in=current_action_names)
                stale_action_count = stale_actions.count()
                if stale_action_count:
                    stale_actions.delete()

    # ── 清理：删除已废弃的旧模块 ──────────────────────────────
    # 凡是当前 _MODULE_REGISTRY 中不存在的模块，全部删除（连带 ModuleAction）
    if registered_names:
        stale_modules = Module.objects.exclude(name__in=registered_names)
        stale_count = stale_modules.count()
        if stale_count:
            stale_modules.delete()
