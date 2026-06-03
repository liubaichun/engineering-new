#!/usr/bin/env python3
"""
权限系统修复脚本 - 43服务器
按顺序执行，每步验证后再下一步

使用 manage.py shell 执行：
  cd /root/engineering-new
  ./venv/bin/python manage.py shell < scripts/fix_permission_step1_verify.py
"""

import os, re

SCRIPT_DIR = '/root/engineering-new/scripts/permission_fix'
os.makedirs(SCRIPT_DIR, exist_ok=True)

# =============================================================================
# 步骤1：验证 VIEW_CATEGORY_MAP 和 action_perms 的当前状态
# =============================================================================
STEP1 = """
print("=" * 70)
print("步骤1：修复前状态验证")
print("=" * 70)

from apps.core.permissions import RoleRequired
from apps.approvals.views import ApprovalFlowViewSet, ApprovalNodeViewSet, ApprovalTemplateViewSet
from apps.core.models import Permission

# 1. 检查 VIEW_CATEGORY_MAP 中的 approval 相关映射
VIEW_MAP = {
    'ApprovalFlowViewSet': ('approval', 'flow'),
    'ApprovalNodeViewSet': ('approval', 'node'),
    'ApprovalTemplateViewSet': ('approval', 'template'),
}
print("\\n1. VIEW_CATEGORY_MAP 当前值：")
for view, (cat, res) in VIEW_MAP.items():
    print(f"   {view} -> ('{cat}', '{res}')")

# 2. 检查 action_perms 中的权限码格式
print("\\n2. action_perms 使用的权限码格式：")
for cls in [ApprovalFlowViewSet, ApprovalNodeViewSet, ApprovalTemplateViewSet]:
    action_perms = cls.action_perms
    none_val = action_perms.get(None, 'N/A')
    print(f"   {cls.__name__}.action_perms[None] = '{none_val}'")

# 3. 检查 Permission 表中的 approval 相关码
all_codes = set(Permission.objects.values_list('code', flat=True))
print("\\n3. Permission 表中的 approval 相关码：")
approval_codes = sorted([c for c in all_codes if c.startswith('approval:')])
for c in approval_codes:
    print(f"   {c}")

flow_codes = [c for c in approval_codes if ':flow:' in c]
approval_approval_codes = [c for c in approval_codes if c.startswith('approval:approval:')]
print(f"\\n   approval:flow:* 数量: {len(flow_codes)}")
print(f"   approval:approval:* 数量: {len(approval_approval_codes)}")

# 4. 模拟 _resolve_action_perm 对 list action 的结果
print("\\n4. 模拟 _resolve_action_perm 对 list action 的结果：")
ri = RoleRequired()
for cls_name, (cat, res) in VIEW_MAP.items():
    code = f"{cat}:{res}:read"
    in_perm = code in all_codes
    status = "存在" if in_perm else "缺失"
    print(f"   {cls_name}.list -> '{code}' -> {status}")

print("\\n结论：需要将 VIEW_CATEGORY_MAP 统一为 approval:approval 格式")
"""

with open(f'{SCRIPT_DIR}/step1_verify_before.py', 'w') as f:
    f.write(STEP1)
print(f"已保存：{SCRIPT_DIR}/step1_verify_before.py")

