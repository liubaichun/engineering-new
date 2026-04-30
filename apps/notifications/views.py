from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import NotificationChannel
from .serializers import NotificationChannelSerializer
from . import services


# ============================================================
# Webhook 广播渠道（NotificationChannel）— 系统级广播
# ============================================================

class NotificationChannelViewSet(viewsets.ModelViewSet):
    """通知渠道管理 API"""
    serializer_class = NotificationChannelSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return NotificationChannel.objects.filter(is_deleted=False)

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.save(update_fields=['is_deleted'])

    @action(detail=True, methods=['post'])
    def test_connection(self, request, pk=None):
        """测试单个渠道连通性"""
        try:
            channel = self.get_object()
        except NotificationChannel.DoesNotExist:
            return Response({"status": "error", "message": "渠道不存在"}, status=status.HTTP_404_NOT_FOUND)

        result = services.test_connection(channel)
        http_status = status.HTTP_200_OK if result['status'] == 'ok' else status.HTTP_400_BAD_REQUEST
        return Response(result, status=http_status)

    @action(detail=False, methods=['post'])
    def test_all(self, request):
        """批量测试所有已启用渠道"""
        channels = self.get_queryset().filter(status='active')
        results = []
        for ch in channels:
            result = services.test_connection(ch)
            results.append({
                "id": ch.id, "name": ch.name, "channel_type": ch.channel_type,
                "status": result['status'], "message": result['message'],
            })
        return Response({
            "total": len(results),
            "success": sum(1 for r in results if r['status'] == 'ok'),
            "failed": sum(1 for r in results if r['status'] == 'error'),
            "results": results,
        })

    @action(detail=False, methods=['get'])
    def types(self, request):
        """支持的渠道类型列表"""
        return Response({
            "types": [
                {"value": "feishu", "label": "飞书", "has_secret": True},
                {"value": "wecom", "label": "企业微信", "has_secret": False},
                {"value": "dingtalk", "label": "钉钉", "has_secret": True},
                {"value": "email", "label": "邮件", "has_secret": False},
                {"value": "webhook", "label": "自定义Webhook", "has_secret": False},
            ]
        })

    @action(detail=True, methods=['post'])
    def send(self, request, pk=None):
        """向指定渠道发送测试消息"""
        try:
            channel = self.get_object()
        except NotificationChannel.DoesNotExist:
            return Response({"status": "error", "message": "渠道不存在"}, status=status.HTTP_404_NOT_FOUND)

        if channel.status != 'active':
            return Response({"status": "error", "message": "渠道未启用"}, status=status.HTTP_400_BAD_REQUEST)

        title = request.data.get('title', '测试通知')
        content = request.data.get('content', '这是一条测试消息')

        try:
            result = services.send_notification(
                channel.channel_type, channel.webhook_url, channel.secret, title, content
            )
            return Response({"status": "ok", "message": "发送成功", "detail": result})
        except services.NotificationSendError as e:
            return Response({"status": "error", "message": str(e)}, status=status.HTTP_400_BAD_REQUEST)
