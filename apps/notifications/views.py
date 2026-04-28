from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
import json

from apps.core.models import Notification
from apps.core.serializers import NotificationSerializer


def notification_list(request):
    """通知列表 API — 查询 core_notification 表，按当前用户筛选"""
    if not request.user.is_authenticated:
        return JsonResponse({'detail': '认证失败'}, status=401)

    queryset = Notification.objects.filter(user=request.user).select_related('user')
    is_read = request.GET.get('is_read')
    notification_type = request.GET.get('type')

    if is_read is not None:
        queryset = queryset.filter(is_read=is_read.lower() == 'true')
    if notification_type:
        queryset = queryset.filter(notification_type=notification_type)

    # 手动分页
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 20))
    total = queryset.count()
    start = (page - 1) * page_size
    end = start + page_size
    notifications = queryset.order_by('-created_at')[start:end]

    serializer = NotificationSerializer(notifications, many=True)
    results = serializer.data

    # 字段名兼容：content → message，notification_type → type
    for r in results:
        r['message'] = r.pop('content', '')
        r['type'] = r.pop('notification_type', '')

    return JsonResponse({
        'count': total,
        'total_pages': (total + page_size - 1) // page_size,
        'current_page': page,
        'results': results
    })


@require_http_methods(["POST"])
def mark_as_read(request, notification_id):
    """标记单条通知为已读"""
    if not request.user.is_authenticated:
        return JsonResponse({'detail': '认证失败'}, status=401)

    notification = get_object_or_404(
        Notification, id=notification_id, user=request.user
    )
    notification.is_read = True
    notification.save(update_fields=['is_read'])
    return JsonResponse({'status': 'success'})


@require_http_methods(["POST"])
def mark_all_read(request):
    """标记当前用户所有通知为已读"""
    if not request.user.is_authenticated:
        return JsonResponse({'detail': '认证失败'}, status=401)

    updated = Notification.objects.filter(
        user=request.user, is_read=False
    ).update(is_read=True)
    return JsonResponse({'status': 'success', 'updated': updated})


# ─────────────────────────────────────────────────────────────────────────────
# 通知创建工具函数（供其他模块调用）
# ─────────────────────────────────────────────────────────────────────────────
def create_notification(user, title, content, notification_type='system',
                       level='info', related_id=None, related_type=''):
    """
    通用通知创建函数。

    用法示例：
        from apps.notifications.views import create_notification
        create_notification(
            user=request.user,
            title='任务已超时',
            content='您负责的任务"需求调研"已超过截止日期',
            notification_type='task',
            level='warning',
            related_id=task.id,
            related_type='task'
        )
    """
    return Notification.objects.create(
        user=user,
        title=title,
        content=content,
        notification_type=notification_type,
        level=level,
        related_id=related_id,
        related_type=related_type,
    )


def notify_if_new(user, title, content, notification_type, level='info',
                  related_id=None, related_type=''):
    """
    防重复通知：同一天同一类型同一 related_id 只通知一次。
    """
    from datetime import datetime, timedelta
    cutoff = datetime.now() - timedelta(days=1)
    exists = Notification.objects.filter(
        user=user,
        notification_type=notification_type,
        related_id=related_id,
        related_type=related_type,
        created_at__gte=cutoff
    ).exists()
    if not exists:
        create_notification(user, title, content, notification_type, level,
                            related_id, related_type)
