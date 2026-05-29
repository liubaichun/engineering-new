"""
直接模拟导入函数，看看缺失的17条到底发生了什么
"""
import os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, '/root/engineering-new')
import django
django.setup()

from apps.finance.import_social_records import import_social_records

excel_path = '/root/.hermes/profiles/hermes-b001/cache/documents/doc_e2de73598919_深圳市百川软件科技发展有限公司_社保费申报明细_20260527.xlsx2401.xlsx'

with open(excel_path, 'rb') as f:
    result = import_social_records(f)

print('=== 导入结果 ===')
import json
print(json.dumps(result, ensure_ascii=False, indent=2))
