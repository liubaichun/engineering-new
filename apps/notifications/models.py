from django.db import models


class NotificationChannel(models.Model):
    """通知渠道配置 — 支持飞书/企微/钉钉 Webhook"""
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

    name = models.CharField(max_length=100, verbose_name='渠道名称')
    channel_type = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name='渠道类型')
    webhook_url = models.URLField(max_length=500, verbose_name='Webhook地址')
    secret = models.CharField(max_length=200, blank=True, default='', verbose_name='Secret密钥')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', verbose_name='状态')
    remark = models.TextField(blank=True, default='', verbose_name='备注')
    is_deleted = models.BooleanField(default=False, verbose_name='已删除')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'notifications_channel'
        ordering = ['-created_at']
        verbose_name = '通知渠道'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.name} ({self.get_channel_type_display()})"
