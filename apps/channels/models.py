"""
通知渠道插件模型
每个租户可以安装多个渠道插件，每个插件独立维护绑定关系
"""
from django.db import models
from apps.finance.models import Company


class ChannelPlugin(models.Model):
    """渠道插件配置（每个公司独立）"""
    CHANNEL_TYPES = [
        ('feishu', '飞书'),
        ('wecom', '企业微信'),
        ('wechat', '微信个人号'),
        ('dingtalk', '钉钉'),
        ('email', '邮件'),
        ('sms', '短信'),
    ]
    CONNECTION_MODES = [
        ('websocket', '长连接'),
        ('webhook', 'Webhook回调'),
        ('polling', '轮询'),
    ]
    PAIRING_MODES = [
        ('qrcode', '二维码扫码'),
        ('pairing', 'DM配对'),
        ('manual', '手动绑定'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='channel_plugins')
    channel_type = models.CharField('渠道类型', max_length=20, choices=CHANNEL_TYPES)
    plugin_name = models.CharField('插件名称', max_length=50)
    app_name = models.CharField('应用名称', max_length=100, blank=True)
    
    # 连接配置
    connection_mode = models.CharField('连接模式', max_length=20, choices=CONNECTION_MODES, default='websocket')
    pairing_mode = models.CharField('配对模式', max_length=20, choices=PAIRING_MODES, default='qrcode')
    
    # 凭证（加密存储）
    config = models.JSONField('配置JSON', default=dict, blank=True)
    
    is_active = models.BooleanField('是否启用', default=True)

    # 软删除字段（CNAS/CMA 要求：关键数据不得物理删除）
    is_deleted = models.BooleanField('已删除', default=False, db_index=True)
    deleted_at = models.DateTimeField('删除时间', null=True, blank=True)
    deleted_by = models.ForeignKey(
        'core.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='deleted_channels',
        verbose_name='删除人'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'channels_plugin'
        unique_together = ['company', 'app_name']
        verbose_name = '渠道插件'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.company.name} - {self.get_channel_type_display()} - {self.app_name}"


class ChannelBinding(models.Model):
    """用户与渠道的绑定关系"""
    STATUS_CHOICES = [
        ('pending', '待确认'),
        ('active', '已激活'),
        ('inactive', '已失效'),
    ]

    user = models.ForeignKey('core.User', on_delete=models.CASCADE, related_name='channel_bindings')
    channel = models.ForeignKey(ChannelPlugin, on_delete=models.CASCADE, related_name='bindings')
    platform_open_id = models.CharField('平台OpenID', max_length=128)
    platform_user_info = models.JSONField('平台用户信息', default=dict, blank=True)
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='active')
    bound_at = models.DateTimeField('绑定时间', auto_now_add=True)
    last_active_at = models.DateTimeField('最后活跃', auto_now=True)
    is_active = models.BooleanField('是否有效', default=True)

    class Meta:
        db_table = 'channels_binding'
        unique_together = ['user', 'channel']
        verbose_name = '渠道绑定'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.user.username} -> {self.channel}"


