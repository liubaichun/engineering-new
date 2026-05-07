from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('finance', '0014_company_bank_account_company_bank_name_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='BankAccount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('bank_code', models.CharField(choices=[('ICBC', '工商银行'), ('CMBC', '招商银行'), ('CCB', '建设银行'), ('BOC', '中国银行'), ('ABC', '农业银行'), ('COMM', '交通银行'), ('PA', '平安银行'), ('OTHER', '其他')], default='OTHER', max_length=20, verbose_name='银行代码')),
                ('bank_name', models.CharField(blank=True, default='', max_length=100, verbose_name='银行名称')),
                ('account_no', models.CharField(max_length=50, verbose_name='账号')),
                ('account_name', models.CharField(blank=True, default='', max_length=200, verbose_name='账户名')),
                ('is_active', models.BooleanField(default=True, verbose_name='启用')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bank_accounts', to='finance.company', verbose_name='所属公司')),
            ],
            options={
                'verbose_name': '银行账户',
                'verbose_name_plural': '银行账户',
                'db_table': 'finance_bank_account',
                'unique_together': {('company', 'account_no')},
            },
        ),
        migrations.CreateModel(
            name='BankStatement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('bank_serial', models.CharField(blank=True, default='', max_length=100, verbose_name='银行流水号')),
                ('transaction_date', models.DateField(verbose_name='交易日期')),
                ('transaction_time', models.TimeField(blank=True, null=True, verbose_name='交易时间')),
                ('direction', models.CharField(choices=[('income', '收入'), ('expense', '支出')], max_length=10, verbose_name='收支方向')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=14, verbose_name='交易金额')),
                ('balance', models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True, verbose_name='余额')),
                ('counterparty_name', models.CharField(blank=True, default='', max_length=200, verbose_name='对方名称')),
                ('counterparty_account', models.CharField(blank=True, default='', max_length=50, verbose_name='对方账号')),
                ('counterparty_bank', models.CharField(blank=True, default='', max_length=200, verbose_name='对方开户行')),
                ('summary', models.CharField(blank=True, default='', max_length=500, verbose_name='交易摘要')),
                ('usage', models.TextField(blank=True, default='', verbose_name='用途/附言')),
                ('reconcile_status', models.CharField(choices=[('matched', '已核销'), ('unmatched', '未核销'), ('partial', '部分核销')], default='unmatched', max_length=20, verbose_name='核销状态')),
                ('reconcile_time', models.DateTimeField(blank=True, null=True, verbose_name='核销时间')),
                ('source_bank', models.CharField(blank=True, default='', max_length=20, verbose_name='来源银行')),
                ('import_batch', models.CharField(blank=True, default='', max_length=64, verbose_name='导入批次号')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('bank_account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='statements', to='finance.bankaccount', verbose_name='银行账户')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bank_statements', to='finance.company', verbose_name='公司')),
                ('matched_income', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='matched_statements', to='finance.income', verbose_name='核销收入')),
                ('matched_expense', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='matched_statements', to='finance.expense', verbose_name='核销支出')),
            ],
            options={
                'verbose_name': '银行流水',
                'verbose_name_plural': '银行流水台账',
                'db_table': 'finance_bank_statement',
                'ordering': ['-transaction_date', '-transaction_time'],
            },
        ),
        migrations.AddIndex(
            model_name='bankstatement',
            index=models.Index(fields=['company', 'transaction_date'], name='finance_ban_company_id_d5e36b_idx'),
        ),
        migrations.AddIndex(
            model_name='bankstatement',
            index=models.Index(fields=['bank_account', 'transaction_date'], name='finance_ban_bank_acc_4a3c91_idx'),
        ),
        migrations.AddIndex(
            model_name='bankstatement',
            index=models.Index(fields=['bank_serial'], name='finance_ban_bank_ser_7d8e2a_idx'),
        ),
        migrations.AddIndex(
            model_name='bankstatement',
            index=models.Index(fields=['import_batch'], name='finance_ban_import__0c9f6b_idx'),
        ),
    ]
