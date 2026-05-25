from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0020_cleanup_permission_schema'),
    ]

    operations = [
        migrations.AddField(
            model_name='moduleaction',
            name='action_group',
            field=models.CharField(
                choices=[('basic', '基础'), ('data', '数据'), ('flow', '流程'), ('operation', '操作')],
                default='basic',
                max_length=20,
                verbose_name='动作分组'
            ),
        ),
    ]