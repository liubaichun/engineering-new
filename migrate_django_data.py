#!/usr/bin/env python3
"""
Django数据迁移：SQLite → PostgreSQL
策略：Django dumpdata(JSON) → loaddata into PostgreSQL
关键：保持PK不变，修复sequence
"""
import os
import sys
import json
import django

# 先用SQLite配置
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'

# 临时改settings用SQLite
import config.settings as settings
ORIGINAL_DB = settings.DATABASES['default'].copy()

def use_sqlite():
    settings.DATABASES['default'] = {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': '/root/engineering-new/db.sqlite3',
    }
    # 重新初始化Django
    django.setup()

def use_postgres():
    settings.DATABASES['default'] = {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'engineering_new',
        'USER': 'engineer',
        'PASSWORD': 'engineer123',
        'HOST': 'localhost',
        'PORT': '5432',
    }
    # 清除已导入的module缓存，强制重新加载
    for app in list(sys.modules.keys()):
        if app.startswith('apps.') or app.startswith('django'):
            continue
    django.setup()

def fix_postgres_sequences():
    """PostgreSQL迁移后需要修复auto-increment序列"""
    import psycopg2
    conn = psycopg2.connect(
        host='localhost', port=5432,
        dbname='engineering_new', user='engineer', password='engineer123'
    )
    cur = conn.cursor()

    tables_with_identity = [
        'core_user', 'core_role', 'core_permission', 'core_system_setting',
        'core_notification', 'core_login_log', 'core_operation_audit_log',
        'finance_company', 'finance_employee', 'finance_employee_company',
        'finance_income', 'finance_expense', 'finance_wage_record',
        'finance_invoice', 'finance_social_config',
        'tasks_project', 'tasks_task', 'tasks_flow_template',
        'tasks_flow_node_template', 'tasks_flow_transition',
        'tasks_stage_activity', 'tasks_task_stage_instance',
        'approvals_template', 'approvals_flow', 'approvals_node',
        'crm_client', 'crm_supplier',
        'material_material', 'material_usage_log',
        'equipment_equipment', 'equipment_repair_log', 'equipment_usage_log',
        'file_category',
    ]

    for table in tables_with_identity:
        try:
            # 获取该表最大ID
            cur.execute(f'SELECT MAX(id) FROM {table}')
            max_id = cur.fetchone()[0]
            if max_id is not None:
                # 设置sequence为max_id+1
                cur.execute(f"SELECT pg_get_serial_sequence('{table}', 'id')")
                seq = cur.fetchone()[0]
                if seq:
                    cur.execute(f"SELECT setval('{seq}', {max_id + 1}, true)")
                    print(f"  {table}: sequence set to {max_id + 1}")
        except Exception as e:
            print(f"  {table}: {e}")
    conn.commit()
    conn.close()

def main():
    print("=" * 60)
    print("Django数据迁移：SQLite → PostgreSQL")
    print("=" * 60)

    FIXTURE_DIR = '/tmp/django_fixtures'
    os.makedirs(FIXTURE_DIR, exist_ok=True)

    # Step 1: 用SQLite配置导出dumpdata
    print("\n[1] 配置SQLite并导出dumpdata...")
    use_sqlite()

    from django.core import management
    from django.core.management import call_command

    # 禁用debug避免循环导入问题
    settings.DEBUG = False

    # 导出的app顺序（依赖顺序）
    apps_to_export = [
        'contenttypes', 'auth', 'core', 'approvals',
        'finance', 'crm', 'tasks', 'files', 'sessions',
        'equipment', 'material', 'notifications', 'admin',
    ]

    for app in apps_to_export:
        fixture_file = os.path.join(FIXTURE_DIR, f'{app}.json')
        print(f"  导出 {app}...", end=" ")
        try:
            with open(fixture_file, 'w') as f:
                call_command('dumpdata', app, stdout=f, verbosity=0)
            size = os.path.getsize(fixture_file)
            print(f"OK ({size} bytes)")
        except Exception as e:
            print(f"ERROR: {e}")

    # Step 2: 清空PostgreSQL所有表（按依赖顺序）
    print("\n[2] 清空PostgreSQL表...")
    use_postgres()
    settings.DEBUG = False

    from django import db
    from django.db import connection

    # 按依赖顺序清空
    tables_to_clear = [
        'core_operation_audit_log', 'core_login_log', 'core_notification',
        'core_permission_audit_log',
        'material_usage_log', 'material_material',
        'equipment_usage_log', 'equipment_repair_log', 'equipment_equipment',
        'approvals_node', 'approvals_flow',
        'finance_invoice', 'finance_wage_record', 'finance_expense',
        'finance_income', 'finance_social_config',
        'finance_employee_company', 'finance_employee', 'finance_company',
        'crm_contract', 'crm_client', 'crm_supplier',
        'tasks_task_stage_instance', 'tasks_task_flow_instance',
        'tasks_task', 'tasks_stage_activity',
        'tasks_flow_transition', 'tasks_flow_node_template',
        'tasks_flow_template', 'tasks_project',
        'approvals_template',
        'core_user_company_role', 'core_user_role', 'core_user',
        'core_system_setting', 'core_role', 'core_permission',
        'file_category', 'company_file',
        'auth_group_permissions', 'auth_user_groups', 'auth_user_user_permissions',
        'auth_group', 'django_admin_log', 'django_session',
        'django_migrations',
    ]

    with connection.cursor() as cur:
        for table in tables_to_clear:
            try:
                cur.execute(f'DELETE FROM {table}')
            except Exception as e:
                print(f"  DELETE {table}: {e}")

    # Step 3: 导入dumpdata
    print("\n[3] 导入dumpdata到PostgreSQL...")
    for app in apps_to_export:
        fixture_file = os.path.join(FIXTURE_DIR, f'{app}.json')
        if not os.path.exists(fixture_file) or os.path.getsize(fixture_file) == 0:
            print(f"  {app}: empty, skip")
            continue
        print(f"  导入 {app}...", end=" ")
        try:
            with open(fixture_file) as f:
                data = json.load(f)
            if not data:
                print("empty JSON, skip")
                continue

            # 逐条导入以便FK依赖顺序处理
            imported = call_command('loaddata', fixture_file, verbosity=0, commit=False)
            print(f"OK ({len(data)} records)")
        except Exception as e:
            print(f"ERROR: {e}")

    # Step 4: 修复PostgreSQL序列
    print("\n[4] 修复PostgreSQL auto-increment序列...")
    fix_postgres_sequences()

    # Step 5: 验证
    print("\n[5] 验证...")
    from django.core.management import call_command

    key_tables = [
        'finance_wage_record', 'finance_income', 'finance_expense',
        'finance_invoice', 'finance_employee', 'finance_employee_company',
        'core_user', 'tasks_task', 'tasks_project', 'crm_client',
        'approvals_flow', 'approvals_node', 'core_notification',
        'material_material', 'equipment_equipment',
        'finance_company', 'file_category', 'approvals_template',
    ]

    with connection.cursor() as cur:
        for t in key_tables:
            try:
                cur.execute(f'SELECT COUNT(*) FROM {t}')
                pc = cur.fetchone()[0]
                print(f"  {t}: {pc} rows")
            except Exception as e:
                print(f"  {t}: ERROR - {e}")

    print("\n完成！")
    print("注意：需重启gunicorn使settings.py修改生效")

if __name__ == '__main__':
    main()
