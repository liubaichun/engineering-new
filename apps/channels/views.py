"""通知渠道视图 — 简化版"""

import logging
from django.core.signing import TimestampSigner
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.views import View
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import Channel, ChannelBinding, NotificationLog
from .base import ChannelRegistry

logger = logging.getLogger(__name__)


class ChannelListView(APIView):
    """渠道列表 / 创建"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        channels = Channel.objects.filter(is_active=True).order_by('-created_at')
        data = []
        for ch in channels:
            plugin = ChannelRegistry.get_plugin(ch.channel_type, ch.config)
            valid = plugin is not None
            icon_map = {'feishu': 'bi-send', 'wecom': 'bi-building', 'dingtalk': 'bi-chat-dots'}
            data.append(
                {
                    'id': ch.id,
                    'channel_type': ch.channel_type,
                    'channel_name': ch.get_channel_type_display(),
                    'name': ch.name,
                    'usage': ch.usage,
                    'is_active': ch.is_active,
                    'valid': valid,
                    'icon': icon_map.get(ch.channel_type, 'bi-bell'),
                }
            )
        return Response(data)

    def post(self, request):
        channel_type = request.data.get('channel_type')
        name = request.data.get('name', '')
        config = request.data.get('config', {})

        if not channel_type:
            return Response({'error': '请选择渠道类型'}, status=400)

        if not ChannelRegistry.is_registered(channel_type):
            return Response({'error': f'不支持的渠道类型: {channel_type}'}, status=400)

        # 取用户当前公司
        company_id = request.session.get('current_company_id')
        if not company_id:
            from apps.core.services import get_active_company_id

            company_id = get_active_company_id(request)
        if not company_id:
            return Response({'error': '无法确定公司'}, status=400)

        channel, created = Channel.objects.update_or_create(
            company_id=company_id,
            channel_type=channel_type,
            defaults={
                'name': name,
                'config': config,
                'usage': request.data.get('usage', 'personal'),
                'is_active': True,
            },
        )
        return Response({'id': channel.id, 'channel_type': channel.channel_type}, status=201 if created else 200)


class ChannelDetailView(APIView):
    """渠道详情 / 更新 / 删除"""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        channel = get_object_or_404(Channel, id=pk)
        return Response(
            {
                'id': channel.id,
                'channel_type': channel.channel_type,
                'channel_name': channel.get_channel_type_display(),
                'name': channel.name,
                'usage': channel.usage,
                'is_active': channel.is_active,
                'config': channel.config,
            }
        )

    def patch(self, request, pk):
        channel = get_object_or_404(Channel, id=pk)
        if 'name' in request.data:
            channel.name = request.data['name']
        if 'config' in request.data:
            channel.config = request.data['config']
        if 'is_active' in request.data:
            channel.is_active = bool(request.data['is_active'])
        if 'usage' in request.data:
            channel.usage = request.data['usage']
        channel.save()
        return Response({'id': channel.id, 'message': '已更新'})

    def delete(self, request, pk):
        channel = get_object_or_404(Channel, id=pk)
        channel.is_active = False
        channel.save()
        return Response({'message': '渠道已停用'})


class ValidateChannelView(APIView):
    """验证渠道凭证"""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        channel = get_object_or_404(Channel, id=pk, is_active=True)
        plugin = ChannelRegistry.get_plugin(channel.channel_type, channel.config)
        if not plugin:
            return Response({'valid': False, 'message': '不支持的渠道类型'})
        valid, msg = plugin.validate_credentials()
        return Response({'valid': valid, 'message': msg})


class SendTestView(APIView):
    """发送测试消息"""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        channel = get_object_or_404(Channel, id=pk, is_active=True)
        plugin = ChannelRegistry.get_plugin(channel.channel_type, channel.config)
        if not plugin:
            return Response({'success': False, 'error': '不支持的渠道类型'})

        # 邮件渠道：使用用户指定的收件人
        recipient = request.data.get('recipient', '')
        if channel.channel_type == 'email' and recipient:
            success, msg = plugin.send_message(
                recipient,
                '测试通知',
                '这是一条来自企业信息化管理系统的测试消息，如果您收到了这条消息，说明邮件配置正确。',
            )
        else:
            # 广播测试：发到群
            success, msg = plugin.send_message(
                '', '测试通知', '这是一条来自企业信息化管理系统的测试消息，如果您收到了这条消息，说明通知渠道配置正确。'
            )
        return Response({'success': success, 'message': msg})


class BindingListCreateView(APIView):
    """用户绑定列表 / 创建 / 删除"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.is_staff and request.query_params.get('all') == '1':
            bindings = ChannelBinding.objects.filter(is_active=True).select_related('user', 'channel')
        else:
            bindings = ChannelBinding.objects.filter(user=request.user, is_active=True).select_related('channel')

        data = []
        for b in bindings:
            info = b.platform_user_info or {}
            data.append(
                {
                    'id': b.id,
                    'user_id': b.user.id,
                    'username': b.user.username,
                    'channel_id': b.channel.id,
                    'channel_type': b.channel.channel_type,
                    'channel_name': b.channel.get_channel_type_display(),
                    'platform_open_id': b.platform_open_id,
                    'user_name': info.get('name', ''),
                    'status': b.status,
                    'bound_at': b.bound_at,
                }
            )
        return Response(data)

    def post(self, request):
        channel_id = request.data.get('channel_id')
        open_id = request.data.get('open_id', '').strip()
        user_name = request.data.get('user_name', '')

        if not channel_id or not open_id:
            return Response({'error': '缺少channel_id或open_id'}, status=400)

        channel = get_object_or_404(Channel, id=channel_id, is_active=True)

        binding, created = ChannelBinding.objects.update_or_create(
            user=request.user,
            channel=channel,
            defaults={
                'platform_open_id': open_id,
                'platform_user_info': {'name': user_name, 'bind_mode': 'manual'},
                'status': 'active',
                'is_active': True,
            },
        )
        return Response({'id': binding.id, 'status': 'active'}, status=201 if created else 200)

    def delete(self, request):
        binding_id = request.data.get('binding_id')
        if not binding_id:
            return Response({'error': '缺少binding_id'}, status=400)
        binding = get_object_or_404(ChannelBinding, id=binding_id, user=request.user)
        binding.is_active = False
        binding.status = 'inactive'
        binding.save()
        return Response({'message': '已解除绑定'})


