"""
通知偏好 API — 保留 UserNotificationPreference 相关视图
其余旧视图已迁移到 channels 应用
"""
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


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
