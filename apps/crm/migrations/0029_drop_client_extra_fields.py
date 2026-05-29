# Manually crafted — safely drop CRM client columns that exist only on 124
# These columns were added via migrations on 124 that never made it into git.
# The model code no longer references them.
# Uses DROP COLUMN IF EXISTS so it works safely on both servers.
from django.db import migrations


def drop_extra_columns(apps, schema_editor):
    """Safely drop client extra columns using IF EXISTS (PostgreSQL)."""
    with schema_editor.connection.cursor() as c:
        for col in ['short_name', 'collaborator', 'customer_status', 'level', 'parent_client_id', 'salesman']:
            c.execute(f'ALTER TABLE crm_client DROP COLUMN IF EXISTS {col}')
            # Also drop any index/constraint that might have been auto-created
            c.execute(f'DROP INDEX IF EXISTS crm_client_{col}_idx')
            c.execute(f'DROP INDEX IF EXISTS crm_client_{col}_like')


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0028_alter_contact_client_alter_contract_client_and_more'),
    ]

    operations = [
        migrations.RunPython(drop_extra_columns, reverse_code=migrations.RunPython.noop),
    ]
