"""
0022_add_user_module_permission.py
新增 UserModulePermission 模型（位掩码权限存储）

UserModulePermission 取代 UserCompanyPermission 作为权限存储。
每条记录 = 用户 × 公司 × 模块，用 granted_bits 位掩码存储所有动作权限。
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0021_add_module_action_group'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserModulePermission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('granted_bits', models.BigIntegerField(default=0, verbose_name='授权位掩码')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='module_permissions', to='core.user')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='module_permissions', to='finance.company')),
                ('module', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user_permissions', to='core.module')),
            ],
            options={
                'verbose_name': '用户模块权限',
                'verbose_name_plural': '用户模块权限',
                'db_table': 'core_user_module_permission',
                'unique_together': {('user', 'company', 'module')},
            },
        ),
    ]
