# Manually crafted — state-only cleanup for already-dropped columns/constraints
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0024_remove_userrole_role_remove_rolepermission_role_and_more'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterUniqueTogether(
                    name='permission',
                    unique_together=set(),
                ),
                migrations.RemoveField(
                    model_name='permission',
                    name='menu_code',
                ),
            ],
            database_operations=[],
        ),
    ]
