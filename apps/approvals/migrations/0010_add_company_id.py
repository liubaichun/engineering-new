# Generated migration for company_id on ApprovalFlow, ApprovalNode, ApprovalTemplate
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('approvals', '0009_remove_approvalflow_company'),
    ]

    operations = [
        migrations.AddField(
            model_name='approvalflow',
            name='company_id',
            field=models.PositiveIntegerField(
                blank=True, db_index=True, null=True,
                help_text='所属公司ID，用于多租户隔离', verbose_name='所属公司'
            ),
        ),
        migrations.AddField(
            model_name='approvalnode',
            name='company_id',
            field=models.PositiveIntegerField(
                blank=True, db_index=True, null=True,
                help_text='所属公司ID，用于多租户隔离', verbose_name='所属公司'
            ),
        ),
        migrations.AddField(
            model_name='approvaltemplate',
            name='company_id',
            field=models.PositiveIntegerField(
                blank=True, db_index=True, null=True,
                help_text='所属公司ID，用于多租户隔离', verbose_name='所属公司'
            ),
        ),
    ]
