import logging
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

logger = logging.getLogger(__name__)

from .models import Notification
from .serializers import NotificationSerializer
from apps.core.exceptions import api_error, ErrorCode
from apps.core.permissions import RoleRequired


class NotificationViewSet(viewsets.ModelViewSet):
    """通知消息视图集"""

    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated, RoleRequired]

    def get_queryset(self):
        queryset = Notification.objects.filter(user=self.request.user)
        is_read = self.request.query_params.get('is_read')
        notification_type = self.request.query_params.get('type')

        if is_read is not None:
            queryset = queryset.filter(is_read=is_read.lower() == 'true')
        if notification_type:
            queryset = queryset.filter(notification_type=notification_type)

        return queryset.select_related('user')

    @action(detail=True, methods=['post'], url_path='mark-read')
    def mark_read(self, request, pk=None):
        """标记单条通知为已读"""
        notification = self.get_object()
        notification.is_read = True
        try:
            notification.save(update_fields=['is_read'])
        except Exception as e:
            return api_error(ErrorCode.INTERNAL_ERROR, f'标记已读失败：{str(e)}', status_code=500)
        return Response({'status': 'success'})

    @action(detail=False, methods=['post'], url_path='mark-all-read')
    def mark_all_read(self, request):
        """标记所有通知为已读"""
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({'status': 'success', 'message': '所有通知已标记为已读'})

    @action(detail=False, methods=['get'], url_path='unread-count')
    def unread_count(self, request):
        """获取未读通知数量"""
        count = Notification.objects.filter(user=request.user, is_read=False).count()
        return Response({'unread_count': count})

    @action(detail=False, methods=['delete'], url_path='clear-read')
    def clear_read(self, request):
        """清除所有已读通知"""
        deleted, _ = Notification.objects.filter(user=request.user, is_read=True).delete()
        return Response({'status': 'success', 'deleted': deleted})
