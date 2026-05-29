# Generated manually — alter Invoice Meta options, add verbose_name to SocialRecord timestamps
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0028_add_employee_housing_fund_fields'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='invoice',
            options={'ordering': ['-issue_date'], 'verbose_name': '发票', 'verbose_name_plural': '发票管理'},
        ),
        migrations.AlterField(
            model_name='socialrecord',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, verbose_name='创建时间'),
        ),
        migrations.AlterField(
            model_name='socialrecord',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, verbose_name='更新时间'),
        ),
    ]
