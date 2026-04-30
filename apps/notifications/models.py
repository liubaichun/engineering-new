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


class NotifyBinding(models.Model):
    """用户与通知渠道的绑定关系 — 用于直接推送消息给用户"""
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
    channel = models.ForeignKey(
        NotificationChannel,
        on_delete=models.CASCADE,
        related_name='bindings',
        verbose_name='渠道'
    )
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES, verbose_name='平台')
    platform_open_id = models.CharField(max_length=200, verbose_name='平台OpenID/账号')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    receive_all = models.BooleanField(default=True, verbose_name='接收全部通知')
    bound_at = models.DateTimeField(auto_now_add=True, verbose_name='绑定时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'notifications_binding'
        verbose_name = '用户通知绑定'
        verbose_name_plural = verbose_name
        unique_together = [('user', 'channel', 'platform_open_id')]
        ordering = ['-bound_at']

    def __str__(self):
        return f"{self.user.username} → {self.platform}:{self.platform_open_id}"
