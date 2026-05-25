# Generated migration — CompanyRolePermission model class
# + CompanyRole.permissions M2M through table
# The core_company_role_permission table already exists from 0018
# This migration adds the model class to Django's registry

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0018_add_company_role_and_source'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='rolepermission',
            name='granted_at',
            field=models.DateTimeField(
                auto_now_add=True,
                null=True,  # 已有数据为 NULL，迁移后由 DB 触发器或应用层填充
                verbose_name='授权时间',
            ),
        ),
    ]