#!/usr/bin/env python3
"""
SQLite → PostgreSQL 迁移脚本 v3
策略：读取所有数据 → Python类型转换 → CSV输出 → psql \copy 导入
处理 SQLite 0/1 → PostgreSQL TRUE/FALSE
处理 timestamp 格式问题
"""
import sqlite3
import csv
import io
import os
import re

SQLITE_PATH = '/root/engineering-new/db.sqlite3'
PG_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'dbname': 'engineering_new',
    'user': 'engineer',
    'password': 'engineer123'
}
PG_CSV_DIR = '/tmp/pg_csv'

os.makedirs(PG_CSV_DIR, exist_ok=True)

# 需要检测Boolean类型的列（从PG schema推断）
BOOLEAN_COLUMNS = {}  # (table, column) -> True

# 所有表（含依赖顺序）
TABLE_ORDER = [
    'core_permission',
    'core_role',
    'core_system_setting',
    'core_user',
    'core_user_company_role',
    'core_user_role',
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

# 不迁移的表
SKIP_TABLES = {
    'django_content_type', 'auth_permission', 'auth_group',
    'auth_group_permissions', 'core_user_groups', 'core_user_user_permissions',
    'django_migrations', 'django_session', 'company_file',
    'sqlite_sequence', 'tasks_task_flow_instance',
}


def get_pg_columns():
    """从PostgreSQL获取所有表的列类型"""
    import psycopg2
    conn = psycopg2.connect(**PG_CONFIG)
    cur = conn.cursor()
    boolean_cols = {}

    for table in TABLE_ORDER:
        if table in SKIP_TABLES:
            continue
        try:
            cur.execute(f"""
                SELECT column_name, data_type, udt_name
                FROM information_schema.columns
                WHERE table_name = %s AND table_schema = 'public'
            """, (table,))
            for row in cur.fetchall():
                col, dtype, udt = row
                if dtype == 'boolean' or udt == 'bool':
                    boolean_cols[(table, col)] = True
        except:
            pass
    conn.close()
    return boolean_cols


def convert_sqlite_value(table, col, value, boolean_cols):
    """将SQLite值转换为PostgreSQL兼容格式"""
    if value is None:
        return ''

    # Boolean: SQLite用0/1存储
    if (table, col) in boolean_cols:
        if value in (1, '1', True):
            return 'TRUE'
        elif value in (0, '0', False):
            return 'FALSE'
        return 'TRUE' if value else 'FALSE'

    # Timestamp格式: SQLite "2026-04-23-11:00:00" → PostgreSQL "2026-04-23 11:00:00"
    if isinstance(value, str):
        # 匹配 "YYYY-MM-DD-HH:MM:SS" 格式并转换为 "YYYY-MM-DD HH:MM:SS"
        if re.match(r'^\d{4}-\d{2}-\d{2}-\d{2}:\d{2}:\d{2}', value):
            value = value.replace('-', ' ', 1).replace('-', ':', 1)
        # 处理带时区的timestamp格式
        elif re.match(r'^\d{4}-\d{2}-\d{2}-\d{2}:\d{2}:\d{2}\.\d+', value):
            value = re.sub(r'^(\d{4}-\d{2}-\d{2})-(\d{2}):(\d{2}):(\d{2})\.(\d+)',
                           r'\1 \2:\3:\4.\5', value)
        # 去除尾部横杠
        value = value.rstrip('-')

        # 转义双引号和反斜杠（CSV格式）
        value = value.replace('\\', '\\\\').replace('"', '""')

    # 数字/其他：转字符串
    return str(value)


def export_table_to_csv(sqlite_conn, table, boolean_cols, csv_dir):
    """导出单个表到CSV"""
    cur = sqlite_conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    cols = [r[1] for r in cur.fetchall()]
    cur.execute(f"SELECT * FROM {table}")
    rows = cur.fetchall()

    if not rows:
        return 0

    csv_path = os.path.join(csv_dir, f"{table}.csv")
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)

        # Header
        writer.writerow(cols)

        # Data rows
        for row in rows:
            converted = [convert_sqlite_value(table, c, v, boolean_cols) for c, v in zip(cols, row)]
            writer.writerow(converted)

    return len(rows)


