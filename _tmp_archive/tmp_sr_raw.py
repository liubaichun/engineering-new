"""
直接查数据库是否有这些身份证的记录
"""
import os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, '/root/engineering-new')
import django
django.setup()

from apps.finance.models import SocialRecord
from django.db import connection

# 直接用SQL查
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT id, company_id, id_card, year_month, total_company, employee_id 
        FROM finance_social_record 
        WHERE id_card IN (
            '450702198711264215', '360313199811260019',
            '450702198005054245', '420984198707172473',
            '341203198105053412', '431121198703038844'
        )
        ORDER BY id_card, year_month
    """)
    rows = cursor.fetchall()
    
    if rows:
        print(f'在数据库中找到 {len(rows)} 条记录:')
        for r in rows:
            print(f'  id={r[0]} company_id={r[1]} 身份证={r[2]} ym={r[3]} total={r[4]} employee_id={r[5]}')
    else:
        print('❌ 数据库中没有这些身份证的任何记录！')
    
    # 检查导入的24条记录的公司
    cursor.execute("""
        SELECT company_id, COUNT(*) 
        FROM finance_social_record 
        WHERE created_at >= '2026-05-27'
        GROUP BY company_id
    """)
    print()
    print('新导入记录的公司分布:')
    for r in cursor.fetchall():
        print(f'  company_id={r[0]}: {r[1]}条')

    # 看导入错误日志
    cursor.execute("""
        SELECT company_id, employee_id, year_month, id_card
        FROM finance_social_record 
        WHERE created_at >= '2026-05-27 14:29:00'
        ORDER BY id
    """)
    new_recs = cursor.fetchall()
    print(f'\n新导入记录数: {len(new_recs)}')
    
    # 检查unique_together
    cursor.execute("""
        SELECT conname, contype, pg_get_constraintdef(oid)
        FROM pg_constraint
        WHERE conrelid = 'finance_social_record'::regclass
    """)
    print('约束:')
    for r in cursor.fetchall():
        print(f'  {r[0]}: {r[2]}')
