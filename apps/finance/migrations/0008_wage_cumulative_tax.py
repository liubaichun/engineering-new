# Generated manually for cumulative tax withholding (累计预扣法)
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0015_bank_statement'),
    ]

    operations = [
        migrations.AddField(
            model_name='wagerecord',
            name='cumulative_gross',
            field=models.DecimalField(
                verbose_name='累计应发工资',
                max_digits=14, decimal_places=2, default=0, editable=False
            ),
        ),
        migrations.AddField(
            model_name='wagerecord',
            name='cumulative_social_insurance',
            field=models.DecimalField(
                verbose_name='累计社保扣款',
                max_digits=14, decimal_places=2, default=0, editable=False
            ),
        ),
        migrations.AddField(
            model_name='wagerecord',
            name='cumulative_housing_fund',
            field=models.DecimalField(
                verbose_name='累计公积金扣款',
                max_digits=14, decimal_places=2, default=0, editable=False
            ),
        ),
        migrations.AddField(
            model_name='wagerecord',
            name='cumulative_taxable_income',
            field=models.DecimalField(
                verbose_name='累计应纳税所得额',
                max_digits=14, decimal_places=2, default=0, editable=False
            ),
        ),
        migrations.AddField(
            model_name='wagerecord',
            name='prior_cumulative_tax',
            field=models.DecimalField(
                verbose_name='上月累计已扣税额',
                max_digits=14, decimal_places=2, default=0
            ),
        ),
        migrations.AddField(
            model_name='wagerecord',
            name='special_deduction',
            field=models.DecimalField(
                verbose_name='专项附加扣除',
                max_digits=12, decimal_places=2, default=0
            ),
        ),
    ]
