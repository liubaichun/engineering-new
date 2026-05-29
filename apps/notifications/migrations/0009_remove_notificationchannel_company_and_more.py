# Manually crafted — tables already dropped manually, only UserNotificationPreference is real
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0008_user_notification_preference'),
    ]

    operations = [
        # Real DB changes: UserNotificationPreference still exists
        migrations.AlterModelOptions(
            name='usernotificationpreference',
            options={'verbose_name': 'User Notification Preference', 'verbose_name_plural': 'User Notification Preference'},
        ),
        migrations.AlterField(
            model_name='usernotificationpreference',
            name='allowed_channels',
            field=models.JSONField(blank=True, default=list, verbose_name='Allowed channels'),
        ),
        migrations.AlterField(
            model_name='usernotificationpreference',
            name='is_enabled',
            field=models.BooleanField(default=True, verbose_name='Enable notification'),
        ),

        # State-only cleanup: these model tables were already dropped manually
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(
                    model_name='notificationchannel',
                    name='company',
                ),
                migrations.RemoveField(
                    model_name='notifybinding',
                    name='channel',
                ),
                migrations.RemoveField(
                    model_name='notificationlog',
                    name='binding',
                ),
                migrations.DeleteModel(name='NotificationRouter'),
                migrations.AlterUniqueTogether(
                    name='notifyapp',
                    unique_together=None,
                ),
                migrations.RemoveField(
                    model_name='notifyapp',
                    name='company',
                ),
                migrations.RemoveField(
                    model_name='notifybinding',
                    name='notify_app',
                ),
                migrations.AlterUniqueTogether(
                    name='notifybinding',
                    unique_together=None,
                ),
                migrations.RemoveField(
                    model_name='notifybinding',
                    name='user',
                ),
                migrations.DeleteModel(name='NotificationChannel'),
                migrations.DeleteModel(name='NotificationLog'),
                migrations.DeleteModel(name='NotifyApp'),
                migrations.DeleteModel(name='NotifyBinding'),
            ],
            database_operations=[],
        ),
    ]