class ChannelAuditLog(models.Model):
    """
    渠道操作审计日志
    CNAS/CMA 要求：所有敏感操作必须记录，留存 ≥ 5 年，不可删除
    """
    ACTION_CHOICES = [
        ('channel_create',       '创建渠道'),
        ('channel_update',       '更新渠道配置'),
        ('channel_delete',       '删除渠道'),
        ('channel_validate',     '验证凭证'),
        ('channel_enable',       '启用渠道'),
        ('channel_disable',      '禁用渠道'),
        ('bind_create',          '创建绑定'),
        ('bind_delete',          '解除绑定'),
        ('oauth_callback_success','OAuth回调成功'),
        ('oauth_callback_fail',  'OAuth回调失败'),
        ('webhook_received',     '接收Webhook事件'),
        ('test_message_sent',    '发送测试消息'),
        ('notification_sent',    '发送通知'),
    ]

    id = models.BigAutoField(primary_key=True)

    # 操作主体
    user = models.ForeignKey(
        'core.User', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='channel_audit_logs',
        verbose_name='操作用户'
    )
    user_ip = models.GenericIPAddressField('操作IP', null=True, blank=True)
    user_agent = models.CharField('User-Agent', max_length=512, blank=True)

    # 操作对象
    channel = models.ForeignKey(
        'ChannelPlugin', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='audit_logs',
        verbose_name='关联渠道'
    )
    binding = models.ForeignKey(
        'ChannelBinding', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='audit_logs',
        verbose_name='关联绑定'
    )

    # 操作详情
    action = models.CharField('操作类型', max_length=32, choices=ACTION_CHOICES, db_index=True)
    detail = models.JSONField('操作详情', default=dict, blank=True)
    # detail 示例：
    #   channel_create:    {channel_id, channel_type, app_name}
    #   channel_update:    {channel_id, changed_fields: [field1, field2], old_values, new_values}
    #   channel_delete:    {channel_id, app_name}
    #   channel_validate:  {channel_id, result: true/false, message}
    #   bind_create:       {channel_id, binding_id, platform_open_id}
    #   bind_delete:       {channel_id, binding_id, platform_open_id}
    #   oauth_callback:     {channel_id, success: bool, error_msg}

    # 结果
    result = models.CharField('操作结果', max_length=16,
        choices=[('success', '成功'), ('failure', '失败'), ('pending', '待定')],
        default='success', db_index=True
    )
    error_message = models.CharField('错误信息', max_length=512, blank=True)

    # 时间戳（精确到毫秒）
    created_at = models.DateTimeField('操作时间', auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'channels_audit_log'
        ordering = ['-created_at']
        verbose_name = '渠道审计日志'
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=['channel', 'created_at']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['action', 'created_at']),
        ]

    def __str__(self):
        user_str = self.user.username if self.user else '系统'
        return f"[{self.created_at}] {user_str} {self.get_action_display()} ({self.result})"


class NotificationRouterRule(models.Model):
    """通知路由规则"""
    PRIORITY_CHOICES = [
        ('low', '低'),
        ('normal', '普通'),
        ('important', '重要'),
        ('critical', '紧急'),
    ]

    event_type = models.CharField('事件类型', max_length=50)
    priority = models.CharField('优先级', max_length=20, choices=PRIORITY_CHOICES, default='normal')
    channel_type = models.CharField('渠道类型', max_length=20)
    recipient_scope = models.CharField('接收人范围', max_length=50, default='all')
    custom_user_ids = models.TextField('自定义用户ID', blank=True)
    is_active = models.BooleanField('是否启用', default=True)
    remarks = models.TextField('备注', blank=True)
    company = models.ForeignKey('finance.Company', on_delete=models.CASCADE, related_name='notification_rules')
    created_by = models.ForeignKey('core.User', on_delete=models.SET_NULL, null=True, related_name='created_rules')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'channels_notification_router_rule'
        ordering = ['-created_at']
        verbose_name = '通知路由规则'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.event_type} -> {self.channel_type}"


class NotificationLog(models.Model):
    """通知发送日志"""
    STATUS_CHOICES = [
        ('pending', '待发送'),
        ('sent', '已发送'),
        ('failed', '发送失败'),
        ('read', '已读'),
    ]

    channel = models.ForeignKey(ChannelPlugin, on_delete=models.CASCADE, related_name='notification_logs')
    user = models.ForeignKey('core.User', on_delete=models.CASCADE, related_name='notification_logs')
    binding = models.ForeignKey(ChannelBinding, on_delete=models.SET_NULL, null=True, related_name='logs')
    
    title = models.CharField('标题', max_length=200)
    content = models.TextField('内容')
    notification_type = models.CharField('通知类型', max_length=50)
    
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField('错误信息', blank=True)
    
    sent_at = models.DateTimeField('发送时间', null=True, blank=True)
    read_at = models.DateTimeField('阅读时间', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'channels_notification_log'
        ordering = ['-created_at']
        verbose_name = '通知日志'
        verbose_name_plural = verbose_name
