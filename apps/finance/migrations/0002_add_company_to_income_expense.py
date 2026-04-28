# Generated manually
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='expense',
            name='company',
            field=models.ForeignKey(
                default=1,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='expenses',
                to='finance.company',
                verbose_name='公司'
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='expense',
            name='expense_category',
            field=models.CharField(blank=True, default='', max_length=50, verbose_name='支出类别'),
        ),
        migrations.AddField(
            model_name='income',
            name='company',
            field=models.ForeignKey(
                default=1,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='incomes',
                to='finance.company',
                verbose_name='公司'
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='income',
            name='source',
            field=models.CharField(blank=True, default='', max_length=200, verbose_name='来源'),
        ),
    ]
