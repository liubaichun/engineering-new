from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from .models import NotificationChannel
from .serializers import NotificationChannelSerializer


class NotificationChannelViewSet(viewsets.ModelViewSet):
    """通知渠道管理 API"""
    serializer_class = NotificationChannelSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # 软删除过滤
        return NotificationChannel.objects.filter(is_deleted=False)

    def perform_create(self, serializer):
        serializer.save()

    def perform_destroy(self, instance):
        # 软删除
        instance.is_deleted = True
        instance.save(update_fields=['is_deleted'])
