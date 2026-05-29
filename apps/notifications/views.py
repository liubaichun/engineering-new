"""
通知偏好 API — 保留 UserNotificationPreference 相关视图
其余旧视图已迁移到 channels 应用
"""

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
                },
            )
        return Response({'status': 'ok'})


class NotificationRouterRuleView(APIView):
    """通知路由规则 CRUD"""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk=None):
        """GET /notifications/router-rules/ 或 /notifications/router-rules/<id>/"""
        from apps.channels.models import NotificationRouterRule
        from apps.core.services import get_active_company_id

        try:
            company_id = get_active_company_id(request)
        except Exception as e:
            import traceback

            traceback.print_exc()
            return Response({'error': str(e)}, status=500)
        if not company_id:
            return Response({'error': '未选择公司'}, status=403)

        if pk:
            try:
                rule = NotificationRouterRule.objects.get(pk=pk, company_id=company_id)
            except NotificationRouterRule.DoesNotExist:
                return Response({'error': '规则不存在'}, status=404)
            return Response(self._rule_to_dict(rule))

        rules = NotificationRouterRule.objects.filter(company_id=company_id)
        return Response([self._rule_to_dict(r) for r in rules])

    def post(self, request):
        """POST /notifications/router-rules/"""
        from apps.channels.models import NotificationRouterRule
        from apps.core.services import get_active_company_id

        company_id = get_active_company_id(request)
        if not company_id:
            return Response({'error': '未选择公司'}, status=403)

        data = request.data
        rule = NotificationRouterRule.objects.create(
            event_type=data['event_type'],
            priority=data.get('priority', 'normal'),
            channel_type=data['channel_type'],
            recipient_scope=data.get('recipient_scope', 'all'),
            custom_user_ids=data.get('custom_user_ids', ''),
            is_active=data.get('is_active', True),
            remarks=data.get('remarks', ''),
            company_id=company_id,
            created_by=request.user,
        )
        return Response(self._rule_to_dict(rule), status=201)

    def patch(self, request, pk=None):
        """PATCH /notifications/router-rules/<id>/"""
        from apps.channels.models import NotificationRouterRule
        from apps.core.services import get_active_company_id

        if not pk:
            return Response({'error': '缺少规则ID'}, status=400)

        company_id = get_active_company_id(request)
        if not company_id:
            return Response({'error': '未选择公司'}, status=403)

        try:
            rule = NotificationRouterRule.objects.get(pk=pk, company_id=company_id)
        except NotificationRouterRule.DoesNotExist:
            return Response({'error': '规则不存在'}, status=404)

        data = request.data
        for field in [
            'event_type',
            'priority',
            'channel_type',
            'recipient_scope',
            'custom_user_ids',
            'is_active',
            'remarks',
        ]:
            if field in data:
                setattr(rule, field, data[field])
        try:
            rule.save()
        except Exception as e:
            return Response({'error': f'保存规则失败：{str(e)}'}, status=500)
        return Response(self._rule_to_dict(rule))

    def delete(self, request, pk=None):
        """DELETE /notifications/router-rules/<id>/"""
        from apps.channels.models import NotificationRouterRule
        from apps.core.services import get_active_company_id

        if not pk:
            return Response({'error': '缺少规则ID'}, status=400)

        company_id = get_active_company_id(request)
        if not company_id:
            return Response({'error': '未选择公司'}, status=403)

        deleted, _ = NotificationRouterRule.objects.filter(pk=pk, company_id=company_id).delete()
        if not deleted:
            return Response({'error': '规则不存在'}, status=404)
        return Response(status=204)

    def _rule_to_dict(self, rule):
        priority_display_map = {'low': '低', 'normal': '普通', 'important': '重要', 'critical': '紧急'}
        recipient_scope_display_map = {
            'all': '全部人员',
            'admins': '管理员',
            'involved': '相关人员',
            'custom': '自定义',
        }
        return {
            'id': rule.id,
            'event_type': rule.event_type,
            'priority': rule.priority,
            'priority_display': priority_display_map.get(rule.priority, rule.priority),
            'channel_type': rule.channel_type,
            'recipient_scope': rule.recipient_scope,
            'recipient_scope_display': recipient_scope_display_map.get(rule.recipient_scope, rule.recipient_scope),
            'custom_user_ids': rule.custom_user_ids,
            'is_active': rule.is_active,
            'remarks': rule.remarks,
        }
