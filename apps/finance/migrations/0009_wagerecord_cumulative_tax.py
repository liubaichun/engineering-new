# Generated manually for cumulative tax feature
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0008_wagerecord_approval_flow_fk'),
    ]

    operations = [
        migrations.AddField(
            model_name='wagerecord',
            name='cumulative_tax',
            field=models.DecimalField(decimal_places=2, default=0, editable=False, max_digits=12, verbose_name='累计税额'),
        ),
    ]
