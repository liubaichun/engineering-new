from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Q

from .models import NotificationChannel, NotifyBinding, NotificationRouter
from .serializers import NotificationChannelSerializer, NotifyBindingSerializer
from . import services


class NotificationChannelViewSet(viewsets.ModelViewSet):
    """通知渠道管理 API（多租户版）"""
    serializer_class = NotificationChannelSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """多租户隔离已移除 - 所有用户可见所有通知渠道"""
        user = self.request.user
        queryset = NotificationChannel.objects.filter(is_deleted=False)
        # 所有认证用户都可访问所有渠道
        return queryset

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
        # 多租户隔离已移除 - 不再验证 channel 归属
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


class UserNotificationPreferenceView:
    """用户通知偏好 — 查询和更新自己的偏好设置"""

    @staticmethod
    def list(request):
        """GET /notifications/preferences/ — 获取当前用户所有偏好"""
        from .models import UserNotificationPreference
        prefs = UserNotificationPreference.objects.filter(user=request.user)
        return Response([{
            'event_type': p.event_type,
            'is_enabled': p.is_enabled,
            'allowed_channels': p.allowed_channels,
        } for p in prefs])

    @staticmethod
    def update(request):
        """PUT /notifications/preferences/ — 批量更新偏好"""
        from .models import UserNotificationPreference
        data = request.data if isinstance(request.data, list) else [request.data]
        for item in data:
            pref, _ = UserNotificationPreference.objects.update_or_create(
                user=request.user,
                event_type=item['event_type'],
                defaults={
                    'is_enabled': item.get('is_enabled', True),
                    'allowed_channels': item.get('allowed_channels', []),
                }
            )
        return Response({'status': 'ok'})


class NotificationRouterViewSet(viewsets.ModelViewSet):
    """通知路由规则 API"""
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return NotificationRouter.objects.all().order_by('event_type', 'priority')

    def list(self, request):
        queryset = self.get_queryset()
        data = [{
            'id': r.id,
            'event_type': r.event_type,
            'priority': r.priority,
            'priority_display': r.get_priority_display(),
            'channel_type': r.channel_type,
            'recipient_scope': r.recipient_scope,
            'recipient_scope_display': r.get_recipient_scope_display(),
            'custom_user_ids': r.custom_user_ids or '',
            'is_active': r.is_active,
            'remarks': r.remarks,
        } for r in queryset]
        return Response(data)

    def create(self, request):
        from .models import NotificationRouter
        event_type = request.data.get('event_type')
        channel_type = request.data.get('channel_type')
        if not event_type or not channel_type:
            return Response({'error': 'event_type 和 channel_type 必填'}, status=status.HTTP_400_BAD_REQUEST)
        obj = NotificationRouter.objects.create(
            event_type=event_type,
            priority=request.data.get('priority', 'normal'),
            channel_type=channel_type,
            recipient_scope=request.data.get('recipient_scope', 'owner'),
            custom_user_ids=request.data.get('custom_user_ids', ''),
            is_active=request.data.get('is_active', True),
            remarks=request.data.get('remarks', ''),
        )
        return Response({
            'id': obj.id,
            'event_type': obj.event_type,
            'priority': obj.priority,
            'channel_type': obj.channel_type,
            'recipient_scope': obj.recipient_scope,
            'is_active': obj.is_active,
        }, status=status.HTTP_201_CREATED)

    def partial_update(self, request, pk=None):
        from .models import NotificationRouter
        try:
            obj = NotificationRouter.objects.get(id=pk)
        except NotificationRouter.DoesNotExist:
            return Response({'error': '规则不存在'}, status=status.HTTP_404_NOT_FOUND)
        for field in ['priority', 'channel_type', 'recipient_scope', 'custom_user_ids', 'is_active', 'remarks']:
            if field in request.data:
                setattr(obj, field, request.data[field])
        obj.save()
        return Response({
            'id': obj.id,
            'event_type': obj.event_type,
            'priority': obj.priority,
            'channel_type': obj.channel_type,
            'recipient_scope': obj.recipient_scope,
            'is_active': obj.is_active,
        })

    def destroy(self, request, pk=None):
        from .models import NotificationRouter
        try:
            obj = NotificationRouter.objects.get(id=pk)
        except NotificationRouter.DoesNotExist:
            return Response({'error': '规则不存在'}, status=status.HTTP_404_NOT_FOUND)
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
