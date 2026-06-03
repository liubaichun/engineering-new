
print("=" * 70)
print("步骤3：验证 VIEW_CATEGORY_MAP 修复后效果")
print("=" * 70)

import sys
for mod in list(sys.modules.keys()):
    if "apps.core" in mod or "apps.approvals" in mod:
        del sys.modules[mod]

from apps.core.permissions import RoleRequired
from apps.core.models import Permission

VIEW_MAP_FIXED = {
    "ApprovalFlowViewSet": ("approval", "approval"),
    "ApprovalNodeViewSet": ("approval", "approval"),
    "ApprovalTemplateViewSet": ("approval", "approval"),
}

all_codes = set(Permission.objects.values_list("code", flat=True))

print("
修复后 _resolve_action_perm 对 list action 的结果：")
for cls_name, (cat, res) in VIEW_MAP_FIXED.items():
    code = f"{cat}:{res}:read"
    in_perm = code in all_codes
    print(f"   {cls_name}.list -> '{code}' -> {'存在' if in_perm else '缺失'}")

approval_approval_codes = sorted([c for c in all_codes if "approval:approval:" in c])
print(f"
Permission 表中的 approval:approval:* 码: {len(approval_approval_codes)} 个")
if approval_approval_codes:
    print(f"   现有: {approval_approval_codes}")
else:
    print("   缺少 approval:approval:* 权限码，需要补充到 Permission 表")
