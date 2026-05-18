from django.db import models
from django.conf import settings


class UserNotificationPreference(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_preferences',
    )
    event_type = models.CharField(max_length=50, db_index=True)
    is_enabled = models.BooleanField(default=True, verbose_name='Enable notification')
    allowed_channels = models.JSONField(default=list, blank=True, verbose_name='Allowed channels')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_notification_preference'
        unique_together = [['user', 'event_type']]
        verbose_name = 'User Notification Preference'
        verbose_name_plural = verbose_name

    def __str__(self):
        state = 'enabled' if self.is_enabled else 'disabled'
        return f'{self.user.username} / {self.event_type} / {state}'
