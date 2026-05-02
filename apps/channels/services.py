"""
通知渠道服务 — 负责将通知通过外部渠道（飞书/钉钉/企微/微信）发送

check_alerts 和其他业务模块都调用这里的 send_channel_notification()
"""
import logging
from typing import List, Optional
from django.utils import timezone

from apps.core.models import User
from apps.channels.models import ChannelPlugin, ChannelBinding, NotificationLog
from apps.channels.base import ChannelRegistry

logger = logging.getLogger('channels')


class ChannelNotificationService:
    """
    统一的通知渠道服务

    用法:
        ChannelNotificationService.send(
            user=user,
            title='合同到期预警',
            content='合同「xxx」将于3天后到期',
            notification_type='contract_alert',
        )
    """

    @classmethod
    def send(
        cls,
        user: User,
        title: str,
        content: str,
        notification_type: str = 'system',
        related_id: int = None,
        related_type: str = '',
    ) -> dict:
        """
        向用户的已绑定渠道发送通知

        Returns:
            dict: {
                'total': N,          # 尝试发送的渠道数
                'sent': M,            # 成功数
                'failed': K,          # 失败数
                'details': [...]      # 详情
            }
        """
        if not user or not user.is_active:
            return {'total': 0, 'sent': 0, 'failed': 0, 'details': []}

        # 找到用户的公司
        company_id = cls._get_user_company_id(user)
        if not company_id:
            logger.warning(f'[ChannelNotify] 用户 {user.username} 无公司，跳过外部通知')
            return {'total': 0, 'sent': 0, 'failed': 0, 'details': []}

        # 获取该公司所有已激活的渠道
        channels = ChannelPlugin.objects.filter(
            company_id=company_id,
            is_active=True
        )

        results = []
        sent_count = 0
        failed_count = 0

        for channel in channels:
            result = cls._send_via_channel(
                user=user,
                channel=channel,
                title=title,
                content=content,
                notification_type=notification_type,
            )
            results.append(result)
            if result['status'] == 'sent':
                sent_count += 1
            else:
                failed_count += 1

        return {
            'total': len(results),
            'sent': sent_count,
            'failed': failed_count,
            'details': results,
        }

    @classmethod
    def send_to_role(
        cls,
        company_id: int,
        role_name: str,
        title: str,
        content: str,
        notification_type: str = 'system',
    ) -> dict:
        """
        向公司内指定角色的所有用户发送通知

        role_name: 'admin' | 'project_manager' | 'employee' | 'finance' 等
        """
        from apps.core.models import UserCompanyRole

        # 找到该公司在该角色下的所有用户
        user_ids = UserCompanyRole.objects.filter(
            company_id=company_id,
            role=role_name,
        ).values_list('user_id', flat=True)

        total_sent = 0
        total_failed = 0
        all_details = []

        for user_id in user_ids:
            try:
                user = User.objects.get(id=user_id)
                result = cls.send(
                    user=user,
                    title=title,
                    content=content,
                    notification_type=notification_type,
                )
                total_sent += result['sent']
                total_failed += result['failed']
                all_details.extend(result['details'])
            except User.DoesNotExist:
                pass

        return {
            'total': len(user_ids),
            'sent': total_sent,
            'failed': total_failed,
            'details': all_details,
        }

    @classmethod
    def _send_via_channel(
        cls,
        user: User,
        channel: ChannelPlugin,
        title: str,
        content: str,
        notification_type: str,
    ) -> dict:
        """通过单个渠道发送"""
        # 找用户在该渠道的绑定
        binding = ChannelBinding.objects.filter(
            user=user,
            channel=channel,
            is_active=True,
        ).first()

        if not binding:
            return {
                'channel_id': channel.id,
                'channel_type': channel.channel_type,
                'channel_name': channel.get_channel_type_display(),
                'user_id': user.id,
                'username': user.username,
                'status': 'failed',
                'error': '用户未绑定该渠道',
            }

        # 加载插件
        plugin = ChannelRegistry.get_plugin(channel.channel_type, channel.config)
        if not plugin:
            return {
                'channel_id': channel.id,
                'channel_type': channel.channel_type,
                'status': 'failed',
                'error': f'插件 {channel.channel_type} 未找到',
            }

        # 发送
        try:
            success, msg = plugin.send_message(
                binding.platform_open_id,
                title,
                content,
            )
        except Exception as e:
            success = False
            msg = str(e)
            logger.exception(f'[{channel.channel_type}] 发送失败: {e}')

        # 记录日志
        NotificationLog.objects.create(
            channel=channel,
            user=user,
            binding=binding,
            title=title,
            content=content,
            notification_type=notification_type,
            status='sent' if success else 'failed',
            error_message=msg if not success else '',
            sent_at=timezone.now() if success else None,
        )

        return {
            'channel_id': channel.id,
            'channel_type': channel.channel_type,
            'channel_name': channel.get_channel_type_display(),
            'user_id': user.id,
            'username': user.username,
            'status': 'sent' if success else 'failed',
            'message': msg,
        }

    @classmethod
    def _get_user_company_id(cls, user: User) -> Optional[int]:
        """获取用户所属的公司ID"""
        from apps.core.models import UserCompanyRole

        # 先尝试直接关联
        if hasattr(user, 'company_id') and user.company_id:
            return user.company_id

        # 通过 UserCompanyRole 查找
        ucr = UserCompanyRole.objects.filter(user=user).first()
        if ucr:
            return ucr.company_id

        return None
