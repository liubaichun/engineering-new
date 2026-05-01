# Generated manually — adds NotificationChannel broadcast webhook table
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0001_add_notify_app_binding'),
    ]

    operations = [
        migrations.CreateModel(
            name='NotificationChannel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='渠道名称')),
                ('channel_type', models.CharField(
                    choices=[('feishu', '飞书'), ('wecom', '企业微信'),
                             ('dingtalk', '钉钉'), ('email', '邮件'),
                             ('webhook', '自定义Webhook')],
                    max_length=20, verbose_name='渠道类型')),
                ('webhook_url', models.URLField(max_length=500, verbose_name='Webhook地址')),
                ('secret', models.CharField(blank=True, default='', max_length=200, verbose_name='Secret密钥')),
                ('status', models.CharField(
                    choices=[('active', '启用'), ('inactive', '停用')],
                    default='active', max_length=20, verbose_name='状态')),
                ('remark', models.TextField(blank=True, default='', verbose_name='备注')),
                ('is_deleted', models.BooleanField(default=False, verbose_name='已删除')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'db_table': 'notifications_channel',
                'ordering': ['-created_at'],
                'verbose_name': '通知渠道',
                'verbose_name_plural': '通知渠道',
            },
        ),
    ]
