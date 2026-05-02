from rest_framework import serializers
from .models import NotificationChannel, NotifyBinding


class NotificationChannelSerializer(serializers.ModelSerializer):
    """通知渠道序列化器"""
    channel_type_display = serializers.CharField(
        source='get_channel_type_display', read_only=True
    )
    status_display = serializers.CharField(
        source='get_status_display', read_only=True
    )
    company_name = serializers.CharField(
        source='company.name', read_only=True, default=None
    )

    class Meta:
        model = NotificationChannel
        fields = [
            'id', 'name', 'channel_type', 'channel_type_display',
            'company', 'company_name',
            'webhook_url', 'secret', 'status', 'status_display',
            'remark', 'is_deleted', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'is_deleted', 'created_at', 'updated_at']

    def create(self, validated_data):
        # 多租户：自动填入当前公司
        request = self.context.get('request')
        if request and hasattr(request, 'company_id') and request.company_id:
            validated_data.setdefault('company_id', request.company_id)
        # 软删除恢复逻辑
        name = validated_data.get('name', '').strip()
        channel_type = validated_data.get('channel_type', '')
        existing = NotificationChannel.all_objects.filter(
            name=name, channel_type=channel_type, is_deleted=True
        ).first()
        if existing:
            existing.is_deleted = False
            for k, v in validated_data.items():
                setattr(existing, k, v)
            existing.save()
            return existing
        return super().create(validated_data)


class NotifyBindingSerializer(serializers.ModelSerializer):
    """用户通知绑定序列化器"""
    platform_display = serializers.CharField(
        source='get_platform_display', read_only=True
    )
    user_username = serializers.CharField(
        source='user.username', read_only=True
    )
    channel_name = serializers.CharField(
        source='channel.name', read_only=True
    )
    channel_type = serializers.CharField(
        source='channel.channel_type', read_only=True
    )

    class Meta:
        model = NotifyBinding
        fields = [
            'id', 'user', 'user_username',
            'channel', 'channel_name', 'channel_type',
            'platform', 'platform_display',
            'platform_open_id', 'is_active', 'receive_all',
            'bound_at', 'updated_at',
        ]
        read_only_fields = ['id', 'bound_at', 'updated_at']

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)
