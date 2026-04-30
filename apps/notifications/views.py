from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Q

from .models import NotificationChannel, NotifyBinding
from .serializers import NotificationChannelSerializer, NotifyBindingSerializer
from . import services


class NotificationChannelViewSet(viewsets.ModelViewSet):
    """通知渠道管理 API（多租户版）"""
    serializer_class = NotificationChannelSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """多租户隔离：普通用户只看自己公司的渠道；staff 可见全部"""
        user = self.request.user
        queryset = NotificationChannel.objects.filter(is_deleted=False)
        if user.is_superuser:
            return queryset
        company_id = getattr(self.request, 'company_id', None)
        if company_id:
            return queryset.filter(
                Q(company_id=company_id) | Q(company__isnull=True)
            )
        return queryset.none()

    def perform_create(self, serializer):
        serializer.save()

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
                "id": ch.id,
                "name": ch.name,
                "channel_type": ch.channel_type,
                "status": result['status'],
                "message": result['message'],
            })
        return Response({
            "total": len(results),
            "success": sum(1 for r in results if r['status'] == 'ok'),
            "failed": sum(1 for r in results if r['status'] == 'error'),
            "results": results,
        })

    @action(detail=False, methods=['get'])
    def types(self, request):
        """返回支持的渠道类型列表"""
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
                channel.channel_type,
                channel.webhook_url,
                channel.secret,
                title,
                content
            )
            return Response({"status": "ok", "message": "发送成功", "detail": result})
        except services.NotificationSendError as e:
            return Response({"status": "error", "message": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class NotifyBindingViewSet(viewsets.ModelViewSet):
    """用户通知绑定 API"""
    serializer_class = NotifyBindingSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'delete', 'patch']

    def get_queryset(self):
        """用户只看自己的绑定；staff 可管理所有"""
        user = self.request.user
        if user.is_superuser:
            return NotifyBinding.objects.all()
        return NotifyBinding.objects.filter(user=user)

    def perform_create(self, serializer):
        # 验证 channel 归属（多租户安全）
        channel = serializer.validated_data.get('channel')
        if channel:
            user = self.request.user
            company_id = getattr(self.request, 'company_id', None)
            if not user.is_superuser and company_id and channel.company_id != company_id:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("不能绑定到其他公司的通知渠道")
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['get'])
    def my_bindings(self, request):
        """获取当前用户所有有效绑定"""
        bindings = self.get_queryset().filter(is_active=True).select_related('channel', 'user')
        serializer = self.get_serializer(bindings, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def test(self, request):
        """测试绑定通道（发送测试消息到该绑定）"""
        binding_id = request.data.get('binding_id')
        title = request.data.get('title', '🔔 绑定测试')
        content = request.data.get('content', '这是一条来自工程管理系统的绑定测试消息，证明你的通知渠道配置正确。')
        try:
            binding = self.get_queryset().get(id=binding_id)
        except NotifyBinding.DoesNotExist:
            return Response({"status": "error", "message": "绑定不存在"}, status=status.HTTP_404_NOT_FOUND)

        channel = binding.channel
        if channel.status != 'active':
            return Response({"status": "error", "message": "渠道未启用"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # 注意：直接推送需要用户的 open_id，这里通过 webhook 发送
            result = services.send_notification(
                binding.platform,
                binding.channel.webhook_url,
                binding.channel.secret,
                title,
                content,
            )
            return Response({"status": "ok", "message": "发送成功", "detail": result})
        except services.NotificationSendError as e:
            return Response({"status": "error", "message": str(e)}, status=status.HTTP_400_BAD_REQUEST)
