# Manually crafted — indexes already removed manually
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('repair', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveIndex(
                    model_name='repairrequest',
                    name='repair_req_idx',
                ),
                migrations.RemoveIndex(
                    model_name='repairrequest',
                    name='repair_status_idx',
                ),
            ],
            database_operations=[],
        ),
    ]
