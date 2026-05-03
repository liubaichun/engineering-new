# Generated manually — 添加邮件服务/域名/HTTPS外部依赖配置项
from django.db import migrations


def migrate_existing_settings(apps, schema_editor):
    """只插入新配置项，已存在则跳过"""
    schema_editor.execute("""
        INSERT INTO core_system_setting (key, value, description, updated_at) VALUES
            ('email_smtp_host', '', 'SMTP主机，如 smtp.qq.com', NOW()),
            ('email_smtp_port', '587', 'SMTP端口，默认587', NOW()),
            ('email_smtp_user', '', 'SMTP用户名', NOW()),
            ('email_smtp_password', '', 'SMTP密码（请勿泄露）', NOW()),
            ('email_use_tls', 'true', '是否启用TLS加密', NOW()),
            ('email_from', '', '系统发件邮箱地址', NOW()),
            ('site_domain', '', '访问域名，不含https://', NOW()),
            ('site_https_enabled', 'false', '是否启用HTTPS', NOW()),
            ('ssl_cert_path', '', 'SSL证书路径，例: /etc/letsencrypt/live/域名/fullchain.pem', NOW()),
            ('ssl_key_path', '', 'SSL私钥路径，例: /etc/letsencrypt/live/域名/privkey.pem', NOW()),
            ('ssl_auto_renew', 'true', '是否启用certbot自动续期', NOW())
        ON CONFLICT (key) DO NOTHING
    """)


def rollback(apps, schema_editor):
    SystemSetting = apps.get_model('core', 'SystemSetting')
    keys = [
        'email_smtp_host', 'email_smtp_port', 'email_smtp_user', 'email_smtp_password',
        'email_use_tls', 'email_from',
        'site_domain', 'site_https_enabled', 'ssl_cert_path', 'ssl_key_path', 'ssl_auto_renew',
    ]
    SystemSetting.objects.filter(key__in=keys).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0011_add_operation_audit_log'),
    ]
    operations = [
        migrations.RunPython(migrate_existing_settings, rollback),
    ]
