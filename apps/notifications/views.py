"""通知相关视图 — 简化版"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_preference_list(request):
    """用户通知偏好 — 查询自己的偏好设置"""
    from .models import UserNotificationPreference

    prefs = UserNotificationPreference.objects.filter(user=request.user)
    return Response(
        [
            {
                'event_type': p.event_type,
                'is_enabled': p.is_enabled,
                'allowed_channels': p.allowed_channels,
            }
            for p in prefs
        ]
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def user_preference_update(request):
    """用户通知偏好 — 更新偏好设置"""
    from .models import UserNotificationPreference

    data = request.data if isinstance(request.data, list) else [request.data]
    for item in data:
        pref, _ = UserNotificationPreference.objects.update_or_create(
            user=request.user,
            event_type=item['event_type'],
            defaults={
                'is_enabled': item.get('is_enabled', True),
                'allowed_channels': item.get('allowed_channels', []),
            },
        )
    return Response({'status': 'ok'})
