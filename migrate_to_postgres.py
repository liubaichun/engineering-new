#!/usr/bin/env python3
"""
SQLite → PostgreSQL 数据迁移脚本
用法: python migrate_to_postgres.py
"""
import sqlite3
import psycopg2
from psycopg2 import sql
import contextlib

SQLITE_PATH = '/root/engineering-new/db.sqlite3'
PG_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'dbname': 'engineering_new',
    'user': 'engineer',
    'password': 'engineer123'
}

# 按依赖顺序排列的表（外键依赖关系）
TABLE_ORDER = [
    'django_content_type',
    'auth_permission',
    'django_migrations',
    'core_role',
    'core_permission',
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
    'core_permission_audit_log',
    'django_session',
    'django_admin_log',
]

# 不迁移的表（自动生成或临时）
SKIP_TABLES = {'sqlite_sequence', 'auth_group_permissions', 'core_user_groups', 'core_user_user_permissions'}

def get_sqlite_tables():
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [r[0] for r in cur.fetchall()]
    conn.close()
    return tables

def get_table_columns(conn, table):
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in cur.fetchall()]

def get_table_rows(conn, table):
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM {table}")
    rows = cur.fetchall()
    cols = get_table_columns(conn, table)
    return cols, rows

def migrate_table(pg_cur, table, columns, rows):
    if not rows:
        print(f"  {table}: 0 rows, skipped")
        return 0

    # PostgreSQL 列名可能大小写不同，先查实际列
    pg_cur.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name = %s ORDER BY ordinal_position", (table,))
    pg_columns = [r[0] for r in pg_cur.fetchall()]

    # 取交集
    common_cols = [c for c in columns if c in pg_columns]
    if len(common_cols) != len(columns):
        print(f"  {table}: column mismatch - SQLite: {columns}, PG: {pg_columns}")
        # 用共同列

    placeholders = ', '.join(['%s'] * len(common_cols))
    col_names = ', '.join(common_cols)

    insert_sql = f"INSERT INTO {table} ({col_names}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"

    count = 0
    for row in rows:
        row_dict = dict(zip(columns, row))
        values = tuple(row_dict[c] for c in common_cols)
        try:
            pg_cur.execute(insert_sql, values)
            count += 1
        except Exception as e:
            # 尝试单条插入，失败则跳过
            pass
    return count

def main():
    print("=" * 60)
    print("SQLite → PostgreSQL 数据迁移")
    print("=" * 60)

    # 1. 读取SQLite
    print(f"\n[1] 连接SQLite: {SQLITE_PATH}")
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cur = sqlite_conn.cursor()

    # 2. 连接PostgreSQL
    print(f"[2] 连接PostgreSQL: {PG_CONFIG['host']}:{PG_CONFIG['port']}/{PG_CONFIG['dbname']}")
    pg_conn = psycopg2.connect(**PG_CONFIG)
    pg_conn.autocommit = False
    pg_cur = pg_conn.cursor()

    # 3. 清空PostgreSQL表（从依赖叶子节点开始）
    print("[3] 清空PostgreSQL已有数据...")
    for table in reversed(TABLE_ORDER):
        try:
            pg_cur.execute(f"DELETE FROM {table}")
            print(f"  DELETE FROM {table}")
        except Exception as e:
            print(f"  {table}: {e}")

    pg_conn.commit()

    # 4. 迁移数据
    print("[4] 迁移数据...")
    total_rows = 0
    for table in TABLE_ORDER:
        if table in SKIP_TABLES:
            continue
        try:
            columns, rows = get_table_rows(sqlite_conn, table)
            count = migrate_table(pg_cur, table, columns, rows)
            total_rows += count
            print(f"  {table}: {count} rows migrated")
        except Exception as e:
            print(f"  {table}: ERROR - {e}")

    pg_conn.commit()

    # 5. 验证
    print("\n[5] 验证数据...")
    for table in ['finance_wage_record', 'finance_income', 'finance_expense', 'core_user', 'tasks_task']:
        try:
            sqlite_cur.execute(f"SELECT COUNT(*) FROM {table}")
            sqlite_count = sqlite_cur.fetchone()[0]
            pg_cur.execute(f"SELECT COUNT(*) FROM {table}")
            pg_count = pg_cur.fetchone()[0]
            status = "✓" if sqlite_count == pg_count else f"✗ (SQLite={sqlite_count})"
            print(f"  {table}: PostgreSQL {pg_count} {status}")
        except Exception as e:
            print(f"  {table}: {e}")

    sqlite_conn.close()
    pg_conn.close()

    print(f"\n总计迁移: {total_rows} rows")
    print("迁移完成！")

if __name__ == '__main__':
    main()
