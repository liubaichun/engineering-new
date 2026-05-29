"""
0023_add_bit_position.py
为 ModuleAction 添加 bit_position 字段
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0022_add_user_module_permission'),
    ]

    operations = [
        migrations.AddField(
            model_name='moduleaction',
            name='bit_position',
            field=models.IntegerField(default=0, verbose_name='位掩码位置'),
        ),
    ]
