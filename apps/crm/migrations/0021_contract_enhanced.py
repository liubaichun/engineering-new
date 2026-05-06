"""
合同管理增强：付款计划 + 变更记录
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0020_alter_client_options'),
    ]

    operations = [
        # ── 付款计划 ──────────────────────────────────────────
        migrations.CreateModel(
            name='PaymentPlan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('plan_date', models.DateField(verbose_name='计划日期')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=15, verbose_name='计划金额')),
                ('paid_date', models.DateField(blank=True, null=True, verbose_name='实际付款日期')),
                ('paid_amount', models.DecimalField(decimal_places=2, max_digits=15, default=0, verbose_name='实付金额')),
                ('status', models.CharField(
                    choices=[('pending', '待付'), ('partial', '部分付款'), ('paid', '已付'), ('overdue', '逾期')],
                    default='pending', max_length=20, verbose_name='付款状态')),
                ('payment_method', models.CharField(blank=True, max_length=50, null=True, verbose_name='付款方式')),
                ('payment_account', models.CharField(blank=True, max_length=200, null=True, verbose_name='付款账户')),
                ('remark', models.TextField(blank=True, null=True, verbose_name='备注')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('contract', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payment_plans', to='crm.contract', verbose_name='关联合同')),
            ],
            options={'verbose_name': '付款计划', 'verbose_name_plural': '付款计划', 'ordering': ['plan_date']},
        ),

        # ── 合同变更记录 ──────────────────────────────────────
        migrations.CreateModel(
            name='ContractChangeLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('change_type', models.CharField(
                    choices=[('amount', '金额变更'), ('term', '期限变更'), ('party', '对方主体变更'), ('content', '合同内容变更'), ('terminate', '终止')],
                    max_length=20, verbose_name='变更类型')),
                ('old_value', models.TextField(blank=True, null=True, verbose_name='变更前')),
                ('new_value', models.TextField(blank=True, null=True, verbose_name='变更后')),
                ('reason', models.TextField(blank=True, null=True, verbose_name='变更原因')),
                ('change_date', models.DateField(auto_now_add=True, verbose_name='变更日期')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('contract', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='change_logs', to='crm.contract', verbose_name='关联合同')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='contract_changes', to='core.user', verbose_name='变更人')),
            ],
            options={'verbose_name': '合同变更记录', 'verbose_name_plural': '合同变更记录', 'ordering': ['-change_date']},
        ),

        # ── 给 Contract 加工作流字段 ───────────────────────────
        migrations.AddField(
            model_name='contract',
            name='approval_flow',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='contract_flows', to='approvals.approvalflow', verbose_name='审批流程'),
        ),
        migrations.AddField(
            model_name='contract',
            name='signed_date',
            field=models.DateField(blank=True, null=True, verbose_name='合同生效日期'),
        ),
        migrations.AddField(
            model_name='contract',
            name='payment_status',
            field=models.CharField(
                choices=[('unpaid', '未付款'), ('partial', '部分付款'), ('paid', '已付清')],
                default='unpaid', max_length=20, verbose_name='付款进度'),
        ),
        migrations.AddField(
            model_name='contract',
            name='total_paid',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=15, verbose_name='已付款总额'),
        ),
    ]