def import_csv_to_pg(table, csv_dir):
    """用 psql \copy 导入CSV"""
    import subprocess
    csv_path = os.path.join(csv_dir, f"{table}.csv")
    if not os.path.exists(csv_path):
        return 0

    # 检查文件是否为空
    if os.path.getsize(csv_path) == 0:
        return 0

    result = subprocess.run([
        'psql', '-h', 'localhost', '-p', '5432',
        '-U', 'engineer',
        '-d', 'engineering_new',
        '-c', f"\\COPY {table} FROM '{csv_path}' WITH (FORMAT CSV, HEADER true, NULL '')"
    ], env={**os.environ, 'PGPASSWORD': 'engineer123'},
       capture_output=True, text=True)

    if result.returncode != 0:
        print(f"    psql error: {result.stderr[:200]}")
        return 0

    # 读取导入行数（stderr里有 "COPY N"）
    for line in result.stderr.split('\n'):
        if 'COPY' in line:
            parts = line.split()
            if len(parts) >= 2:
                try:
                    return int(parts[-1])
                except:
                    pass
    return -1


def main():
    import psycopg2

    print("=" * 60)
    print("SQLite → PostgreSQL 迁移 v3 (CSV方式)")
    print("=" * 60)

    # 1. 获取PG布尔列
    print("\n[1] 获取PostgreSQL列类型...")
    boolean_cols = get_pg_columns()
    bool_count = len(boolean_cols)
    print(f"    布尔列数量: {bool_count}")

    # 2. 连接SQLite
    print(f"\n[2] 读取SQLite...")
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cur = sqlite_conn.cursor()

    # 3. 导出CSV
    print(f"\n[3] 导出CSV到 {PG_CSV_DIR}...")
    total_export = 0
    for table in TABLE_ORDER:
        if table in SKIP_TABLES:
            continue
        try:
            count = export_table_to_csv(sqlite_conn, table, boolean_cols, PG_CSV_DIR)
            if count > 0:
                print(f"    {table}: {count} rows → CSV")
                total_export += count
            else:
                print(f"    {table}: 0 rows, skip")
        except Exception as e:
            print(f"    {table}: export ERROR - {e}")

    # 4. 清空PG表（按依赖顺序，从叶子节点开始）
    print(f"\n[4] 清空PostgreSQL表...")
    pg_conn = psycopg2.connect(**PG_CONFIG)
    pg_conn.autocommit = True
    pg_cur = pg_conn.cursor()

    for table in reversed(TABLE_ORDER):
        if table in SKIP_TABLES:
            continue
        try:
            pg_cur.execute(f"DELETE FROM {table}")
            print(f"    DELETE {table}")
        except Exception as e:
            print(f"    DELETE {table}: {e}")

    # 5. 导入CSV
    print(f"\n[5] 导入CSV到PostgreSQL...")
    total_import = 0
    for table in TABLE_ORDER:
        if table in SKIP_TABLES:
            continue
        try:
            count = import_csv_to_pg(table, PG_CSV_DIR)
            total_import += count if count > 0 else 0
            status = f"{count} rows" if count >= 0 else "error"
            print(f"    {table}: {status}")
        except Exception as e:
            print(f"    {table}: import ERROR - {e}")

    # 6. 验证
    print(f"\n[6] 验证...")
    key_tables = [
        'finance_wage_record', 'finance_income', 'finance_expense',
        'finance_invoice', 'finance_employee', 'finance_employee_company',
        'core_user', 'tasks_task', 'tasks_project', 'crm_client',
        'approvals_flow', 'approvals_node', 'core_notification',
        'material_material', 'equipment_equipment',
        'finance_company', 'file_category', 'approvals_template',
    ]
    all_ok = True
    for t in key_tables:
        if t in SKIP_TABLES:
            continue
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
        print(f"    {mark} {t}: SQLite={sc}, PG={pc}")

    sqlite_conn.close()
    pg_conn.close()
    print(f"\n总计: 导出{total_export} rows, 导入{total_import} rows")
    print("完成！")
    return all_ok


if __name__ == '__main__':
    import sys
    ok = main()
    sys.exit(0 if ok else 1)
