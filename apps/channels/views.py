"""
通知渠道视图
提供绑定二维码、回调处理、绑定管理等接口
"""
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated, AllowAny

from .models import ChannelPlugin, ChannelBinding, NotificationLog, ChannelAuditLog
from .base import ChannelRegistry
from apps.core.services import get_active_company_id


# ========== 绑定流程 ==========

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
            return Response({
                'binding_mode': 'manual',
                'channel_id': channel.id,
                'channel_type': channel.channel_type,
                'channel_name': channel.get_channel_type_display(),
                'message': '该渠道需要手动配置，请在下方填入您的推送标识',
            })

        return Response({
            'binding_mode': 'oauth',
            'binding_url': binding_url,
            'channel_id': channel.id,
            'channel_type': channel.channel_type,
            'channel_name': channel.get_channel_type_display(),
        })


class BindingCallbackView(APIView):
    """处理渠道OAuth回调"""
    permission_classes = [AllowAny]

    def get(self, request, channel_id):
        channel = get_object_or_404(ChannelPlugin, id=channel_id, is_deleted=False)

        # 验证 OAuth state（防会话固定攻击）
        from apps.channels.utils import verify_oauth_state
        state = request.GET.get('state')
        valid, user_id, error_reason = verify_oauth_state(state) if state else (False, None, "state 为空")

        if not valid:
            write_audit_log(
                'oauth_callback_fail', request,
                channel=channel,
                detail={'error': f'state 校验失败: {error_reason}', 'state': str(state)[:50] if state else ''},
                result='failure',
                error_message=f'state 校验失败: {error_reason}'
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
                        }
                    )
                except User.DoesNotExist:
                    pass

            write_audit_log(
                'oauth_callback_success', request,
                channel=channel, binding=binding,
                detail={'open_id': result.get('open_id', ''), 'user_id': user_id},
                result='success'
            )

            html = f"""
<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <title>绑定成功</title>
    <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f5f5f5; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; }}
        .card {{ background: white; border-radius: 12px; padding: 48px 40px; text-align: center; box-shadow: 0 4px 24px rgba(0,0,0,0.1); max-width: 400px; }}
        .icon {{ width: 72px; height: 72px; background: #10b981; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto 24px; }}
        .icon svg {{ width: 40px; height: 40px; fill: white; }}
        h2 {{ color: #1f2937; margin: 0 0 12px; font-size: 24px; }}
        p {{ color: #6b7280; margin: 0 0 32px; font-size: 15px; }}
        a {{ display: inline-block; background: #10b981; color: white; padding: 12px 32px; border-radius: 8px; text-decoration: none; font-weight: 500; }}
        a:hover {{ background: #059669; }}
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
            'oauth_callback_fail', request,
            channel=channel,
            detail={'error': result.get('error', '')},
            result='failure',
            error_message=result.get('error', '未知错误')
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


# ========== 绑定管理 ==========

class WebhookView(APIView):
    """接收各渠道的Webhook回调"""
    permission_classes = [AllowAny]

    def post(self, request, channel_id):
        """处理渠道推送的消息事件"""
        channel = get_object_or_404(ChannelPlugin, id=channel_id, is_active=True, is_deleted=False)
        plugin = ChannelRegistry.get_plugin(channel.channel_type, channel.config)
        if not plugin:
            write_audit_log(
                'webhook_received', request,
                channel=channel,
                detail={'received': True, 'plugin_found': False},
                result='failure',
                error_message='不支持的渠道类型'
            )
            return Response({'error': '不支持的渠道类型'}, status=400)

        # 尝试验签（plugin可选择实现）
        verify_result = None
        if hasattr(plugin, 'verify_webhook_signature'):
            verify_result = plugin.verify_webhook_signature(request, channel)
            if not verify_result.get('valid', False):
                write_audit_log(
                    'webhook_received', request,
                    channel=channel,
                    detail={'received': True, 'signature_valid': False, 'ip': get_client_ip(request)},
                    result='failure',
                    error_message='验签失败: ' + str(verify_result.get('error', ''))
                )
                return Response({'error': '验签失败'}, status=401)

        # 调用 plugin 处理 webhook
        result = plugin.handle_webhook(request, channel)

        # 审计日志（无论成功失败均记录）
        notification_log_status = 'failed'
        if result is not None:
            notification_log_status = 'delivered'
            write_audit_log(
                'webhook_received', request,
                channel=channel,
                detail={
                    'title': result.get('title', ''),
                    'content': result.get('content', '')[:200],
                    'open_id': result.get('open_id', ''),
                    'ip': get_client_ip(request),
                },
                result='success'
            )
        else:
            write_audit_log(
                'webhook_received', request,
                channel=channel,
                detail={'received': True, 'handled': False},
                result='failure',
                error_message='该渠道不支持Webhook处理'
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
            bindings = ChannelBinding.objects.filter(is_active=True).select_related('user', 'channel').order_by('-bound_at')
        else:
            bindings = ChannelBinding.objects.filter(user=request.user, is_active=True).select_related('user', 'channel').order_by('-bound_at')

        data = [{
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
        } for b in bindings]

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
                return Response({'error': f'用户不存在: target_user_id={target_user_id}'}, status=status.HTTP_400_BAD_REQUEST)
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
            }
        )

        write_audit_log(
            'bind_create', request,
            channel=channel, binding=binding,
            detail={
                'channel_id': channel.id,
                'binding_id': binding.id,
                'platform_open_id': open_id,
                'bind_mode': 'manual',
            },
            result='success'
        )

        return Response({
            'id': binding.id,
            'channel_id': channel.id,
            'channel_type': channel.channel_type,
            'channel_name': channel.get_channel_type_display(),
            'platform_open_id': open_id,
            'status': 'active',
            'bound_at': binding.bound_at,
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    def delete(self, request):
        """解除绑定"""
        binding_id = request.data.get('binding_id')
        if not binding_id:
            return Response({'error': '缺少binding_id'}, status=status.HTTP_400_BAD_REQUEST)

        binding = get_object_or_404(ChannelBinding, id=binding_id, user=request.user)

        write_audit_log(
            'bind_delete', request,
            channel=binding.channel, binding=binding,
            detail={
                'channel_id': binding.channel_id,
                'binding_id': binding.id,
                'platform_open_id': binding.platform_open_id,
            },
            result='success'
        )

        binding.is_active = False
        binding.save()

        return Response({'message': '解除绑定成功'})


# ========== 渠道管理 ==========

class ChannelListView(APIView):
    """获取可用渠道列表"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        company_id = get_active_company_id(request)
        queryset = ChannelPlugin.objects.filter(is_deleted=False)
        
        if not (request.user.is_superuser or request.user.is_staff):
            if company_id is None:
                return Response([])
            queryset = queryset.filter(company_id=company_id)
        
        channels = queryset.filter(is_active=True).order_by('-created_at')
        
        data = []
        for ch in channels:
            plugin = ChannelRegistry.get_plugin(ch.channel_type, ch.config)
            status_info = plugin.get_status() if plugin else {}
            
            data.append({
                'id': ch.id,
                'channel_type': ch.channel_type,
                'channel_name': ch.get_channel_type_display(),
                'plugin_name': ch.plugin_name,
                'app_name': ch.app_name,
                'connection_mode': ch.connection_mode,
                'pairing_mode': ch.pairing_mode,
                'is_active': ch.is_active,
                'config': ch.config or {},
                'status': status_info,
                'config_schema': {
                    'required_fields': plugin.get_required_config_fields() if plugin else [],
                    'optional_fields': plugin.get_optional_config_fields() if plugin else [],
                } if plugin else {},
            })
        
        return Response(data)
    
    def post(self, request):
        """创建新渠道"""
        company_id = get_active_company_id(request)
        
        if not company_id and request.user.is_authenticated and (request.user.is_superuser or request.user.is_staff):
            # 超管/staff 用户：取其第一个 UCP 记录对应的公司
            from apps.core.models import UserCompanyPermission
            first_ucp = UserCompanyPermission.objects.filter(user=request.user).first()
            if first_ucp:
                company_id = first_ucp.company_id
        
        if not company_id:
            return Response({'error': '无法确定公司'}, status=status.HTTP_400_BAD_REQUEST)
        
        channel_type = request.data.get('channel_type')
        app_name = request.data.get('app_name', '')
        config = request.data.get('config', {})

        if not channel_type:
            return Response({'error': '缺少channel_type'}, status=status.HTTP_400_BAD_REQUEST)

        plugin_class = ChannelRegistry._plugins.get(channel_type)
        if not plugin_class:
            return Response({'error': f'不支持的渠道类型: {channel_type}'}, status=status.HTTP_400_BAD_REQUEST)

        # 保存前加密敏感凭证（CNAS/CMA 要求）
        from apps.channels.utils import encrypt_credentials
        encrypted_config = encrypt_credentials(config)

        try:
            channel = ChannelPlugin.objects.create(
                company_id=company_id,
                channel_type=channel_type,
                plugin_name=channel_type,
                app_name=app_name,
                config=encrypted_config,
                is_active=True,
            )
        except Exception as e:
            return Response({'error': f'创建渠道失败: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

        write_audit_log(
            'channel_create', request,
            channel=channel,
            detail={
                'channel_id': channel.id,
                'channel_type': channel_type,
                'app_name': app_name,
            },
            result='success'
        )

        return Response({
            'id': channel.id,
            'channel_type': channel.channel_type,
            'channel_name': channel.get_channel_type_display(),
            'app_name': channel.app_name,
            'is_active': channel.is_active,
        }, status=status.HTTP_201_CREATED)


class ChannelDetailView(APIView):
    """渠道详情（更新/删除）"""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        """获取渠道详情（含配置字段定义）"""
        channel = get_object_or_404(ChannelPlugin, id=pk, is_deleted=False)

        plugin = ChannelRegistry.get_plugin(channel.channel_type, channel.config)
        schema = {
            'required_fields': plugin.get_required_config_fields() if plugin else [],
            'optional_fields': plugin.get_optional_config_fields() if plugin else [],
            'current_config_keys': list(channel.config.keys()) if channel.config else [],
        }

        return Response({
            'id': channel.id,
            'channel_type': channel.channel_type,
            'channel_name': channel.get_channel_type_display(),
            'app_name': channel.app_name,
            'connection_mode': channel.connection_mode,
            'pairing_mode': channel.pairing_mode,
            'is_active': channel.is_active,
            'config': channel.config or {},
            'config_schema': schema,
        })

    def patch(self, request, pk):
        channel = get_object_or_404(ChannelPlugin, id=pk, is_deleted=False)

        # 记录变更前快照
        old_values = {}
        new_values = {}
        changed_fields = []

        if 'app_name' in request.data and request.data['app_name'] != channel.app_name:
            old_values['app_name'] = channel.app_name
            new_values['app_name'] = request.data['app_name']
            changed_fields.append('app_name')
            channel.app_name = request.data['app_name']

        if 'is_active' in request.data:
            new_is_active = bool(request.data['is_active'])
            if channel.is_active != new_is_active:
                old_values['is_active'] = channel.is_active
                new_values['is_active'] = new_is_active
                changed_fields.append('is_active')
                channel.is_active = new_is_active

        if 'config' in request.data:
            new_config = request.data['config']
            old_values['config'] = '[已加密]'  # 不记录实际凭证值
            new_values['config'] = '[已加密]'  # 不记录实际凭证值
            changed_fields.append('config')
            # 保存前加密敏感凭证（CNAS/CMA 要求）
            from apps.channels.utils import encrypt_credentials
            merged = {**channel.config, **new_config}
            channel.config = encrypt_credentials(merged)

        if 'connection_mode' in request.data and request.data['connection_mode'] != channel.connection_mode:
            old_values['connection_mode'] = channel.connection_mode
            new_values['connection_mode'] = request.data['connection_mode']
            changed_fields.append('connection_mode')
            channel.connection_mode = request.data['connection_mode']

        if 'pairing_mode' in request.data and request.data['pairing_mode'] != channel.pairing_mode:
            old_values['pairing_mode'] = channel.pairing_mode
            new_values['pairing_mode'] = request.data['pairing_mode']
            changed_fields.append('pairing_mode')
            channel.pairing_mode = request.data['pairing_mode']

        if changed_fields:
            channel.save()
            write_audit_log(
                'channel_update', request,
                channel=channel,
                detail={
                    'channel_id': channel.id,
                    'changed_fields': changed_fields,
                    'old_values': old_values,
                    'new_values': new_values,
                },
                result='success'
            )
        else:
            write_audit_log(
                'channel_update', request,
                channel=channel,
                detail={'channel_id': channel.id, 'changed_fields': [], 'note': '无实际变更'},
                result='success'
            )

        return Response({
            'id': channel.id,
            'channel_type': channel.channel_type,
            'channel_name': channel.get_channel_type_display(),
            'app_name': channel.app_name,
            'is_active': channel.is_active,
        })

    def delete(self, request, pk):
        """
        删除渠道 — 软删除（CNAS/CMA 要求：关键数据不得物理删除）
        将 is_active 设为 False，保留数据完整性
        """
        try:
            channel = get_object_or_404(ChannelPlugin, id=pk, is_deleted=False)

            write_audit_log(
                'channel_delete', request,
                channel=channel,
                detail={
                    'channel_id': channel.id,
                    'channel_type': channel.channel_type,
                    'app_name': channel.app_name,
                    'delete_type': 'soft',
                },
                result='success'
            )

            channel.is_active = False
            channel.is_deleted = True
            channel.deleted_at = timezone.now()
            channel.deleted_by = request.user if request.user.is_authenticated else None
            channel.save()

            return Response({'message': '渠道已停用（软删除）'}, status=status.HTTP_200_OK)
        except Exception as e:
            import traceback
            return Response(
                {'error': str(e), 'trace': traceback.format_exc()},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ========== 角色绑定 ==========

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
        
        result = [{
            'role_id': rb.get('role_id'),
            'role_name': roles.get(rb.get('role_id'), f"角色{rb.get('role_id')}"),
            'enabled': rb.get('enabled', True),
        } for rb in role_bindings]
        
        return Response(result)
    
    def post(self, request, channel_id):
        """添加/更新角色绑定"""
        channel = get_object_or_404(ChannelPlugin, id=channel_id, is_deleted=False)
        
        role_id = request.data.get('role_id')
        enabled = request.data.get('enabled', True)
        
        if not role_id:
            return Response({'error': '缺少role_id'}, status=status.HTTP_400_BAD_REQUEST)
        
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
        channel.save(update_fields=['config'])
        
        return Response({'message': '角色绑定已更新', 'role_bindings': role_bindings})
    
    def delete(self, request, channel_id):
        """删除角色绑定"""
        channel = get_object_or_404(ChannelPlugin, id=channel_id, is_deleted=False)
        
        role_id = request.data.get('role_id')
        if not role_id:
            return Response({'error': '缺少role_id'}, status=status.HTTP_400_BAD_REQUEST)
        
        role_bindings = channel.config.get('role_bindings', [])
        role_bindings = [rb for rb in role_bindings if str(rb.get('role_id')) != str(role_id)]
        channel.config['role_bindings'] = role_bindings
        channel.save(update_fields=['config'])
        
        return Response({'message': '角色绑定已删除'})


# ========== 验证和测试 ==========

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
                'channel_validate', request,
                channel=channel,
                detail={'channel_id': channel.id, 'error': str(e), 'trace': traceback.format_exc()},
                result='failure',
                error_message=f'插件初始化失败: {str(e)}'
            )
            return Response({'valid': False, 'message': f'插件初始化失败: {str(e)}'})

        if not plugin:
            write_audit_log(
                'channel_validate', request,
                channel=channel,
                detail={'channel_id': channel.id, 'plugin_found': False},
                result='failure',
                error_message='不支持的渠道类型'
            )
            return Response({'error': '不支持的渠道类型'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            is_valid, msg = plugin.validate_credentials()
        except Exception as e:
            import traceback
            write_audit_log(
                'channel_validate', request,
                channel=channel,
                detail={'channel_id': channel.id, 'error': str(e), 'trace': traceback.format_exc()},
                result='failure',
                error_message=f'验证异常: {str(e)}'
            )
            return Response({'valid': False, 'message': f'验证异常: {str(e)}'})

        write_audit_log(
            'channel_validate', request,
            channel=channel,
            detail={
                'channel_id': channel.id,
                'channel_type': channel.channel_type,
                'result': is_valid,
                'message': msg,
            },
            result='success' if is_valid else 'failure',
            error_message='' if is_valid else msg
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
                'test_message_sent', request,
                channel=channel,
                detail={'channel_id': channel.id, 'plugin_found': False},
                result='failure',
                error_message='不支持的渠道类型'
            )
            return Response({'error': f'不支持的渠道类型'}, status=status.HTTP_400_BAD_REQUEST)

        binding = ChannelBinding.objects.filter(
            user=request.user,
            channel=channel,
            is_active=True
        ).first()

        if not binding:
            write_audit_log(
                'test_message_sent', request,
                channel=channel,
                detail={'channel_id': channel.id, 'reason': 'user_not_bound'},
                result='failure',
                error_message='用户未绑定该渠道'
            )
            return Response({'error': '您尚未绑定该渠道，请先扫码绑定'}, status=status.HTTP_400_BAD_REQUEST)

        test_title = '测试消息'
        test_content = '这是一条来自企业信息化管理系统的测试通知，收到此消息表示绑定成功！'

        success, msg = plugin.send_message(
            binding.platform_open_id,
            test_title,
            test_content
        )

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
            'test_message_sent', request,
            channel=channel, binding=binding,
            detail={
                'channel_id': channel.id,
                'binding_id': binding.id,
                'platform_open_id': binding.platform_open_id,
                'success': success,
                'error': msg if not success else '',
            },
            result='success' if success else 'failure',
            error_message=msg if not success else ''
        )

        if success:
            return Response({'success': True, 'message': '测试消息发送成功'})
        return Response({'success': False, 'error': msg}, status=status.HTTP_400_BAD_REQUEST)


# ========== 通知发送 ==========

class SendNotificationView(APIView):
    """发送通知"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        user_ids = request.data.get('user_ids', [])
        channel_id = request.data.get('channel_id')
        title = request.data.get('title', '')
        content = request.data.get('content', '')
        notification_type = request.data.get('notification_type', 'system')
        
        if not all([channel_id, title, content]):
            return Response({'error': '缺少必要参数'}, status=status.HTTP_400_BAD_REQUEST)
        
        channel = get_object_or_404(ChannelPlugin, id=channel_id, is_active=True, is_deleted=False)
        
        plugin = ChannelRegistry.get_plugin(channel.channel_type, channel.config)
        if not plugin:
            return Response({'error': f'不支持的渠道类型'}, status=status.HTTP_400_BAD_REQUEST)
        
        User = get_user_model()
        company_id = get_active_company_id(request)
        
        if user_ids:
            users = User.objects.filter(id__in=user_ids, is_active=True)
        elif company_id:
            users = User.objects.filter(company_id=company_id, is_active=True)
        else:
            return Response({'error': '无法确定公司'}, status=status.HTTP_400_BAD_REQUEST)
        
        results = []
        for user in users:
            binding = ChannelBinding.objects.filter(
                user=user,
                channel=channel,
                is_active=True
            ).first()
            
            if not binding:
                results.append({
                    'user_id': user.id,
                    'username': user.username,
                    'status': 'failed',
                    'error': '用户未绑定该渠道'
                })
                continue
            
            success, msg = plugin.send_message(
                binding.platform_open_id,
                title,
                content
            )
            
            NotificationLog.objects.create(
                channel=channel,
                user=user,
                binding=binding,
                title=title,
                content=content,
                notification_type=notification_type,
                status='sent' if success else 'failed',
                error_message=msg if not success else '',
                sent_at=timezone.now() if success else None,
            )
            
            results.append({
                'user_id': user.id,
                'username': user.username,
                'status': 'sent' if success else 'failed',
                'message': msg
            })
        
        return Response({
            'total': len(results),
            'sent': len([r for r in results if r['status'] == 'sent']),
            'failed': len([r for r in results if r['status'] == 'failed']),
            'results': results
        })


# ========== 辅助函数 ==========

def get_client_ip(request):
    """从请求中提取真实IP（兼顾反向代理）"""
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def write_audit_log(action, request, channel=None, binding=None,
                    detail=None, result='success', error_message=''):
    """
    写入审计日志的标准化入口。
    CNAS/CMA 要求：所有敏感操作必须同步写入，不得异步或批量。
    """
    user = request.user if request.user.is_authenticated else None
    ChannelAuditLog.objects.create(
        user=user,
        user_ip=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:512],
        channel=channel,
        binding=binding,
        action=action,
        detail=detail or {},
        result=result,
        error_message=error_message,
    )


def send_notification(user, channel, title, content, notification_type='system'):
    """内部通知函数"""
    binding = ChannelBinding.objects.filter(user=user, channel=channel, is_active=True).first()
    if not binding:
        return False, '用户未绑定该渠道'

    plugin = ChannelRegistry.get_plugin(channel.channel_type, channel.config)
    if not plugin:
        return False, '不支持的渠道类型'

    success, msg = plugin.send_message(binding.platform_open_id, title, content)

    NotificationLog.objects.create(
        channel=channel,
        user=user,
        binding=binding,
        title=title,
        content=content,
        notification_type=notification_type,
        status='sent' if success else 'failed',
        error_message=msg if not success else '',
        sent_at=timezone.now() if success else None,
    )

    return success, msg


class NotificationLogView(APIView):
    """通知日志列表+导出"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company_id = get_active_company_id(request)
        if not company_id and not (request.user.is_superuser or request.user.is_staff):
            return Response({
                'error': '无权访问',
                'debug': {
                    'auth_company': str(getattr(request, 'auth_company', None)),
                    'company_id_attr': getattr(request, 'company_id', None),
                    'session_current_company': request.session.get('current_company_id'),
                    'is_super': request.user.is_superuser,
                    'is_staff': request.user.is_staff,
                    'user_id': request.user.id,
                }
            }, status=status.HTTP_403_FORBIDDEN)

        notification_type = request.GET.get('notification_type', '')
        channel_type = request.GET.get('channel_type', '')
        status_filter = request.GET.get('status', '')
        date_from = request.GET.get('date_from', '')
        date_to = request.GET.get('date_to', '')

        queryset = NotificationLog.objects.select_related('channel', 'user', 'binding').order_by('-created_at')

        if company_id:
            queryset = queryset.filter(channel__company_id=company_id)
        if notification_type:
            queryset = queryset.filter(notification_type=notification_type)
        if channel_type:
            queryset = queryset.filter(channel__channel_type=channel_type)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)

        # 统计
        total_qs = NotificationLog.objects.filter(channel__company_id=company_id) if company_id else NotificationLog.objects.all()
        stats = {
            'sent': total_qs.filter(status='sent').count(),
            'failed': total_qs.filter(status='failed').count(),
            'pending': total_qs.filter(status='pending').count(),
        }

        # 分页
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 50))
        start = (page - 1) * page_size
        end = start + page_size

        total = queryset.count()
        logs = queryset[start:end]

        data = []
        for log in logs:
            data.append({
                'id': log.id,
                'channel_type': log.channel.channel_type if log.channel else None,
                'channel_name': log.channel.get_channel_type_display() if log.channel else None,
                'username': log.user.username if log.user else None,
                'title': log.title,
                'notification_type': log.notification_type,
                'status': log.status,
                'error_message': log.error_message or '',
                'sent_at': log.sent_at.isoformat() if log.sent_at else None,
                'created_at': log.created_at.isoformat() if log.created_at else None,
            })

        return Response({
            'total': total,
            'page': page,
            'page_size': page_size,
            'logs': data,
            'stats': stats,
        })
