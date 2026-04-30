from rest_framework import serializers
from .models import NotificationChannel


class NotificationChannelSerializer(serializers.ModelSerializer):
    channel_type_display = serializers.CharField(
        source='get_channel_type_display', read_only=True
    )
    status_display = serializers.CharField(
        source='get_status_display', read_only=True
    )

    class Meta:
        model = NotificationChannel
        fields = [
            'id', 'name', 'channel_type', 'channel_type_display',
            'webhook_url', 'secret', 'status', 'status_display',
            'remark', 'is_deleted', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'is_deleted', 'created_at', 'updated_at']

    def create(self, validated_data):
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
