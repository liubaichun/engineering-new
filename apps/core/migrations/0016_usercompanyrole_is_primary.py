from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0015_add_password_changed_field'),
    ]

    operations = [
        migrations.AddField(
            model_name='UserCompanyRole',
            name='is_primary',
            field=models.BooleanField(default=False, verbose_name='主体企业'),
        ),
        # 旧表 core_user_company_permission 可能不存在（全新安装）
        # 直接设置 is_primary=False，数据迁移由后续脚本处理
        migrations.RunSQL(
            sql="""
            UPDATE core_user_company_role SET is_primary = FALSE;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
