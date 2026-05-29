# Manually crafted — Phase1 permission system cleanup
# Only operates on tables/columns that still exist.
# core_rolepermission and core_userrole tables already dropped manually;
# menu_code column already removed manually.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def migrate_auditlog_references(apps, schema_editor):
    """Copy role_id/permission_id FK refs to role_name/permission_code text fields."""
    PermissionAuditLog = apps.get_model('core', 'PermissionAuditLog')
    Permission = apps.get_model('core', 'Permission')
    with schema_editor.connection.cursor() as c:
        c.execute("SELECT id, name FROM core_role")
        role_map = dict(c.fetchall())

    for log in PermissionAuditLog.objects.all():
        role_id = getattr(log, 'role_id', None)
        permission_id = getattr(log, 'permission_id', None)
        changed = False

        if role_id and role_id in role_map:
            log.role_name = role_map[role_id]
            changed = True
        if permission_id:
            try:
                perm = Permission.objects.get(id=permission_id)
                log.permission_code = perm.code
                changed = True
            except Permission.DoesNotExist:
                pass

        if changed:
            log.save(update_fields=['role_name', 'permission_code'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0023_add_bit_position'),
    ]

    operations = [
        # 1. Add new text fields to PermissionAuditLog
        migrations.AddField(
            model_name='permissionauditlog',
            name='permission_code',
            field=models.CharField(blank=True, default='', max_length=100, verbose_name='权限码'),
        ),
        migrations.AddField(
            model_name='permissionauditlog',
            name='role_name',
            field=models.CharField(blank=True, default='', max_length=100, verbose_name='角色名称'),
        ),

        # 2. Preserve audit log FK references
        migrations.RunPython(migrate_auditlog_references, reverse_code=migrations.RunPython.noop),

        # 3. Drop FK columns from PermissionAuditLog (data already saved in step 2)
        migrations.RemoveField(
            model_name='permissionauditlog',
            name='role',
        ),
        migrations.RemoveField(
            model_name='permissionauditlog',
            name='permission',
        ),

        # 4. Drop core_role table (7 rows of deprecated Phase1 data)
        migrations.DeleteModel(
            name='Role',
        ),
        # Note: RolePermission and UserRole tables were already dropped manually.
        # Use SeparateDatabaseAndState to update Django's project state
        # without trying to DROP TABLE on already-dropped tables.
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='RolePermission'),
                migrations.DeleteModel(name='UserRole'),
            ],
            database_operations=[],
        ),

        # 5. Update model field definitions to match current code
        migrations.AlterField(
            model_name='companyrolepermission',
            name='company_role',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='role_permissions', to='core.companyrole', verbose_name='公司角色'),
        ),
        migrations.AlterField(
            model_name='companyrolepermission',
            name='granted_at',
            field=models.DateTimeField(auto_now_add=True, verbose_name='授权时间'),
        ),
        migrations.AlterField(
            model_name='companyrolepermission',
            name='granted_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='授权人'),
        ),
        migrations.AlterField(
            model_name='companyrolepermission',
            name='permission',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='role_assignments', to='core.permission', verbose_name='权限'),
        ),
        migrations.AlterField(
            model_name='moduleaction',
            name='action_group',
            field=models.CharField(default='basic', max_length=20, verbose_name='动作分组'),
        ),
        migrations.AlterField(
            model_name='notification',
            name='notification_type',
            field=models.CharField(choices=[('task_overdue', '任务超时'), ('approval_timeout', '审批超时'), ('approval', '待审批'), ('approval_pending', '审批待处理'), ('contract_expiring', '合同到期'), ('large_expense', '大额支出'), ('project_overdue', '项目超时'), ('wage_pending', '工资待发放'), ('invoice_expiry', '发票到期')], default='info', max_length=20),
        ),
        migrations.AlterField(
            model_name='permission',
            name='action',
            field=models.CharField(max_length=50, verbose_name='动作'),
        ),
        migrations.AlterField(
            model_name='permission',
            name='category',
            field=models.CharField(max_length=50, verbose_name='分类'),
        ),
        migrations.AlterField(
            model_name='permission',
            name='code',
            field=models.CharField(max_length=100, unique=True, verbose_name='权限码'),
        ),
        migrations.AlterField(
            model_name='permission',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='是否激活'),
        ),
    ]
