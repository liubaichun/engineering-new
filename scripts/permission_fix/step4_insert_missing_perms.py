
print("=" * 70)
print("步骤4：补充 Permission 表缺失的权限码")
print("=" * 70)

from apps.core.models import Permission
import shutil
from datetime import datetime

backup_name = f"/root/engineering-new/apps/core/models.py.bak.step4.{datetime.now().strftime('%Y%m%d%H%M%S')}"
shutil.copy("/root/engineering-new/apps/core/models.py", backup_name)
print(f"备份已保存：{backup_name}")

MISSING_PERMS = [
    ("approval:approval:read", "审批管理-读取", "approval", "approval", "审批基础读取权限"),
    ("approval:approval:create", "审批管理-创建", "approval", "approval", "审批基础创建权限"),
    ("approval:approval:update", "审批管理-更新", "approval", "approval", "审批基础更新权限"),
    ("approval:approval:delete", "审批管理-删除", "approval", "approval", "审批基础删除权限"),
    ("approval:approval:approve", "审批管理-审批", "approval", "approval", "审批基础审批权限"),
    ("finance:bank:read", "银行账户-读取", "finance", "bank", "银行账户读取权限"),
    ("finance:bank:update", "银行账户-更新", "finance", "bank", "银行账户更新权限"),
    ("finance:budget:create", "预算管理-创建", "finance", "budget", "预算创建权限"),
    ("finance:budget:read", "预算管理-读取", "finance", "budget", "预算读取权限"),
    ("finance:budget:update", "预算管理-更新", "finance", "budget", "预算更新权限"),
    ("finance:budget:delete", "预算管理-删除", "finance", "budget", "预算删除权限"),
    ("finance:social_security:read", "社保管理-读取", "finance", "social_security", "社保读取权限"),
    ("finance:social_security:update", "社保管理-更新", "finance", "social_security", "社保更新权限"),
    ("purchasing:purchase_order:create", "采购订单-创建", "purchasing", "purchase_order", "采购订单创建权限"),
    ("purchasing:purchase_order:read", "采购订单-读取", "purchasing", "purchase_order", "采购订单读取权限"),
    ("purchasing:purchase_order:update", "采购订单-更新", "purchasing", "purchase_order", "采购订单更新权限"),
    ("purchasing:purchase_receive:create", "采购入库-创建", "purchasing", "purchase_receive", "采购入库创建权限"),
    ("purchasing:purchase_receive:read", "采购入库-读取", "purchasing", "purchase_receive", "采购入库读取权限"),
    ("purchasing:purchase_receive:update", "采购入库-更新", "purchasing", "purchase_receive", "采购入库更新权限"),
    ("purchasing:purchase_request:create", "采购申请-创建", "purchasing", "purchase_request", "采购申请创建权限"),
    ("purchasing:purchase_request:read", "采购申请-读取", "purchasing", "purchase_request", "采购申请读取权限"),
    ("purchasing:purchase_request:update", "采购申请-更新", "purchasing", "purchase_request", "采购申请更新权限"),
    ("task:activity:create", "任务活动-创建", "task", "activity", "任务活动创建权限"),
    ("task:attachment:create", "任务附件-创建", "task", "attachment", "任务附件创建权限"),
    ("task:comment:create", "任务评论-创建", "task", "comment", "任务评论创建权限"),
    ("task:dependency:create", "任务依赖-创建", "task", "dependency", "任务依赖创建权限"),
    ("task:flow_instance:create", "流程实例-创建", "task", "flow_instance", "流程实例创建权限"),
    ("task:flow_node:create", "流程节点-创建", "task", "flow_node", "流程节点创建权限"),
    ("task:flow_template:create", "流程模板-创建", "task", "flow_template", "流程模板创建权限"),
    ("task:stage_instance:create", "阶段实例-创建", "task", "stage_instance", "阶段实例创建权限"),
    ("task:transition:create", "任务转换-创建", "task", "transition", "任务转换创建权限"),
]

existing_codes = set(Permission.objects.values_list("code", flat=True))
to_insert = [p for p in MISSING_PERMS if p[0] not in existing_codes]

print(f"需要插入的权限码数量: {len(to_insert)}")
print(f"已存在的权限码数量: {len(existing_codes)}")

if to_insert:
    print("
插入中...")
    for code, name, cat, res, desc in to_insert:
        perm, created = Permission.objects.get_or_create(
            code=code,
            defaults={
                "name": name,
                "category": cat,
                "resource": res,
                "action": code.split(":")[-1],
                "description": desc,
                "is_active": True,
            }
        )
        status = "新增" if created else "已存在"
        print(f"   {code} ({status})")
    print(f"
插入完成，共 {len(to_insert)} 条")
else:
    print("
没有需要插入的权限码（全部已存在）")

final_codes = set(Permission.objects.values_list("code", flat=True))
missing_after = [p[0] for p in MISSING_PERMS if p[0] not in final_codes]
if missing_after:
    print(f"
仍有缺失: {missing_after}")
else:
    print("
所有 29 个权限码已全部插入 Permission 表")
