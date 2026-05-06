"""
合同增强 - 修复迁移（纯 SQL，只加缺失列，跳过已存在）
用于修复 0021 部分失败（approval_flow_id 已存在但后续字段未加）的问题
"""
from django.db import migrations, models


def add_column_if_not_exists(c, table, column, field_def):
    """安全的列添加：先检查再添加"""
    c.execute(
        "SELECT 1 FROM information_schema.columns WHERE table_name=%s AND column_name=%s",
        [table, column]
    )
    if not c.fetchone():
        c.execute(f'ALTER TABLE {table} ADD COLUMN {column} {field_def};')
        print(f"  ✅ Added {table}.{column}")


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0021_contract_enhanced'),
    ]

    operations = [
        migrations.RunPython(
            lambda apps, schema_editor: _fix_contract_columns(apps, schema_editor),
            reverse_code=migrations.RunPython.noop,
        ),
    ]


def _fix_contract_columns(apps, schema_editor):
    with schema_editor.connection.cursor() as c:
        print("检查 crm_contract 表缺失列...")
        add_column_if_not_exists(c, 'crm_contract', 'signed_date',
            'DATE USING signed_date::date')
        add_column_if_not_exists(c, 'crm_contract', 'payment_status',
            "VARCHAR(20) DEFAULT 'unpaid'")
        add_column_if_not_exists(c, 'crm_contract', 'total_paid',
            'DECIMAL(15,2) DEFAULT 0')
        print("  ✅ 所有缺失列已补齐")
