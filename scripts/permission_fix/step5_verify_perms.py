
print("=" * 70)
print("步骤5：验证 Permission 表完整性")
print("=" * 70)

from apps.core.models import Permission, Module, ModuleAction, ACTION_BITS
import os, re

all_codes = set(Permission.objects.values_list("code", flat=True))
print(f"Permission 表总条数: {len(all_codes)}")

print("
检查所有 Module 生成的权限码是否在 Permission 表中：")
modules = Module.objects.all().order_by("category", "name")
all_good = True
for m in modules:
    actions = list(ModuleAction.objects.filter(module=m).values_list("name", flat=True))
    for action in actions:
        code = f"{m.category}:{m.name}:{action}"
        if code not in all_codes:
            print(f"   缺失: {code} (module: {m.category}:{m.name})")
            all_good = False

if all_good:
    print("   所有 Module 生成的权限码均已在 Permission 表中")

apps_dir = "/root/engineering-new/apps"
missing_from_action_perms = {}
total = 0

for app_name in ["finance", "approvals", "crm", "purchasing", "operations", "tasks", "projects", "files", "core"]:
    app_dir = os.path.join(apps_dir, app_name)
    if not os.path.exists(app_dir):
        continue
    for view_file in os.listdir(app_dir):
        if not view_file.startswith("views") or not view_file.endswith(".py"):
            continue
        filepath = os.path.join(app_dir, view_file)
        try:
            content = open(filepath).read()
            pattern = re.compile(r"action_perms\s*=\s*\{([^}]+)\}", re.MULTILINE | re.DOTALL)
            for m in pattern.finditer(content):
                codes_in_block = re.findall(r"'([^']+)'", m.group(0))
                for code in codes_in_block:
                    if code and ":" in code:
                        total += 1
                        if code not in all_codes:
                            missing_from_action_perms.setdefault(code, []).append(f"{app_name}/{view_file}")
        except:
            pass

print(f"
扫描 action_perms 引用: {total} 个")
if missing_from_action_perms:
    print(f"仍有 {len(missing_from_action_perms)} 个权限码缺失：")
    for code, sources in sorted(missing_from_action_perms.items()):
        print(f"   缺失: {code}")
        for s in sources:
            print(f"      <- {s}")
else:
    print("所有 action_perms 引用的权限码均已在 Permission 表中")
