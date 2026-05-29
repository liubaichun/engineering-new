"""Update income_category choices to include new options

Migration 0033 creates the income_category field with the original choices.
This migration updates it to include additional options added in the model:
- other_income (其他收益)
- investment_income (投资收益)

On production servers, the column already exists from manual ALTER TABLE.
Migration 0033 was already applied as AlterField (which worked because the
column existed). This migration ensures the choices are up to date.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0041_alter_account_company_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='income',
            name='income_category',
            field=models.CharField(
                blank=True,
                choices=[
                    ('main_business', '主营业务收入'),
                    ('other_business', '其他业务收入'),
                    ('non_operating', '营业外收入'),
                    ('other_income', '其他收益'),
                    ('investment_income', '投资收益'),
                    ('internal_transfer', '内部往来'),
                    ('equity', '实收资本'),
                ],
                default='',
                help_text='收入科目分类：主营业务/其他业务/营业外收入/其他收益/投资收益/内部往来/实收资本',
                max_length=50,
                verbose_name='收入科目',
            ),
        ),
    ]
