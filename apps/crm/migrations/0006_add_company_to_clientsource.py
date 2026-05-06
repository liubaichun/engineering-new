"""
ClientSource多租户：公司字段（Client/Supplier/Contract已在DB有company_id，仅ClientSource缺失）
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0001_initial'),
        ('crm', '0005_clientsource_contract_attachment_client_source'),
    ]

    operations = [
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
