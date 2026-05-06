# 001_add_project_approval.py
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0001_initial'),
        ('approvals', '0009_remove_approvalflow_company'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='approval_flow',
            field=models.ForeignKey(
                null=True, blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='projects',
                to='approvals.approvalflow',
                verbose_name='审批流'
            ),
        ),
        migrations.AddField(
            model_name='project',
            name='approval_status',
            field=models.CharField(
                '审批状态', max_length=20, blank=True, default='',
                choices=[
                    ('draft', '草稿'),
                    ('pending', '待审批'),
                    ('approved', '已批准'),
                    ('rejected', '已拒绝'),
                    ('cancelled', '已取消'),
                ]
            ),
        ),
        migrations.AddIndex(
            model_name='project',
            index=models.Index(fields=['approval_status'], name='tasks_proj_appr_idx'),
        ),
    ]
