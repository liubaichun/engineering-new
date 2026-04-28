# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_add_permission_category'),
    ]

    operations = [
        migrations.AddField(
            model_name='permission',
            name='menu_code',
            field=models.CharField(
                verbose_name='菜单编码',
                max_length=50,
                blank=True,
                default='',
                help_text='关联的菜单编码，如 project.list, task.create'
            ),
        ),
    ]
