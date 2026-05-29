import logging
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny

logger = logging.getLogger(__name__)
User = get_user_model()

from .models import ChannelPlugin, ChannelBinding, NotificationLog
from .base import ChannelRegistry


class BindingQRCodeView(APIView):
    """获取绑定二维码URL"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        channel_id = request.data.get('channel_id')
        if not channel_id:
            return Response({'error': '缺少channel_id'}, status=status.HTTP_400_BAD_REQUEST)

        channel = get_object_or_404(ChannelPlugin, id=channel_id, is_active=True, is_deleted=False)

        # 构造回调地址（不含state，state会单独传给OAuth插件）
        callback_url = request.build_absolute_uri(f'/api/channels/bind/callback/{channel.id}/')
        # OAuth state：带签名+时间戳，防会话固定攻击（10分钟有效期）
        from apps.channels.utils import make_oauth_state

        oauth_state = make_oauth_state(request.user.id)

        # 加载对应插件
        plugin = ChannelRegistry.get_plugin(channel.channel_type, channel.config)
        if not plugin:
            return Response({'error': f'不支持的渠道类型: {channel.channel_type}'}, status=status.HTTP_400_BAD_REQUEST)

        binding_url = plugin.get_binding_url(callback_url, state=oauth_state)

        # 对于不需要OAuth的渠道（如微信PushPlus），直接返回配置提示
        if not binding_url:
            return Response(
                {
                    'binding_mode': 'manual',
                    'channel_id': channel.id,
                    'channel_type': channel.channel_type,
                    'channel_name': channel.get_channel_type_display(),
                    'message': '该渠道需要手动配置，请在下方填入您的推送标识',
                }
            )

        return Response(
            {
                'binding_mode': 'oauth',
                'binding_url': binding_url,
                'channel_id': channel.id,
                'channel_type': channel.channel_type,
                'channel_name': channel.get_channel_type_display(),
            }
        )


class BindingCallbackView(APIView):
    """处理渠道OAuth回调"""

    permission_classes = [AllowAny]

    def get(self, request, channel_id):
        channel = get_object_or_404(ChannelPlugin, id=channel_id, is_deleted=False)

        # 验证 OAuth state（防会话固定攻击）
        from apps.channels.utils import verify_oauth_state

        state = request.GET.get('state')
        valid, user_id, error_reason = verify_oauth_state(state) if state else (False, None, 'state 为空')

        if not valid:
            write_audit_log(
                'oauth_callback_fail',
                request,
                channel=channel,
                detail={'error': f'state 校验失败: {error_reason}', 'state': str(state)[:50] if state else ''},
                result='failure',
                error_message=f'state 校验失败: {error_reason}',
            )
            return Response({'error': f'OAuth state 校验失败: {error_reason}'}, status=status.HTTP_400_BAD_REQUEST)

        plugin = ChannelRegistry.get_plugin(channel.channel_type, channel.config)
        if not plugin:
            return Response({'error': f'不支持的渠道类型: {channel.channel_type}'}, status=status.HTTP_400_BAD_REQUEST)

        success, result = plugin.handle_callback(request, channel)

        if success:
            user = None
            binding = None
            if user_id:
                User = get_user_model()
                try:
                    user = User.objects.get(id=user_id)
                    binding, _ = ChannelBinding.objects.update_or_create(
                        user=user,
                        channel=channel,
                        defaults={
                            'platform_open_id': result.get('open_id', ''),
                            'platform_user_info': result.get('user_info', {}),
                            'status': 'active',
                            'is_active': True,
                        },
                    )
                except User.DoesNotExist:
                    pass

            write_audit_log(
                'oauth_callback_success',
                request,
                channel=channel,
                binding=binding,
                detail={'open_id': result.get('open_id', ''), 'user_id': user_id},
                result='success',
            )

            html = """
