# Generated manually — aligns model state with actual DB structure for notify_binding
# notify_binding table was created by 0001_add_notify_app_binding (CreateModel)
# This migration adds DB columns that were NOT in the original 0001 model:
#   channel_id FK, platform, receive_all
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='notifybinding',
            name='channel',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='bindings',
                to='notifications.notificationchannel',
                verbose_name='推送渠道'
            ),
        ),
        migrations.AddField(
            model_name='notifybinding',
            name='platform',
            field=models.CharField(
                choices=[('feishu', '飞书'), ('wecom', '企业微信'), ('dingtalk', '钉钉'), ('email', '邮件')],
                default='feishu', max_length=20, verbose_name='平台'
            ),
        ),
        migrations.AddField(
            model_name='notifybinding',
            name='receive_all',
            field=models.BooleanField(default=True, verbose_name='接收全部通知'),
        ),
    ]
