from rest_framework import serializers
from .models import UserNotificationPreference


class UserNotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserNotificationPreference
        fields = ['event_type', 'is_enabled', 'allowed_channels']
