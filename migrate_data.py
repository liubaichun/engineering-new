#!/usr/bin/env python3
"""
SQLite → PostgreSQL 数据迁移脚本（v2）
每张表独立处理，单表失败不影响其他表
"""
import sqlite3
import psycopg2

SQLITE_PATH = '/root/engineering-new/db.sqlite3'
PG_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'dbname': 'engineering_new',
    'user': 'engineer',
    'password': 'engineer123'
}

TABLE_ORDER = [
    'django_content_type',
    'auth_permission',
    'django_migrations',
    'core_permission',
    'core_role',
    'auth_group',
    'core_system_setting',
    'core_user',
    'core_user_groups',
    'core_user_user_permissions',
    'core_user_company_role',
    'core_user_role',
    'company_file',
    'file_category',
    'finance_company',
    'finance_social_config',
    'crm_client',
    'crm_supplier',
    'finance_employee',
    'finance_employee_company',
    'tasks_flow_template',
    'tasks_flow_node_template',
    'tasks_flow_transition',
    'approvals_template',
    'tasks_project',
    'tasks_stage_activity',
    'tasks_task',
    'tasks_task_stage_instance',
    'tasks_task_flow_instance',
    'finance_income',
    'finance_expense',
    'finance_wage_record',
    'finance_invoice',
    'approvals_flow',
    'approvals_node',
    'equipment_equipment',
    'equipment_repair_log',
    'equipment_usage_log',
    'material_material',
    'material_usage_log',
    'core_notification',
    'core_login_log',
    'core_operation_audit_log',
    'django_session',
    'django_admin_log',
]

SKIP_TABLES = {'sqlite_sequence'}

def get_pg_columns(pg_cur, table):
    pg_cur.execute(f"""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = %s AND table_schema = 'public'
        ORDER BY ordinal_position
    """, (table,))
    return [r[0] for r in pg_cur.fetchall()]

def migrate_table_one_by_one(pg_cur, table, sqlite_cols, rows):
    """逐条插入，失败时记录但不中断"""
    if not rows:
        return 0

    pg_cols = get_pg_columns(pg_cur, table)
    common = [c for c in sqlite_cols if c in pg_cols]
    if not common:
        return 0

    insert = f"INSERT INTO {table} ({','.join(common)}) VALUES ({','.join(['%s'] * len(common))})"
    count = 0
    errors = []
    for row in rows:
        row_dict = dict(zip(sqlite_cols, row))
        vals = tuple(row_dict.get(c) for c in common)
        try:
            pg_cur.execute(insert, vals)
            count += 1
        except Exception as e:
            errors.append((vals[:3], str(e)[:80]))
    if errors:
        print(f"    {len(errors)} errors, first: {errors[0]}")
    return count

def main():
    print("=" * 60)
    print("SQLite → PostgreSQL 数据迁移 v2")
    print("=" * 60)

    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cur = sqlite_conn.cursor()

    pg_conn = psycopg2.connect(**PG_CONFIG)
    pg_conn.autocommit = True
    pg_cur = pg_conn.cursor()

    total = 0
    failed_tables = []
    print("\nMigrating...")
    for table in TABLE_ORDER:
        if table in SKIP_TABLES:
            continue

        # 获取SQLite数据
        sqlite_cur.execute(f"PRAGMA table_info({table})")
        sqlite_cols = [r[1] for r in sqlite_cur.fetchall()]
        sqlite_cur.execute(f"SELECT * FROM {table}")
        rows = sqlite_cur.fetchall()

        if not rows:
            print(f"  {table}: 0 rows, skip")
            continue

        # 清空PG表（先删后插）
        try:
            pg_cur.execute(f"DELETE FROM {table}")
        except Exception as e:
            print(f"  {table}: DELETE failed: {e}")
            continue

        # 迁移
        count = migrate_table_one_by_one(pg_cur, table, sqlite_cols, rows)
        total += count
        if count < len(rows):
            failed_tables.append((table, len(rows) - count))
        print(f"  {table}: {count}/{len(rows)} rows")

    # 验证
    print("\n" + "=" * 40)
    print("Verification:")
    key_tables = [
        'finance_wage_record', 'finance_income', 'finance_expense',
        'finance_invoice', 'finance_employee', 'finance_employee_company',
        'core_user', 'tasks_task', 'tasks_project', 'crm_client',
        'approvals_flow', 'approvals_node', 'core_notification',
        'core_login_log', 'material_material', 'equipment_equipment',
        'finance_company', 'file_category', 'approvals_template',
    ]
    all_ok = True
    for t in key_tables:
        sqlite_cur.execute(f"SELECT COUNT(*) FROM {t}")
        sc = sqlite_cur.fetchone()[0]
        try:
            pg_cur.execute(f"SELECT COUNT(*) FROM {t}")
            pc = pg_cur.fetchone()[0]
        except:
            pc = -1
        mark = "✓" if sc == pc else "✗"
        if sc != pc:
            all_ok = False
        print(f"  {mark} {t}: SQLite={sc}, PG={pc}")

    sqlite_conn.close()
    pg_conn.close()
    print(f"\n总计迁移: {total} rows")
    if failed_tables:
        print(f"部分失败: {failed_tables}")
    print("完成！")
    return all_ok

if __name__ == '__main__':
    import sys
    ok = main()
    sys.exit(0 if ok else 1)