class GenerateBindQRCodeView(APIView):
    """生成扫码绑定二维码/URL"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        channel_id = request.data.get('channel_id')
        if not channel_id:
            return Response({'error': '缺少channel_id'}, status=400)

        channel = get_object_or_404(Channel, id=channel_id, is_active=True)
        plugin = ChannelRegistry.get_plugin(channel.channel_type, channel.config)

        if not plugin:
            return Response({'error': '不支持的渠道类型'}, status=400)

        # 检查插件是否支持OAuth绑定
        base_url = request.build_absolute_uri('/')[:-1]
        callback_url = f'{base_url}/api/channels/bind/callback/{channel.id}/'

        # 用TimestampSigner签名state，编码当前用户ID（防篡改+5分钟超时）
        signer = TimestampSigner()
        state = signer.sign(str(request.user.id))

        try:
            binding_url = plugin.get_binding_url(callback_url=callback_url, state=state)
        except Exception as e:
            logger.warning(f'生成绑定URL异常: {e}')
            binding_url = ''

        if binding_url:
            return Response(
                {
                    'binding_mode': 'oauth',
                    'binding_url': binding_url,
                    'channel_id': channel.id,
                    'channel_type': channel.channel_type,
                }
            )
        else:
            return Response(
                {
                    'binding_mode': 'manual',
                    'channel_id': channel.id,
                    'channel_type': channel.channel_type,
                }
            )


class BindCallbackView(View):
    """处理OAuth扫码回调 — GET请求（OAuth提供商回调后重定向到此）"""

    def get(self, request, channel_id):
        channel = get_object_or_404(Channel, id=channel_id, is_active=True)
        plugin = ChannelRegistry.get_plugin(channel.channel_type, channel.config)
        if not plugin:
            return self._result_page('绑定失败', '不支持的渠道类型', 'error', channel)

        if not hasattr(plugin, 'handle_callback'):
            return self._result_page('绑定失败', '该渠道不支持OAuth绑定', 'error', channel)

        # 从state中解析用户ID（手机扫码没有PC端的session）
        state = request.GET.get('state', '')
        user_id = None
        if state:
            try:
                signer = TimestampSigner()
                user_id = int(signer.unsign(state, max_age=300))  # 5分钟有效
            except (ValueError, Exception):
                user_id = None

        if not user_id:
            return self._result_page('绑定失败', '绑定请求已过期或无效，请重新扫码', 'error', channel)

        # 获取要绑定的系统用户
        from django.contrib.auth import get_user_model

        User = get_user_model()
        try:
            user = User.objects.get(id=user_id, is_active=True)
        except User.DoesNotExist:
            return self._result_page('绑定失败', '用户不存在或已停用', 'error', channel)

        success, data = plugin.handle_callback(request, channel)
        if not success:
            return self._result_page('绑定失败', data.get('error', '处理回调失败'), 'error', channel)

        open_id = data.get('open_id', '')
        user_info = data.get('user_info', {})

        if not open_id:
            return self._result_page('绑定失败', '获取用户标识失败', 'error', channel)

        # 创建绑定（关联到state中指定的系统用户）
        ChannelBinding.objects.update_or_create(
            user=user,
            channel=channel,
            defaults={
                'platform_open_id': open_id,
                'platform_user_info': user_info,
                'status': 'active',
                'is_active': True,
            },
        )
        return self._result_page(
            '绑定成功',
            f'系统用户「{user.username}」已成功绑定{channel.get_channel_type_display()}，可以接收通知了',
            'success',
            channel,
        )

    def _result_page(self, title, message, level, channel=None):
        icon_map = {
            'success': '&#10003;',
            'error': '&#10007;',
            'info': '&#9432;',
        }
        color_map = {
            'success': '#10b981',
            'error': '#ef4444',
            'info': '#3b82f6',
        }
        icon = icon_map.get(level, '&#9432;')
        color = color_map.get(level, '#3b82f6')
        channel_name = channel.get_channel_type_display() if channel else ''

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>绑定结果 - 企业信息化管理系统</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    display: flex; justify-content: center; align-items: center;
    min-height: 100vh; background: #f8fafc;
}}
.card {{
    background: #fff; border-radius: 16px; padding: 40px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.08); text-align: center;
    max-width: 420px; width: 90%;
}}
.icon {{
    width: 64px; height: 64px; border-radius: 50%;
    display: inline-flex; align-items: center; justify-content: center;
    font-size: 28px; color: #fff; margin-bottom: 16px;
    background: {color};
}}
h3 {{ font-size: 18px; margin-bottom: 8px; color: #1e293b; }}
p {{ font-size: 14px; color: #64748b; line-height: 1.6; margin-bottom: 24px; }}
.btn {{
    display: inline-block; padding: 10px 24px; border-radius: 8px;
    background: {color}; color: #fff; text-decoration: none;
    font-size: 14px; transition: opacity 0.2s;
}}
.btn:hover {{ opacity: 0.85; }}
</style>
</head>
<body>
<div class="card">
    <div class="icon">{icon}</div>
    <h3>{title}</h3>
    <p>{channel_name}：{message}</p>
    <a class="btn" href="/system/notification-channels/" onclick="window.close();return false;">关闭页面</a>
</div>
<script>
// 检测是否为弹出窗口，3秒后自动关闭
if (window.opener) {{ setTimeout(function() {{ window.close(); }}, 3000); }}
</script>
</body>
</html>"""
        return HttpResponse(html, content_type='text/html; charset=utf-8')


