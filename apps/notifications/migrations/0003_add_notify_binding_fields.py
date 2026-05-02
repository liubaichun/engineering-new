# Generated manually — aligns model state with actual DB structure for notify_binding
# DB reality: notify_binding has notify_app_id FK (NOT channel_id)
# Model has: channel FK + platform + receive_all + unique(user, channel, platform_open_id)
# This migration adds DB columns channel_id, platform, receive_all + fixes unique_together
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0002_initial'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE notify_binding ADD COLUMN channel_id bigint;
            ALTER TABLE notify_binding ADD COLUMN platform varchar(20) DEFAULT 'feishu' NOT NULL;
            ALTER TABLE notify_binding ADD COLUMN receive_all boolean DEFAULT true NOT NULL;
            """,
            reverse_sql="""
            ALTER TABLE notify_binding DROP COLUMN IF EXISTS receive_all;
            ALTER TABLE notify_binding DROP COLUMN IF EXISTS platform;
            ALTER TABLE notify_binding DROP COLUMN IF EXISTS channel_id;
            """,
        ),
        # unique_together in DB is (user_id, notify_app_id); model should reflect that
        migrations.AlterUniqueTogether(
            name='notifybinding',
            unique_together={('user', 'notify_app')},
        ),
    ]
