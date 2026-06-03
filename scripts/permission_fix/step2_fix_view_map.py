
print("=" * 70)
print("步骤2：修复 VIEW_CATEGORY_MAP")
print("=" * 70)

import shutil

filepath = "/root/engineering-new/apps/core/permissions.py"
with open(filepath, "r") as f:
    content = f.read()

backup_path = filepath + ".bak.step2"
shutil.copy(filepath, backup_path)
print(f"备份已保存：{backup_path}")

old_lines = """        "ApprovalFlowViewSet": ("approval", "flow"),
        "ApprovalNodeViewSet": ("approval", "node"),
        "ApprovalTemplateViewSet": ("approval", "template"),"""

new_lines = """        "ApprovalFlowViewSet": ("approval", "approval"),
        "ApprovalNodeViewSet": ("approval", "approval"),
        "ApprovalTemplateViewSet": ("approval", "approval"),"""

if old_lines in content:
    content = content.replace(old_lines, new_lines)
    with open(filepath, "w") as f:
        f.write(content)
    print("VIEW_CATEGORY_MAP 已修改：")
    print("   ApprovalFlowViewSet -> ('approval', 'approval')")
    print("   ApprovalNodeViewSet -> ('approval', 'approval')")
    print("   ApprovalTemplateViewSet -> ('approval', 'approval')")
else:
    print("未找到需要修改的内容（可能已修改过）")

with open(filepath, "r") as f:
    verify = f.read()
if "'ApprovalFlowViewSet': ('approval', 'approval')" in verify:
    print("
验证通过：VIEW_CATEGORY_MAP 已正确修改")
else:
    print("
验证失败：修改未成功")
