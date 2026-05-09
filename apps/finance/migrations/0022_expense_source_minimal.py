# Generated manually — adds only expense.source field
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0021_add_expense_source_field'),
    ]

    operations = [
        migrations.AddField(
            model_name='expense',
            name='source',
            field=models.CharField(blank=True, default='', max_length=200, verbose_name='来源'),
        ),
    ]
