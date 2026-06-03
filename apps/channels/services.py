"""通知服务 — 统一发送接口

用法：
    send_notification(company_id=1, title='通知', content='内容')
        → 给该公司所有有绑定的用户发通知（走他们绑定的所有渠道）

    send_notification(company_id=1, title='通知', content='内容', user_ids=[1,2])
        → 只发给指定用户

    send_notification(company_id=1, title='通知', content='内容', broadcast=True)
        → 发到公司所有渠道的群（公告广播）
"""

import logging
from django.utils import timezone
from .models import Channel, ChannelBinding, NotificationLog
from .base import ChannelRegistry

logger = logging.getLogger('channels')


def send_notification(company_id, title, content, user_ids=None, notification_type='system', broadcast=False):
    """
    统一通知发送函数

    参数:
        company_id: 公司ID
        title: 通知标题
        content: 通知内容（支持Markdown）
        user_ids: 指定用户ID列表（可选），为空时发所有有绑定的用户
        notification_type: 通知类型（system/approval/contract/task/project/equipment）
        broadcast: 是否群发广播（发到群/webhook，不依赖用户绑定）

    返回:
        {'total': N, 'sent': M, 'failed': K, 'details': [...]}
    """
    if not company_id:
        return {'total': 0, 'sent': 0, 'failed': 0, 'details': []}

    channels = Channel.objects.filter(company_id=company_id, is_active=True)
    if not channels:
        return {'total': 0, 'sent': 0, 'failed': 0, 'details': [], 'message': '未配置通知渠道'}

    results = []
    sent_count = 0
    failed_count = 0

    for channel in channels:
        plugin = ChannelRegistry.get_plugin(channel.channel_type, channel.config)
        if not plugin:
            continue

        # 广播模式：发到群/webhook（open_id=''）
        if broadcast:
            success, msg = plugin.send_message('', title, content)
            if success:
                sent_count += 1
            else:
                failed_count += 1
            results.append({
                'channel_id': channel.id,
                'channel_type': channel.channel_type,
                'mode': 'broadcast',
                'status': 'sent' if success else 'failed',
                'message': msg,
            })
            continue

        # 私信模式：发给指定用户
        target_users = user_ids if user_ids else None
        bindings = ChannelBinding.objects.filter(
            channel=channel,
            is_active=True,
        )
        if target_users:
            bindings = bindings.filter(user_id__in=target_users)

        for binding in bindings.select_related('user'):
            success, msg = plugin.send_message(binding.platform_open_id, title, content)
            if success:
                sent_count += 1
            else:
                failed_count += 1

            NotificationLog.objects.create(
                channel=channel,
                user=binding.user,
                title=title,
                content=content,
                notification_type=notification_type,
                status='sent' if success else 'failed',
                error_message=msg if not success else '',
                sent_at=timezone.now() if success else None,
            )

            results.append({
                'user_id': binding.user.id,
                'username': binding.user.username,
                'channel_type': channel.channel_type,
                'status': 'sent' if success else 'failed',
                'message': msg,
            })

    return {
        'total': len(results),
        'sent': sent_count,
        'failed': failed_count,
        'details': results,
    }
