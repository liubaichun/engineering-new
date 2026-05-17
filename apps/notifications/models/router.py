"""
通知路由表 — 按事件类型/角色/公司分发到不同渠道
"""
from django.db import models


class NotificationRouter(models.Model):
    """
    通知路由规则：定义某类事件默认走哪个外部渠道发给哪些人
    支持公司级别覆盖（company_id=null 为全局规则）
    """

    PRIORITY_CHOICES = [
        ('low', '低'),
        ('normal', '普通'),
        ('important', '重要'),
        ('critical', '紧急'),
    ]

    RECIPIENT_SCOPE_CHOICES = [
        ('owner', '负责人'),
        ('requester', '申请人'),
        ('all', '全部相关人'),
        ('custom', '自定义用户'),
    ]

    event_type = models.CharField(
        max_length=50,
        db_index=True,
        help_text='事件类型，如 task_created / approval_transferred / contract_approved 等'
    )
    priority = models.CharField(
        max_length=10, default='normal',
        choices=PRIORITY_CHOICES,
        help_text='优先级，低→高'
    )
    channel_type = models.CharField(
        max_length=20, db_index=True,
        help_text='feishu / wecom / dingtalk / email 等'
    )
    recipient_scope = models.CharField(
        max_length=20, default='owner',
        choices=RECIPIENT_SCOPE_CHOICES,
        help_text='owner=负责人 / requester=申请人 / all=全部相关人 / custom=自定义'
    )
    custom_user_ids = models.TextField(
        blank=True, default='',
        help_text='custom时填写的用户ID列表，逗号分隔'
    )
    company_id = models.BigIntegerField(
        null=True, blank=True, db_index=True,
        help_text='null表示全局生效，非null优先于全局规则'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    remarks = models.TextField(blank=True, default='', help_text='路由说明/用途')

    class Meta:
        db_table = 'notification_router'
        ordering = ['event_type', 'priority', 'channel_type']
        verbose_name = '通知路由'
        verbose_name_plural = '通知路由'

    def __str__(self):
        return f'{self.event_type} → {self.channel_type}({self.recipient_scope})'