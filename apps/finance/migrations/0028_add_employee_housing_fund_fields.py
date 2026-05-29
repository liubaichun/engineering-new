# Generated manually — add housing fund fields to Employee model
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0027_add_social_record'),
    ]

    operations = [
        migrations.AddField(
            model_name='employee',
            name='housing_fund_company',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name='公司公积金'),
        ),
        migrations.AddField(
            model_name='employee',
            name='housing_fund_employee',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name='个人公积金'),
        ),
    ]
