# Generated manually for unique_together fix
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('finance', '0012_fix_unemployment_rate_precision'),
    ]
    operations = [
        migrations.AlterUniqueTogether(
            name='wagerecord',
            unique_together={('company', 'employee_company', 'year', 'month')},
        ),
    ]
