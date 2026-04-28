from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0001_initial'),
    ]

    operations = [
        # Manual changes already applied via direct SQL:
        # - crm_client: added code + category columns, updated existing rows with KH-YYYY-NNNN codes
        # - crm_supplier: created table with all fields
        # This migration is a no-op marker to record the change
        migrations.RunSQL("SELECT 1;", reverse_sql="SELECT 1;"),
    ]
