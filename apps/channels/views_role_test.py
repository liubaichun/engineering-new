import logging
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated

from apps.core.exceptions import api_error, ErrorCode

logger = logging.getLogger(__name__)
User = get_user_model()

from .models import ChannelPlugin, ChannelBinding, NotificationLog
from .base import ChannelRegistry


class RoleBindingListView(APIView):
    """角色-渠道绑定管理"""

    permission_classes = [IsAuthenticated]

    def get(self, request, channel_id):
        """获取某渠道的角色绑定列表"""
        channel = get_object_or_404(ChannelPlugin, id=channel_id, is_deleted=False)
        role_bindings = channel.config.get('role_bindings', [])

        User = get_user_model()
        role_ids = [rb.get('role_id') for rb in role_bindings]
        roles = {r.id: r.name for r in User.objects.filter(id__in=role_ids)}

        result = [
            {
                'role_id': rb.get('role_id'),
                'role_name': roles.get(rb.get('role_id'), f'角色{rb.get("role_id")}'),
                'enabled': rb.get('enabled', True),
            }
            for rb in role_bindings
        ]

        return Response(result)

    def post(self, request, channel_id):
        """添加/更新角色绑定"""
        channel = get_object_or_404(ChannelPlugin, id=channel_id, is_deleted=False)

        role_id = request.data.get('role_id')
        enabled = request.data.get('enabled', True)

        if not role_id:
            return api_error(ErrorCode.VALIDATION_ERROR, '缺少role_id')

        role_bindings = channel.config.get('role_bindings', [])
        found = False
        for rb in role_bindings:
            if rb.get('role_id') == role_id:
                rb['enabled'] = enabled
                found = True
                break

        if not found:
            role_bindings.append({'role_id': role_id, 'enabled': enabled})

        channel.config['role_bindings'] = role_bindings
        try:
            channel.save(update_fields=['config'])
        except Exception as e:
            return api_error(ErrorCode.INTERNAL_ERROR, f'更新角色绑定失败：{str(e)}', status_code=500)

        return Response({'message': '角色绑定已更新', 'role_bindings': role_bindings})

    def delete(self, request, channel_id):
        """删除角色绑定"""
        channel = get_object_or_404(ChannelPlugin, id=channel_id, is_deleted=False)

        role_id = request.data.get('role_id')
        if not role_id:
            return api_error(ErrorCode.VALIDATION_ERROR, '缺少role_id')

        role_bindings = channel.config.get('role_bindings', [])
        role_bindings = [rb for rb in role_bindings if str(rb.get('role_id')) != str(role_id)]
        channel.config['role_bindings'] = role_bindings
        try:
            channel.save(update_fields=['config'])
        except Exception as e:
            return api_error(ErrorCode.INTERNAL_ERROR, f'删除角色绑定失败：{str(e)}', status_code=500)

        return Response({'message': '角色绑定已删除'})


class ValidateCredentialsView(APIView):
    """验证渠道凭证"""

    permission_classes = [IsAuthenticated]

    def post(self, request, channel_id):
        channel = get_object_or_404(ChannelPlugin, id=channel_id, is_deleted=False)

        try:
            plugin = ChannelRegistry.get_plugin(channel.channel_type, channel.config)
        except Exception as e:
            import traceback

            write_audit_log(
                'channel_validate',
                request,
                channel=channel,
                detail={'channel_id': channel.id, 'error': str(e), 'trace': traceback.format_exc()},
                result='failure',
                error_message=f'插件初始化失败: {str(e)}',
            )
            return Response({'valid': False, 'message': f'插件初始化失败: {str(e)}'})

        if not plugin:
            write_audit_log(
                'channel_validate',
                request,
                channel=channel,
                detail={'channel_id': channel.id, 'plugin_found': False},
                result='failure',
                error_message='不支持的渠道类型',
            )
            return api_error(ErrorCode.VALIDATION_ERROR, '不支持的渠道类型')

        try:
            is_valid, msg = plugin.validate_credentials()
        except Exception as e:
            import traceback

            write_audit_log(
                'channel_validate',
                request,
                channel=channel,
                detail={'channel_id': channel.id, 'error': str(e), 'trace': traceback.format_exc()},
                result='failure',
                error_message=f'验证异常: {str(e)}',
            )
            return Response({'valid': False, 'message': f'验证异常: {str(e)}'})

        write_audit_log(
            'channel_validate',
            request,
            channel=channel,
            detail={
                'channel_id': channel.id,
                'channel_type': channel.channel_type,
                'result': is_valid,
                'message': msg,
            },
            result='success' if is_valid else 'failure',
            error_message='' if is_valid else msg,
        )

        return Response({'valid': is_valid, 'message': msg})


class SendTestMessageView(APIView):
    """发送测试消息"""

    permission_classes = [IsAuthenticated]

    def post(self, request, channel_id):
        channel = get_object_or_404(ChannelPlugin, id=channel_id, is_active=True, is_deleted=False)

        plugin = ChannelRegistry.get_plugin(channel.channel_type, channel.config)
        if not plugin:
            write_audit_log(
                'test_message_sent',
                request,
                channel=channel,
                detail={'channel_id': channel.id, 'plugin_found': False},
                result='failure',
                error_message='不支持的渠道类型',
            )
            return api_error(ErrorCode.VALIDATION_ERROR, '不支持的渠道类型')

        binding = ChannelBinding.objects.filter(user=request.user, channel=channel, is_active=True).first()

        if not binding:
            write_audit_log(
                'test_message_sent',
                request,
                channel=channel,
                detail={'channel_id': channel.id, 'reason': 'user_not_bound'},
                result='failure',
                error_message='用户未绑定该渠道',
            )
            return api_error(ErrorCode.PERMISSION_DENIED, '您尚未绑定该渠道，请先扫码绑定')

        test_title = '测试消息'
        test_content = '这是一条来自企业信息化管理系统的测试通知，收到此消息表示绑定成功！'

        success, msg = plugin.send_message(binding.platform_open_id, test_title, test_content)

        NotificationLog.objects.create(
            channel=channel,
            user=request.user,
            binding=binding,
            title=test_title,
            content=test_content,
            notification_type='test',
            status='sent' if success else 'failed',
            error_message=msg if not success else '',
            sent_at=timezone.now() if success else None,
        )

        write_audit_log(
            'test_message_sent',
            request,
            channel=channel,
            binding=binding,
            detail={
                'channel_id': channel.id,
                'binding_id': binding.id,
                'platform_open_id': binding.platform_open_id,
                'success': success,
                'error': msg if not success else '',
            },
            result='success' if success else 'failure',
            error_message=msg if not success else '',
        )

        if success:
            return Response({'success': True, 'message': '测试消息发送成功'})
        return api_error(ErrorCode.VALIDATION_ERROR, msg)
