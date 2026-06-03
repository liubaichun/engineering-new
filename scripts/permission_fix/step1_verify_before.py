
print("=" * 70)
print("步骤1：修复前状态验证")
print("=" * 70)

from apps.core.permissions import RoleRequired
from apps.approvals.views import ApprovalFlowViewSet, ApprovalNodeViewSet, ApprovalTemplateViewSet
from apps.core.models import Permission

VIEW_MAP = {
    "ApprovalFlowViewSet": ("approval", "flow"),
    "ApprovalNodeViewSet": ("approval", "node"),
    "ApprovalTemplateViewSet": ("approval", "template"),
}
print("
1. VIEW_CATEGORY_MAP 当前值：")
for view, (cat, res) in VIEW_MAP.items():
    print(f"   {view} -> ('{cat}', '{res}')")

print("
2. action_perms 使用的权限码格式：")
for cls in [ApprovalFlowViewSet, ApprovalNodeViewSet, ApprovalTemplateViewSet]:
    action_perms = cls.action_perms
    none_val = action_perms.get(None, "N/A")
    print(f"   {cls.__name__}.action_perms[None] = '{none_val}'")

all_codes = set(Permission.objects.values_list("code", flat=True))
print("
3. Permission 表中的 approval 相关码：")
approval_codes = sorted([c for c in all_codes if c.startswith("approval:")])
for c in approval_codes:
    print(f"   {c}")

flow_codes = [c for c in approval_codes if ":flow:" in c]
approval_approval_codes = [c for c in approval_codes if c.startswith("approval:approval:")]
print(f"
   approval:flow:* 数量: {len(flow_codes)}")
print(f"   approval:approval:* 数量: {len(approval_approval_codes)}")

print("
4. 模拟 _resolve_action_perm 对 list action 的结果：")
ri = RoleRequired()
for cls_name, (cat, res) in VIEW_MAP.items():
    code = f"{cat}:{res}:read"
    in_perm = code in all_codes
    status = "存在" if in_perm else "缺失"
    print(f"   {cls_name}.list -> '{code}' -> {status}")

print("
结论：需要将 VIEW_CATEGORY_MAP 统一为 approval:approval 格式")
