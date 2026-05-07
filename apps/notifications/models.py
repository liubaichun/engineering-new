from django.db import models
from django.conf import settings


class AllObjectsManager(models.Manager):
    """提供 all_objects 查询能力（包含软删除）"""
    def get_queryset(self):
        return super().get_queryset()


class NotificationChannel(models.Model):
    """通知渠道配置 — 支持飞书/企微/钉钉 Webhook（多租户版本）"""
    TYPE_CHOICES = [
        ('feishu', '飞书'),
        ('wecom', '企业微信'),
        ('dingtalk', '钉钉'),
        ('email', '邮件'),
        ('webhook', '自定义Webhook'),
    ]
    STATUS_CHOICES = [
        ('active', '启用'),
        ('inactive', '停用'),
    ]

    company = models.ForeignKey(
        'finance.Company',
        on_delete=models.CASCADE,
        related_name='notification_channels',
        verbose_name='所属公司',
        null=True, blank=True,
        help_text='关联公司；系统超级管理员可见所有渠道'
    )
    name = models.CharField(max_length=100, verbose_name='渠道名称')
    channel_type = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name='渠道类型')
    webhook_url = models.URLField(max_length=500, verbose_name='Webhook地址')
    secret = models.CharField(max_length=200, blank=True, default='', verbose_name='Secret密钥')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', verbose_name='状态')
    remark = models.TextField(blank=True, default='', verbose_name='备注')
    is_deleted = models.BooleanField(default=False, verbose_name='已删除')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    objects = models.Manager()
    all_objects = AllObjectsManager()

    class Meta:
        db_table = 'notifications_channel'
        ordering = ['-created_at']
        verbose_name = '通知渠道'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.name} ({self.get_channel_type_display()})"


class NotifyApp(models.Model):
    """通知应用 — 对应数据库 notify_app 表"""
    TYPE_CHOICES = [
        ('feishu', '飞书'),
        ('wecom', '企业微信'),
        ('qq', 'QQ 机器人'),
        ('telegram', 'Telegram'),
        ('email', '邮件'),
    ]
    CONNECTION_MODE_CHOICES = [
        ('websocket', 'WebSocket 长连接'),
        ('webhook', 'Webhook 回调'),
    ]
    PAIRING_MODE_CHOICES = [
        ('pairing', '配对模式（用户扫码+发消息自动绑定）'),
        ('allowlist', '白名单模式（手动添加用户 open_id）'),
    ]

    company = models.ForeignKey(
        'finance.Company',
        on_delete=models.CASCADE,
        related_name='notify_apps',
        verbose_name='所属公司',
        null=True, blank=True,
    )
    channel_type = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name='渠道类型')
    app_name = models.CharField(
        max_length=100,
        verbose_name='应用名称',
        help_text='显示在用户端的机器人名称，如"工程管理系统通知小助手"'
    )
    app_id = models.CharField(
        max_length=100, blank=True,
        verbose_name='App ID / Client ID',
        help_text='飞书 CLI_xxx / 企微 CorpID / QQ AppID'
    )
    app_secret = models.CharField(
        max_length=200, blank=True,
        verbose_name='App Secret / Client Secret',
        help_text='凭证敏感字段，页面不展示明文'
    )
    webhook_url = models.URLField(max_length=500, blank=True, verbose_name='Webhook 地址')
    webhook_token = models.CharField(max_length=200, blank=True, verbose_name='Webhook 验证令牌')
    connection_mode = models.CharField(
        max_length=20, choices=CONNECTION_MODE_CHOICES, default='websocket',
        verbose_name='连接模式'
    )
    pairing_mode = models.CharField(
        max_length=20, choices=PAIRING_MODE_CHOICES, default='pairing',
        verbose_name='配对模式'
    )
    allow_from = models.TextField(
        blank=True,
        verbose_name='白名单 open_id',
        help_text='配对模式下可留空；白名单模式下填入允许的 open_id，逗号分隔'
    )
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    binding_count = models.PositiveIntegerField(default=0, verbose_name='已绑定用户数')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager()

    class Meta:
        db_table = 'notify_app'
        ordering = ['-created_at']
        verbose_name = '通知应用'
        verbose_name_plural = verbose_name
        unique_together = [('company', 'channel_type', 'app_name')]

    def __str__(self):
        return f"{self.app_name} ({self.get_channel_type_display()})"


