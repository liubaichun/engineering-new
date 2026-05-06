"""
CRM模块多租户隔离：公司字段
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0001_initial'),
        ('crm', '0005_clientsource_contract_attachment_client_source'),
    ]

    operations = [
        # Client 新增 company 字段
        migrations.AddField(
            model_name='client',
            name='company',
            field=models.ForeignKey(
                to='finance.Company',
                on_delete=django.db.models.deletion.CASCADE,
                related_name='clients',
                null=True, blank=True,
                verbose_name='所属公司'
            ),
        ),
        # Supplier 新增 company 字段
        migrations.AddField(
            model_name='supplier',
            name='company',
            field=models.ForeignKey(
                to='finance.Company',
                on_delete=django.db.models.deletion.CASCADE,
                related_name='suppliers',
                null=True, blank=True,
                verbose_name='所属公司'
            ),
        ),
        # Contract 新增 company 字段
        migrations.AddField(
            model_name='contract',
            name='company',
            field=models.ForeignKey(
                to='finance.Company',
                on_delete=django.db.models.deletion.CASCADE,
                related_name='contracts',
                null=True, blank=True,
                verbose_name='所属公司'
            ),
        ),
        # ClientSource 新增 company 字段
        migrations.AddField(
            model_name='clientsource',
            name='company',
            field=models.ForeignKey(
                to='finance.Company',
                on_delete=django.db.models.deletion.CASCADE,
                related_name='client_sources',
                null=True, blank=True,
                verbose_name='所属公司'
            ),
        ),
    ]
