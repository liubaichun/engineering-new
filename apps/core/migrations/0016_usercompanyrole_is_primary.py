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
        # 从 UserCompanyPermission.is_primary 迁移已有数据
        # 对于每个用户，取其 UserCompanyPermission 中 is_primary=True 的记录
        # 复制到 UserCompanyRole.is_primary
        migrations.RunSQL(
            sql="""
            UPDATE core_user_company_role ucr
            SET is_primary = TRUE
            FROM core_user_company_permission ucp
            WHERE ucp.user_id = ucr.user_id
              AND ucp.company_id = ucr.company_id
              AND ucp.is_primary = TRUE;
            """,
            reverse_sql="""
            UPDATE core_user_company_role SET is_primary = FALSE;
            """
        ),
    ]