class NotifyBinding(models.Model):
    """用户与通知应用的绑定关系 — 用于直接推送消息给用户"""
    PLATFORM_CHOICES = [
        ('feishu', '飞书'),
        ('wecom', '企业微信'),
        ('dingtalk', '钉钉'),
        ('email', '邮件'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notify_bindings',
        verbose_name='用户'
    )
    notify_app = models.ForeignKey(
        NotifyApp,
        on_delete=models.CASCADE,
        related_name='bindings',
        verbose_name='通知应用'
    )
    channel = models.ForeignKey(
        NotificationChannel,
        on_delete=models.SET_NULL,
        related_name='bindings',
        verbose_name='推送渠道',
        null=True, blank=True
    )
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES, default='feishu', verbose_name='平台')
    platform_open_id = models.CharField(max_length=100, verbose_name='平台 Open ID')
    platform_display_name = models.CharField(max_length=200, blank=True, verbose_name='平台显示名')
    is_active = models.BooleanField(default=True, verbose_name='是否有效')
    receive_all = models.BooleanField(default=True, verbose_name='接收全部通知')
    notify_contract = models.BooleanField(default=True, verbose_name='合同通知')
    notify_equipment = models.BooleanField(default=True, verbose_name='设备通知')
    notify_project = models.BooleanField(default=True, verbose_name='项目通知')
    notify_approval = models.BooleanField(default=True, verbose_name='审批通知')
    notify_wage = models.BooleanField(default=True, verbose_name='工资通知')
    bound_at = models.DateTimeField(auto_now_add=True, verbose_name='绑定时间')
    last_notified_at = models.DateTimeField(null=True, blank=True, verbose_name='最后通知时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    objects = models.Manager()
    all_objects = AllObjectsManager()

    class Meta:
        db_table = 'notify_binding'
        verbose_name = '用户通知绑定'
        verbose_name_plural = verbose_name
        unique_together = [('user', 'notify_app')]
        ordering = ['-bound_at']

    def __str__(self):
        return f"{self.user.username} → {self.platform}:{self.platform_open_id}"


class NotificationLog(models.Model):
    """通知发送日志"""
    NOTIFY_TYPE_CHOICES = [
        ('contract', '合同通知'),
        ('equipment', '设备通知'),
        ('project', '项目通知'),
        ('approval', '审批通知'),
        ('wage', '工资通知'),
        ('system', '系统通知'),
    ]
    STATUS_CHOICES = [
        ('pending', '待发送'),
        ('sent', '已发送'),
        ('failed', '发送失败'),
        ('read', '已读'),
    ]

    binding = models.ForeignKey(
        NotifyBinding,
        on_delete=models.CASCADE,
        related_name='logs',
        verbose_name='绑定记录'
    )
    title = models.CharField(max_length=200, verbose_name='通知标题')
    content = models.TextField(blank=True, verbose_name='通知内容')
    notify_type = models.CharField(
        max_length=30,
        choices=NOTIFY_TYPE_CHOICES,
        verbose_name='通知类型',
        help_text='contract/equipment/project/approval/wage/system'
    )
    related_id = models.IntegerField(null=True, blank=True, verbose_name='关联记录ID')
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='发送状态'
    )
    error_message = models.TextField(blank=True, verbose_name='错误信息')
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name='发送时间')
    created_at = models.DateTimeField(auto_now_add=True)

    objects = models.Manager()

    class Meta:
        db_table = 'notify_log'
        ordering = ['-created_at']
        verbose_name = '通知日志'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"
