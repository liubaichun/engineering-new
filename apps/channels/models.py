"""通知渠道 — 简化为两个核心模型"""

from django.db import models
from apps.finance.models import Company


class Channel(models.Model):
    """渠道配置 — 公司级的通知通道"""

    CHANNEL_TYPES = [
        ('feishu', '飞书'),
        ('wecom', '企业微信'),
        ('dingtalk', '钉钉'),
        ('email', '邮件'),
        ('sms', '短信'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='channels')
    channel_type = models.CharField('渠道类型', max_length=20, choices=CHANNEL_TYPES)
    name = models.CharField('渠道名称', max_length=50, blank=True, default='', db_column='app_name')
    config = models.JSONField('配置', default=dict, blank=True)
    is_active = models.BooleanField('是否启用', default=True)

    usage = models.CharField(
        '用途',
        max_length=20,
        choices=[('broadcast', '群通知'), ('personal', '私信通知')],
        default='personal',
    )

    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'channels_plugin'
        verbose_name = '通知渠道'
        verbose_name_plural = '通知渠道'
        # 保留了旧表名 channnels_plugin，但去掉无用的字段定义
        # connection_mode / pairing_mode / usage / is_deleted / plugin_name / app_name 字段仍在表中但不使用

    def __str__(self):
        return f'{self.company.name} - {self.get_channel_type_display()} - {self.name}'


class ChannelBinding(models.Model):
    """用户绑定 — 用户与平台账号的绑定关系"""

    STATUS_CHOICES = [
        ('pending', '待确认'),
        ('active', '已激活'),
        ('inactive', '已失效'),
    ]

    user = models.ForeignKey('core.User', on_delete=models.CASCADE, related_name='channel_bindings')
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name='bindings')
    platform_open_id = models.CharField('平台用户ID', max_length=128)
    platform_user_info = models.JSONField('平台用户信息', default=dict, blank=True)
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='active')
    is_active = models.BooleanField('是否有效', default=True)
    bound_at = models.DateTimeField('绑定时间', auto_now_add=True)
    last_active_at = models.DateTimeField('最后活跃', auto_now=True)

    class Meta:
        db_table = 'channels_binding'
        unique_together = ['user', 'channel']
        verbose_name = '用户绑定'
        verbose_name_plural = '用户绑定'

    def __str__(self):
        return f'{self.user.username} -> {self.channel}'


# ── 向后兼容别名（旧代码仍可使用 ChannelPlugin 引用）──
ChannelPlugin = Channel


class NotificationLog(models.Model):
    """通知发送日志"""

    STATUS_CHOICES = [
        ('pending', '待发送'),
        ('sent', '已发送'),
        ('failed', '发送失败'),
        ('read', '已读'),
    ]

    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name='notification_logs')
    user = models.ForeignKey('core.User', on_delete=models.CASCADE, related_name='notification_logs')
    title = models.CharField('标题', max_length=200)
    content = models.TextField('内容')
    notification_type = models.CharField('通知类型', max_length=50)
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField('错误信息', blank=True)
    sent_at = models.DateTimeField('发送时间', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'channels_notification_log'
        ordering = ['-created_at']
        verbose_name = '通知日志'
        verbose_name_plural = '通知日志'
