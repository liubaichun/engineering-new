import logging
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated

logger = logging.getLogger(__name__)
User = get_user_model()

from .models import ChannelPlugin, ChannelBinding, NotificationLog, ChannelAuditLog
from .base import ChannelRegistry
from apps.core.services import get_active_company_id


class SendNotificationView(APIView):
    """发送通知"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        user_ids = request.data.get('user_ids', [])
        channel_id = request.data.get('channel_id')
        title = request.data.get('title', '')
        content = request.data.get('content', '')
        notification_type = request.data.get('notification_type', 'system')

        if not all([channel_id, title, content]):
            return Response({'error': '缺少必要参数'}, status=status.HTTP_400_BAD_REQUEST)

        channel = get_object_or_404(ChannelPlugin, id=channel_id, is_active=True, is_deleted=False)

        plugin = ChannelRegistry.get_plugin(channel.channel_type, channel.config)
        if not plugin:
            return Response({'error': '不支持的渠道类型'}, status=status.HTTP_400_BAD_REQUEST)

        User = get_user_model()
        company_id = get_active_company_id(request)

        if user_ids:
            users = User.objects.filter(id__in=user_ids, is_active=True)
        elif company_id:
            users = User.objects.filter(company_id=company_id, is_active=True)
        else:
            return Response({'error': '无法确定公司'}, status=status.HTTP_400_BAD_REQUEST)

        results = []
        for user in users:
            binding = ChannelBinding.objects.filter(user=user, channel=channel, is_active=True).first()

            if not binding:
                results.append(
                    {'user_id': user.id, 'username': user.username, 'status': 'failed', 'error': '用户未绑定该渠道'}
                )
                continue

            success, msg = plugin.send_message(binding.platform_open_id, title, content)

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

            results.append(
                {
                    'user_id': user.id,
                    'username': user.username,
                    'status': 'sent' if success else 'failed',
                    'message': msg,
                }
            )

        return Response(
            {
                'total': len(results),
                'sent': len([r for r in results if r['status'] == 'sent']),
                'failed': len([r for r in results if r['status'] == 'failed']),
                'results': results,
            }
        )


# ========== 辅助函数 ==========


def get_client_ip(request):
    """从请求中提取真实IP（兼顾反向代理）"""
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def write_audit_log(action, request, channel=None, binding=None, detail=None, result='success', error_message=''):
    """
    写入审计日志的标准化入口。
    CNAS/CMA 要求：所有敏感操作必须同步写入，不得异步或批量。
    """
    user = request.user if request.user.is_authenticated else None
    ChannelAuditLog.objects.create(
        user=user,
        user_ip=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:512],
        channel=channel,
        binding=binding,
        action=action,
        detail=detail or {},
        result=result,
        error_message=error_message,
    )


def send_notification(user, channel, title, content, notification_type='system'):
    """内部通知函数"""
    binding = ChannelBinding.objects.filter(user=user, channel=channel, is_active=True).first()
    if not binding:
        return False, '用户未绑定该渠道'

    plugin = ChannelRegistry.get_plugin(channel.channel_type, channel.config)
    if not plugin:
        return False, '不支持的渠道类型'

    success, msg = plugin.send_message(binding.platform_open_id, title, content)

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

    return success, msg


class NotificationLogView(APIView):
    """通知日志列表+导出"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        company_id = get_active_company_id(request)
        if not company_id and not (request.user.is_superuser or request.user.is_staff):
            return Response(
                {
                    'error': '无权访问',
                    'debug': {
                        'auth_company': str(getattr(request, 'auth_company', None)),
                        'company_id_attr': getattr(request, 'company_id', None),
                        'session_current_company': request.session.get('current_company_id'),
                        'is_super': request.user.is_superuser,
                        'is_staff': request.user.is_staff,
                        'user_id': request.user.id,
                    },
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        notification_type = request.GET.get('notification_type', '')
        channel_type = request.GET.get('channel_type', '')
        status_filter = request.GET.get('status', '')
        date_from = request.GET.get('date_from', '')
        date_to = request.GET.get('date_to', '')

        queryset = NotificationLog.objects.select_related('channel', 'user', 'binding').order_by('-created_at')

        if company_id:
            queryset = queryset.filter(channel__company_id=company_id)
        if notification_type:
            queryset = queryset.filter(notification_type=notification_type)
        if channel_type:
            queryset = queryset.filter(channel__channel_type=channel_type)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)

        # 统计
        total_qs = (
            NotificationLog.objects.filter(channel__company_id=company_id)
            if company_id
            else NotificationLog.objects.all()
        )
        stats = {
            'sent': total_qs.filter(status='sent').count(),
            'failed': total_qs.filter(status='failed').count(),
            'pending': total_qs.filter(status='pending').count(),
        }

        # 分页
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 50))
        start = (page - 1) * page_size
        end = start + page_size

        total = queryset.count()
        logs = queryset[start:end]

        data = []
        for log in logs:
            data.append(
                {
                    'id': log.id,
                    'channel_type': log.channel.channel_type if log.channel else None,
                    'channel_name': log.channel.get_channel_type_display() if log.channel else None,
                    'username': log.user.username if log.user else None,
                    'title': log.title,
                    'notification_type': log.notification_type,
                    'status': log.status,
                    'error_message': log.error_message or '',
                    'sent_at': log.sent_at.isoformat() if log.sent_at else None,
                    'created_at': log.created_at.isoformat() if log.created_at else None,
                }
            )

        return Response(
            {
                'total': total,
                'page': page,
                'page_size': page_size,
                'logs': data,
                'stats': stats,
            }
        )