<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <title>绑定成功</title>
    <style>
        body { font-family: 'Segoe UI', Arial, sans-serif; background: #f5f5f5; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; }
        .card { background: white; border-radius: 12px; padding: 48px 40px; text-align: center; box-shadow: 0 4px 24px rgba(0,0,0,0.1); max-width: 400px; }
        .icon { width: 72px; height: 72px; background: #10b981; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto 24px; }
        .icon svg { width: 40px; height: 40px; fill: white; }
        h2 { color: #1f2937; margin: 0 0 12px; font-size: 24px; }
        p { color: #6b7280; margin: 0 0 32px; font-size: 15px; }
        a { display: inline-block; background: #10b981; color: white; padding: 12px 32px; border-radius: 8px; text-decoration: none; font-weight: 500; }
        a:hover { background: #059669; }
    </style>
</head>
<body>
    <div class="card">
        <div class="icon">
            <svg viewBox="0 0 20 20"><path d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"/></svg>
        </div>
        <h2>绑定成功</h2>
        <p>绑定成功！您现在可以接收来自系统的通知了。</p>
        <a href="/channels/">返回渠道管理</a>
    </div>
</body>
</html>"""
            return HttpResponse(html)

        # OAuth 失败
        write_audit_log(
            'oauth_callback_fail',
            request,
            channel=channel,
            detail={'error': result.get('error', '')},
            result='failure',
            error_message=result.get('error', '未知错误'),
        )

        html = f"""
<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <title>绑定失败</title>
    <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f5f5f5; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; }}
        .card {{ background: white; border-radius: 12px; padding: 48px 40px; text-align: center; box-shadow: 0 4px 24px rgba(0,0,0,0.1); max-width: 400px; }}
        .icon {{ width: 72px; height: 72px; background: #ef4444; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto 24px; }}
        .icon svg {{ width: 40px; height: 40px; fill: white; }}
        h2 {{ color: #1f2937; margin: 0 0 12px; font-size: 24px; }}
        p {{ color: #6b7280; margin: 0 0 32px; font-size: 15px; }}
        a {{ display: inline-block; background: #ef4444; color: white; padding: 12px 32px; border-radius: 8px; text-decoration: none; font-weight: 500; }}
        a:hover {{ background: #dc2626; }}
    </style>
</head>
<body>
    <div class="card">
        <div class="icon">
            <svg viewBox="0 0 20 20"><path d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"/></svg>
        </div>
        <h2>绑定失败</h2>
        <p>绑定失败：{result.get('error', '未知错误')}。请返回后重试。</p>
        <a href="/channels/">返回渠道管理</a>
    </div>
</body>
</html>"""
        return HttpResponse(html)


class WebhookView(APIView):
    """接收各渠道的Webhook回调"""

    permission_classes = [AllowAny]

    def post(self, request, channel_id):
        """处理渠道推送的消息事件"""
        channel = get_object_or_404(ChannelPlugin, id=channel_id, is_active=True, is_deleted=False)
        plugin = ChannelRegistry.get_plugin(channel.channel_type, channel.config)
        if not plugin:
            write_audit_log(
                'webhook_received',
                request,
                channel=channel,
                detail={'received': True, 'plugin_found': False},
                result='failure',
                error_message='不支持的渠道类型',
            )
            return Response({'error': '不支持的渠道类型'}, status=400)

        # 尝试验签（plugin可选择实现）
        verify_result = None
        if hasattr(plugin, 'verify_webhook_signature'):
            verify_result = plugin.verify_webhook_signature(request, channel)
            if not verify_result.get('valid', False):
                write_audit_log(
                    'webhook_received',
                    request,
                    channel=channel,
                    detail={'received': True, 'signature_valid': False, 'ip': get_client_ip(request)},
                    result='failure',
                    error_message='验签失败: ' + str(verify_result.get('error', '')),
                )
                return Response({'error': '验签失败'}, status=401)

        # 调用 plugin 处理 webhook
        result = plugin.handle_webhook(request, channel)

        # 审计日志（无论成功失败均记录）
        notification_log_status = 'failed'
        if result is not None:
            notification_log_status = 'delivered'
            write_audit_log(
                'webhook_received',
                request,
                channel=channel,
                detail={
                    'title': result.get('title', ''),
                    'content': result.get('content', '')[:200],
                    'open_id': result.get('open_id', ''),
                    'ip': get_client_ip(request),
                },
                result='success',
            )
        else:
            write_audit_log(
                'webhook_received',
                request,
                channel=channel,
                detail={'received': True, 'handled': False},
                result='failure',
                error_message='该渠道不支持Webhook处理',
            )
            return Response({'error': '该渠道不支持Webhook处理'}, status=400)

        NotificationLog.objects.create(
            channel=channel,
            notification_type='webhook_event',
            title=result.get('title', 'Webhook事件'),
            content=result.get('content', ''),
            recipient=str(result.get('open_id', '')),
            status=notification_log_status,
        )
        return Response({'success': True, 'data': result})

    def get(self, request, channel_id):
        """验证Webhook配置（渠道商验证URL时调用）"""
        channel = get_object_or_404(ChannelPlugin, id=channel_id, is_deleted=False)
        return Response({'challenge': request.GET.get('challenge', '')})


class BindingListCreateView(APIView):
    """绑定列表、创建、删除"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """获取绑定列表
        staff 可查看所有绑定；普通用户只能查看自己的
        """
        if request.user.is_staff and request.query_params.get('all') == '1':
            bindings = (
                ChannelBinding.objects.filter(is_active=True).select_related('user', 'channel').order_by('-bound_at')
            )
        else:
            bindings = (
                ChannelBinding.objects.filter(user=request.user, is_active=True)
                .select_related('user', 'channel')
                .order_by('-bound_at')
            )

        data = [
            {
                'id': b.id,
                'user_id': b.user.id,
                'user_name': b.user.username,
                'channel_id': b.channel.id,
                'channel': {
                    'id': b.channel.id,
                    'app_name': b.channel.app_name,
                    'channel_type': b.channel.channel_type,
                    'channel_name': b.channel.get_channel_type_display(),
                },
                'platform_open_id': b.platform_open_id,
                'platform_user_info': b.platform_user_info,
                'status': b.status,
                'bound_at': b.bound_at,
            }
            for b in bindings
        ]

        return Response(data)

    def post(self, request):
        """手动绑定（适用于微信PushPlus等不需要OAuth的渠道）

        admin 可为任意用户创建绑定；普通用户只能绑定自己。
        """
        channel_id = request.data.get('channel_id')
        open_id = request.data.get('open_id', '').strip()

        # 判断目标用户：admin 可指定任意用户，否则只能绑定自己
        if request.user.is_staff and request.data.get('user_id'):
            target_user_id = int(request.data['user_id'])
            User = get_user_model()
            try:
                target_user = User.objects.get(id=target_user_id)
            except User.DoesNotExist:
                return Response(
                    {'error': f'用户不存在: target_user_id={target_user_id}'}, status=status.HTTP_400_BAD_REQUEST
                )
        else:
            target_user = request.user

        if not channel_id or not open_id:
            return Response({'error': '缺少channel_id或open_id'}, status=status.HTTP_400_BAD_REQUEST)

        channel = get_object_or_404(ChannelPlugin, id=channel_id, is_active=True, is_deleted=False)

        binding, created = ChannelBinding.objects.update_or_create(
            user=target_user,
            channel=channel,
            defaults={
                'platform_open_id': open_id,
                'platform_user_info': {'bind_mode': 'manual', 'created_by': request.user.username},
                'status': 'active',
                'is_active': True,
            },
        )

        write_audit_log(
            'bind_create',
            request,
            channel=channel,
            binding=binding,
            detail={
                'channel_id': channel.id,
                'binding_id': binding.id,
                'platform_open_id': open_id,
                'bind_mode': 'manual',
            },
            result='success',
        )

        return Response(
            {
                'id': binding.id,
                'channel_id': channel.id,
                'channel_type': channel.channel_type,
                'channel_name': channel.get_channel_type_display(),
                'platform_open_id': open_id,
                'status': 'active',
                'bound_at': binding.bound_at,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def delete(self, request):
        """解除绑定"""
        binding_id = request.data.get('binding_id')
        if not binding_id:
            return Response({'error': '缺少binding_id'}, status=status.HTTP_400_BAD_REQUEST)

        binding = get_object_or_404(ChannelBinding, id=binding_id, user=request.user)

        write_audit_log(
            'bind_delete',
            request,
            channel=binding.channel,
            binding=binding,
            detail={
                'channel_id': binding.channel_id,
                'binding_id': binding.id,
                'platform_open_id': binding.platform_open_id,
            },
            result='success',
        )

        binding.is_active = False
        try:
            binding.save()
        except Exception as e:
            return Response({'error': f'解除绑定失败：{str(e)}'}, status=500)

        return Response({'message': '解除绑定成功'})
