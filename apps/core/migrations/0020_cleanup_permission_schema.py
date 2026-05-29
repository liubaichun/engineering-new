"""
0020_cleanup_permission_schema.py
清理 core_permission 表中不再使用的 menu_code 列和错误约束。
已在本地开发环境（43服务器）执行，迁移用于记录变更。
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0019_add_company_role_permission_model'),
    ]

    operations = [
        # 删除 Django 模型中已移除的 menu_code 列（数据库层残留）
        migrations.RunSQL(
            'ALTER TABLE core_permission DROP COLUMN IF EXISTS menu_code',
            reverse_sql=migrations.RunSQL.noop,
        ),
        # 删除错误的多列唯一约束（导致同 resource+action 不同 category 重复键冲突）
        migrations.RunSQL(
            'ALTER TABLE core_permission DROP CONSTRAINT IF EXISTS core_permission_resource_action_302cdbc0_uniq',
            reverse_sql=migrations.RunSQL.noop,
        ),
        # description 列设为 nullable（Django 模型 blank=True）
        migrations.RunSQL(
            'ALTER TABLE core_permission ALTER COLUMN description DROP NOT NULL',
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
