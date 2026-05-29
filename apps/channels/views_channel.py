import logging
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated

logger = logging.getLogger(__name__)
User = get_user_model()

from .models import ChannelPlugin
from .base import ChannelRegistry
from apps.core.services import get_active_company_id


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

            data.append(
                {
                    'id': ch.id,
                    'channel_type': ch.channel_type,
                    'channel_name': ch.get_channel_type_display(),
                    'usage': ch.usage,
                    'usage_display': ch.get_usage_display(),
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
                    }
                    if plugin
                    else {},
                }
            )

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
        usage = request.data.get('usage', 'personal')
        app_name = request.data.get('app_name', '')
        config = request.data.get('config', {})

        if not channel_type:
            return Response({'error': '缺少channel_type'}, status=status.HTTP_400_BAD_REQUEST)

        if usage not in ('broadcast', 'personal'):
            return Response({'error': '用途必须为 broadcast 或 personal'}, status=status.HTTP_400_BAD_REQUEST)

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
                usage=usage,
                plugin_name=channel_type,
                app_name=app_name,
                config=encrypted_config,
                is_active=True,
            )
        except Exception as e:
            return Response({'error': f'创建渠道失败: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

        write_audit_log(
            'channel_create',
            request,
            channel=channel,
            detail={
                'channel_id': channel.id,
                'channel_type': channel_type,
                'app_name': app_name,
            },
            result='success',
        )

        return Response(
            {
                'id': channel.id,
                'channel_type': channel.channel_type,
                'channel_name': channel.get_channel_type_display(),
                'app_name': channel.app_name,
                'is_active': channel.is_active,
            },
            status=status.HTTP_201_CREATED,
        )


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

        return Response(
            {
                'id': channel.id,
                'channel_type': channel.channel_type,
                'channel_name': channel.get_channel_type_display(),
                'usage': channel.usage,
                'usage_display': channel.get_usage_display(),
                'app_name': channel.app_name,
                'connection_mode': channel.connection_mode,
                'pairing_mode': channel.pairing_mode,
                'is_active': channel.is_active,
                'config': channel.config or {},
                'config_schema': schema,
            }
        )

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

        if 'usage' in request.data:
            new_usage = request.data['usage']
            if new_usage not in ('broadcast', 'personal'):
                return Response({'error': '用途必须为 broadcast 或 personal'}, status=status.HTTP_400_BAD_REQUEST)
            if channel.usage != new_usage:
                old_values['usage'] = channel.usage
                new_values['usage'] = new_usage
                changed_fields.append('usage')
                channel.usage = new_usage

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
            try:
                channel.save()
            except Exception as e:
                return Response({'error': f'更新渠道失败：{str(e)}'}, status=500)
            write_audit_log(
                'channel_update',
                request,
                channel=channel,
                detail={
                    'channel_id': channel.id,
                    'changed_fields': changed_fields,
                    'old_values': old_values,
                    'new_values': new_values,
                },
                result='success',
            )
        else:
            write_audit_log(
                'channel_update',
                request,
                channel=channel,
                detail={'channel_id': channel.id, 'changed_fields': [], 'note': '无实际变更'},
                result='success',
            )

        return Response(
            {
                'id': channel.id,
                'channel_type': channel.channel_type,
                'channel_name': channel.get_channel_type_display(),
                'app_name': channel.app_name,
                'is_active': channel.is_active,
            }
        )

    def delete(self, request, pk):
        """
        删除渠道 — 软删除（CNAS/CMA 要求：关键数据不得物理删除）
        将 is_active 设为 False，保留数据完整性
        """
        try:
            channel = get_object_or_404(ChannelPlugin, id=pk, is_deleted=False)

            write_audit_log(
                'channel_delete',
                request,
                channel=channel,
                detail={
                    'channel_id': channel.id,
                    'channel_type': channel.channel_type,
                    'app_name': channel.app_name,
                    'delete_type': 'soft',
                },
                result='success',
            )

            channel.is_active = False
            channel.is_deleted = True
            channel.deleted_at = timezone.now()
            channel.deleted_by = request.user if request.user.is_authenticated else None
            try:
                channel.save()
            except Exception as e:
                return Response({'error': f'停用渠道失败：{str(e)}'}, status=500)

            return Response({'message': '渠道已停用（软删除）'}, status=status.HTTP_200_OK)
        except Exception as e:
            import traceback

            return Response(
                {'error': str(e), 'trace': traceback.format_exc()}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