# =============================================================================
# 步骤2：修复 VIEW_CATEGORY_MAP
# =============================================================================
STEP2 = """
print("=" * 70)
print("步骤2：修复 VIEW_CATEGORY_MAP")
print("=" * 70)

import shutil

# 读取 permissions.py
filepath = '/root/engineering-new/apps/core/permissions.py'
with open(filepath, 'r') as f:
    content = f.read()

# 备份
backup_path = filepath + '.bak.step2'
shutil.copy(filepath, backup_path)
print(f"备份已保存：{backup_path}")

# 执行替换
old_lines = """        'ApprovalFlowViewSet': ('approval', 'flow'),
        'ApprovalNodeViewSet': ('approval', 'node'),
        'ApprovalTemplateViewSet': ('approval', 'template'),"""

new_lines = """        'ApprovalFlowViewSet': ('approval', 'approval'),
        'ApprovalNodeViewSet': ('approval', 'approval'),
        'ApprovalTemplateViewSet': ('approval', 'approval'),"""

if old_lines in content:
    content = content.replace(old_lines, new_lines)
    with open(filepath, 'w') as f:
        f.write(content)
    print("VIEW_CATEGORY_MAP 已修改：")
    print("   ApprovalFlowViewSet  -> ('approval', 'approval')")
    print("   ApprovalNodeViewSet  -> ('approval', 'approval')")
    print("   ApprovalTemplateViewSet -> ('approval', 'approval')")
else:
    print("未找到需要修改的内容（可能已修改过）")

# 验证
with open(filepath, 'r') as f:
    verify = f.read()
if "'ApprovalFlowViewSet': ('approval', 'approval')" in verify:
    print("\\n验证通过：VIEW_CATEGORY_MAP 已正确修改")
else:
    print("\\n验证失败：修改未成功")
"""

with open(f'{SCRIPT_DIR}/step2_fix_view_map.py', 'w') as f:
    f.write(STEP2)
print(f"已保存：{SCRIPT_DIR}/step2_fix_view_map.py")

# =============================================================================
# 步骤3：验证 VIEW_CATEGORY_MAP 修复后效果
# =============================================================================
STEP3 = """
print("=" * 70)
print("步骤3：验证 VIEW_CATEGORY_MAP 修复后效果")
print("=" * 70)

# 重新加载模块
import sys
for mod in list(sys.modules.keys()):
    if 'apps.core' in mod or 'apps.approvals' in mod:
        del sys.modules[mod]

# 重新导入
from apps.core.permissions import RoleRequired
from apps.core.models import Permission

VIEW_MAP_FIXED = {
    'ApprovalFlowViewSet': ('approval', 'approval'),
    'ApprovalNodeViewSet': ('approval', 'approval'),
    'ApprovalTemplateViewSet': ('approval', 'approval'),
}

all_codes = set(Permission.objects.values_list('code', flat=True))

print("\\n修复后 _resolve_action_perm 对 list action 的结果：")
for cls_name, (cat, res) in VIEW_MAP_FIXED.items():
    code = f"{cat}:{res}:read"
    in_perm = code in all_codes
    print(f"   {cls_name}.list -> '{code}' -> {'存在' if in_perm else '缺失'}")

approval_approval_codes = sorted([c for c in all_codes if 'approval:approval:' in c])
print(f"\\nPermission 表中的 approval:approval:* 码: {len(approval_approval_codes)} 个")
if approval_approval_codes:
    print(f"   现有: {approval_approval_codes}")
else:
    print("   缺少 approval:approval:* 权限码，需要补充到 Permission 表")
"""

with open(f'{SCRIPT_DIR}/step3_verify_after_map.py', 'w') as f:
    f.write(STEP3)
print(f"已保存：{SCRIPT_DIR}/step3_verify_after_map.py")

