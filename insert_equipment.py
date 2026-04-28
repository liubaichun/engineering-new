import sqlite3
import os
os.chdir('/root/engineering-new')

conn = sqlite3.connect('db.sqlite3')
c = conn.cursor()
now = '2026-04-23 13:00:00'
data = [
    ('SB-0001', 'Cisco Catalyst 2960 交换机', 'C2960-24TC-L', 'network', 'serial', None, 'SN2024C2960001', '台', 'idle', '仓库A-1-01', '2024-01-15', 2500.00, '2027-01-15', ''),
    ('SB-0002', 'Dell PowerEdge R740 服务器', 'R740-8B-SFF', 'server', 'serial', None, 'SN2024DELL74001', '台', 'in_use', '机房-2-03', '2024-02-20', 15000.00, '2027-02-20', ''),
    ('SB-0003', '海康威视网络摄像机', 'DS-2CD3T86FWDV2-I3S', 'monitor', 'serial', None, 'SN2024HIK86001', '台', 'idle', '仓库B-2-05', '2024-03-10', 800.00, '2026-03-10', ''),
    ('SB-0004', '六类网线（305米/箱）', 'CAT6-305M', 'cable', 'batch', 'BATCH-2024-001', None, '箱', 'idle', '仓库A-2-10', '2024-01-05', 450.00, '2026-01-05', ''),
    ('SB-0005', 'APC Smart-UPS 3KVA', 'SMT3000RMI2U', 'server', 'serial', None, 'SN2024APC300001', '台', 'repair', '机房-1-02', '2023-11-20', 8500.00, '2026-11-20', ''),
    ('SB-0006', '光纤跳线（SC-LC 3米）', 'SM-SCLC-3M', 'cable', 'quantity', None, None, '根', 'idle', '仓库B-1-08', '2024-04-15', 35.00, '2025-04-15', ''),
]
for d in data:
    c.execute('INSERT INTO equipment_equipment (code, name, spec, category, management_type, batch_number, serial_number, unit, status, location, purchase_date, purchase_price, warranty_end, remarks, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (*d, now, now))
conn.commit()
print('Done')
c.execute('SELECT code, name FROM equipment_equipment')
print(c.fetchall())