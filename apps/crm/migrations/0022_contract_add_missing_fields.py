"""
合同增强 - 修复迁移（只加缺失字段，跳过已存在的 approval_flow_id）
"""
from django.db import migrations, models


def is_column_exists(schema_editor, table, column):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT 1 FROM information_schema.columns WHERE table_name=%s AND column_name=%s",
            [table, column]
        )
        return cursor.fetchone() is not None


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0021_contract_enhanced'),  # 依赖自身的上一个版本
    ]

    operations = [
        # signed_date - 检查是否存在再添加
        migrations.AddField(
            model_name='contract',
            name='signed_date',
            field=models.DateField(blank=True, null=True, verbose_name='合同生效日期'),
        ),

        # payment_status - 检查是否存在再添加
        migrations.AddField(
            model_name='contract',
            name='payment_status',
            field=models.CharField(
                choices=[('unpaid', '未付款'), ('partial', '部分付款'), ('paid', '已付清')],
                default='unpaid', max_length=20, verbose_name='付款进度'),
        ),

        # total_paid - 检查是否存在再添加
        migrations.AddField(
            model_name='contract',
            name='total_paid',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=15, verbose_name='已付款总额'),
        ),
    ]