# =============================================================================
# 步骤4：补充 Permission 表缺失的码
# =============================================================================
STEP4 = """
print("=" * 70)
print("步骤4：补充 Permission 表缺失的权限码")
print("=" * 70)

from apps.core.models import Permission

# 备份
import shutil
from datetime import datetime
backup_name = f'/root/engineering-new/apps/core/models.py.bak.step4.{datetime.now().strftime("%Y%m%d%H%M%S")}'
shutil.copy('/root/engineering-new/apps/core/models.py', backup_name)
print(f"备份已保存：{backup_name}")

# 缺失的权限码列表（按 category 分组）
MISSING_PERMS = [
    # approval:approval:* (5个)
    ('approval:approval:read', '审批管理-读取', 'approval', 'approval', '审批基础读取权限'),
    ('approval:approval:create', '审批管理-创建', 'approval', 'approval', '审批基础创建权限'),
    ('approval:approval:update', '审批管理-更新', 'approval', 'approval', '审批基础更新权限'),
    ('approval:approval:delete', '审批管理-删除', 'approval', 'approval', '审批基础删除权限'),
    ('approval:approval:approve', '审批管理-审批', 'approval', 'approval', '审批基础审批权限'),
    # finance:bank:* (2个)
    ('finance:bank:read', '银行账户-读取', 'finance', 'bank', '银行账户读取权限'),
    ('finance:bank:update', '银行账户-更新', 'finance', 'bank', '银行账户更新权限'),
    # finance:budget:* (4个)
    ('finance:budget:create', '预算管理-创建', 'finance', 'budget', '预算创建权限'),
    ('finance:budget:read', '预算管理-读取', 'finance', 'budget', '预算读取权限'),
    ('finance:budget:update', '预算管理-更新', 'finance', 'budget', '预算更新权限'),
    ('finance:budget:delete', '预算管理-删除', 'finance', 'budget', '预算删除权限'),
    # finance:social_security:* (2个)
    ('finance:social_security:read', '社保管理-读取', 'finance', 'social_security', '社保读取权限'),
    ('finance:social_security:update', '社保管理-更新', 'finance', 'social_security', '社保更新权限'),
    # purchasing:purchase_order:* (3个)
    ('purchasing:purchase_order:create', '采购订单-创建', 'purchasing', 'purchase_order', '采购订单创建权限'),
    ('purchasing:purchase_order:read', '采购订单-读取', 'purchasing', 'purchase_order', '采购订单读取权限'),
    ('purchasing:purchase_order:update', '采购订单-更新', 'purchasing', 'purchase_order', '采购订单更新权限'),
    # purchasing:purchase_receive:* (3个)
    ('purchasing:purchase_receive:create', '采购入库-创建', 'purchasing', 'purchase_receive', '采购入库创建权限'),
    ('purchasing:purchase_receive:read', '采购入库-读取', 'purchasing', 'purchase_receive', '采购入库读取权限'),
    ('purchasing:purchase_receive:update', '采购入库-更新', 'purchasing', 'purchase_receive', '采购入库更新权限'),
    # purchasing:purchase_request:* (3个)
    ('purchasing:purchase_request:create', '采购申请-创建', 'purchasing', 'purchase_request', '采购申请创建权限'),
    ('purchasing:purchase_request:read', '采购申请-读取', 'purchasing', 'purchase_request', '采购申请读取权限'),
    ('purchasing:purchase_request:update', '采购申请-更新', 'purchasing', 'purchase_request', '采购申请更新权限'),
    # task:* (9个)
    ('task:activity:create', '任务活动-创建', 'task', 'activity', '任务活动创建权限'),
    ('task:attachment:create', '任务附件-创建', 'task', 'attachment', '任务附件创建权限'),
    ('task:comment:create', '任务评论-创建', 'task', 'comment', '任务评论创建权限'),
    ('task:dependency:create', '任务依赖-创建', 'task', 'dependency', '任务依赖创建权限'),
    ('task:flow_instance:create', '流程实例-创建', 'task', 'flow_instance', '流程实例创建权限'),
    ('task:flow_node:create', '流程节点-创建', 'task', 'flow_node', '流程节点创建权限'),
    ('task:flow_template:create', '流程模板-创建', 'task', 'flow_template', '流程模板创建权限'),
    ('task:stage_instance:create', '阶段实例-创建', 'task', 'stage_instance', '阶段实例创建权限'),
    ('task:transition:create', '任务转换-创建', 'task', 'transition', '任务转换创建权限'),
]

existing_codes = set(Permission.objects.values_list('code', flat=True))
to_insert = [p for p in MISSING_PERMS if p[0] not in existing_codes]

print(f"需要插入的权限码数量: {len(to_insert)}")
print(f"已存在的权限码数量: {len(existing_codes)}")

if to_insert:
    print("\\n插入中...")
    for code, name, cat, res, desc in to_insert:
        perm, created = Permission.objects.get_or_create(
            code=code,
            defaults={
                'name': name,
                'category': cat,
                'resource': res,
                'action': code.split(':')[-1],
                'description': desc,
                'is_active': True,
            }
        )
        status = '新增' if created else '已存在'
        print(f"   {code} ({status})")
    print(f"\\n插入完成，共 {len(to_insert)} 条")
else:
    print("\\n没有需要插入的权限码（全部已存在）")

# 最终验证
final_codes = set(Permission.objects.values_list('code', flat=True))
missing_after = [p[0] for p in MISSING_PERMS if p[0] not in final_codes]
if missing_after:
    print(f"\\n仍有缺失: {missing_after}")
else:
    print("\\n所有 29 个权限码已全部插入 Permission 表")
"""