class SendNotificationView(APIView):
    """发送通知 — 给指定用户或全体广播"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        title = request.data.get('title', '')
        content = request.data.get('content', '')
        user_ids = request.data.get('user_ids', [])  # 指定用户（空=发给当前公司所有绑定用户）
        notification_type = request.data.get('type', 'system')
        broadcast = request.data.get('broadcast', False)  # 是否群发

        if not title or not content:
            return Response({'error': '缺少标题或内容'}, status=400)

        from .services import send_notification

        result = send_notification(
            company_id=request.session.get('current_company_id'),
            title=title,
            content=content,
            user_ids=user_ids,
            notification_type=notification_type,
            broadcast=broadcast,
        )
        return Response(result)


class NotificationLogView(APIView):
    """通知日志"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        company_id = request.session.get('current_company_id')
        qs = NotificationLog.objects.select_related('channel', 'user').order_by('-created_at')
        if company_id:
            qs = qs.filter(channel__company_id=company_id)

        # 筛选
        status = request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        channel_type = request.GET.get('channel_type')
        if channel_type:
            qs = qs.filter(channel__channel_type=channel_type)

        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 50))
        total = qs.count()
        logs = qs[(page - 1) * page_size : page * page_size]

        data = []
        for log in logs:
            data.append(
                {
                    'id': log.id,
                    'channel_type': log.channel.channel_type if log.channel else None,
                    'channel_name': log.channel.get_channel_type_display() if log.channel else None,
                    'username': log.user.username if log.user else None,
                    'title': log.title,
                    'notification_type': log.notification_type,
                    'status': log.status,
                    'error_message': log.error_message or '',
                    'sent_at': log.sent_at.isoformat() if log.sent_at else None,
                    'created_at': log.created_at.isoformat(),
                }
            )

        return Response(
            {
                'total': total,
                'page': page,
                'page_size': page_size,
                'logs': data,
            }
        )
