# Generated manually
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('channels', '0003_add_soft_delete'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='ChannelPlugin',
            unique_together={('company', 'app_name')},
        ),
    ]