with open(f'{SCRIPT_DIR}/step4_insert_missing_perms.py', 'w') as f:
    f.write(STEP4)
print(f"已保存：{SCRIPT_DIR}/step4_insert_missing_perms.py")

# =============================================================================
# 步骤5：验证 Permission 表完整性
# =============================================================================
STEP5 = """
print("=" * 70)
print("步骤5：验证 Permission 表完整性")
print("=" * 70)

from apps.core.models import Permission, Module, ModuleAction, ACTION_BITS
import os, re

all_codes = set(Permission.objects.values_list('code', flat=True))
print(f"Permission 表总条数: {len(all_codes)}")

# 检查所有 Module 能生成的权限码
print("\\n检查所有 Module 生成的权限码是否在 Permission 表中：")
modules = Module.objects.all().order_by('category', 'name')
all_good = True
for m in modules:
    actions = list(ModuleAction.objects.filter(module=m).values_list('name', flat=True))
    for action in actions:
        code = f"{m.category}:{m.name}:{action}"
        if code not in all_codes:
            print(f"   缺失: {code} (module: {m.category}:{m.name})")
            all_good = False

if all_good:
    print("   所有 Module 生成的权限码均已在 Permission 表中")
else:
    print("   仍有缺失")

# 扫描所有 action_perms 引用
apps_dir = '/root/engineering-new/apps'
missing_from_action_perms = {}
total = 0

for app_name in ['finance', 'approvals', 'crm', 'purchasing', 'operations', 'tasks', 'projects', 'files', 'core']:
    app_dir = os.path.join(apps_dir, app_name)
    if not os.path.exists(app_dir):
        continue
    for view_file in os.listdir(app_dir):
        if not view_file.startswith('views') or not view_file.endswith('.py'):
            continue
        filepath = os.path.join(app_dir, view_file)
        try:
            content = open(filepath).read()
            pattern = re.compile(r'action_perms\s*=\s*\{([^}]+)\}', re.MULTILINE | re.DOTALL)
            for m in pattern.finditer(content):
                codes_in_block = re.findall(r"'([^']+)'", m.group(0))
                for code in codes_in_block:
                    if code and ':' in code:
                        total += 1
                        if code not in all_codes:
                            missing_from_action_perms.setdefault(code, []).append(f"{app_name}/{view_file}")
        except:
            pass

print(f"\\n扫描 action_perms 引用: {total} 个")
if missing_from_action_perms:
    print(f"仍有 {len(missing_from_action_perms)} 个权限码缺失：")
    for code, sources in sorted(missing_from_action_perms.items()):
        print(f"   缺失: {code}")
        for s in sources:
            print(f"      <- {s}")
else:
    print("所有 action_perms 引用的权限码均已在 Permission 表中")
"""

with open(f'{SCRIPT_DIR}/step5_verify_perms.py', 'w') as f:
    f.write(STEP5)
print(f"已保存：{SCRIPT_DIR}/step5_verify_perms.py")

print(f"\\n所有脚本已保存到：{SCRIPT_DIR}/")
print("""
执行顺序：
1. step1_verify_before.py   - 验证修复前状态
2. step2_fix_view_map.py     - 修复 VIEW_CATEGORY_MAP
3. step3_verify_after_map.py - 验证 VIEW_CATEGORY_MAP 修复后效果
4. step4_insert_missing_perms.py - 补充 Permission 表缺失的码
5. step5_verify_perms.py     - 验证 Permission 表完整性

每步执行后检查输出，确认后再执行下一步。
""")
