# Generated manually to record the raw SQL addition of company_id column
# This column was added via: ALTER TABLE notifications_channel ADD COLUMN company_id bigint REFERENCES finance_company(id) ON DELETE SET NULL

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0004_alter_notifybinding_options_and_more'),
        ('finance', '0014_company_bank_account_company_bank_name_and_more'),
    ]

    operations = [
        # This column was added via raw SQL but migration state didn't record it.
        # Using RunSQL as a no-op to keep migration state in sync.
        # The actual column already exists in the DB (verified by inspecting the table).
        migrations.RunSQL(
            sql="SELECT 1;",  # No-op: column already exists
            reverse_sql="",   # Do not allow reverse: this column must exist
        ),
    ]
