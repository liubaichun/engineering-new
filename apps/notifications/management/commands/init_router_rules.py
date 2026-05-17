"""
初始化30条通知路由规则
用法: python manage.py shell -c "exec(open('apps/notifications/management/commands/init_router_rules.py').read())"
"""
from apps.notifications.models import NotificationRouter

# 所有规则（company_id=null 表示全局）
rules = [
    # 任务相关
    ('task_created', 'normal', 'feishu', 'owner', ''),
    ('task_started', 'normal', 'feishu', 'owner', ''),
    ('task_completed', 'low', 'feishu', 'requester', ''),
    ('flow_started', 'normal', 'feishu', 'owner', ''),
    ('stage_started', 'normal', 'feishu', 'owner', ''),
    ('stage_completed', 'low', 'feishu', 'owner', ''),
    ('flow_completed', 'low', 'feishu', 'owner', ''),
    ('stage_timeout', 'critical', 'feishu', 'owner', ''),
    # 审批相关
    ('approval_created', 'important', 'feishu', 'all', ''),
    ('approval_result', 'normal', 'feishu', 'requester', ''),
    ('approval_transferred', 'normal', 'feishu', 'all', ''),
    ('approval_delegated', 'normal', 'feishu', 'all', ''),
    ('approval_timeout', 'important', 'feishu', 'owner', ''),
    # 合同相关
    ('contract_created', 'normal', 'feishu', 'owner', ''),
    ('contract_approved', 'normal', 'feishu', 'requester', ''),
    ('contract_rejected', 'normal', 'feishu', 'requester', ''),
    ('contract_expire_soon', 'important', 'feishu', 'owner', ''),
    # 项目相关
    ('project_created', 'normal', 'feishu', 'owner', ''),
    ('project_approval_submitted', 'important', 'feishu', 'all', ''),
    ('project_approval_result', 'normal', 'feishu', 'owner', ''),
    ('project_progress_changed', 'low', 'feishu', 'owner', ''),
    # 设备相关
    ('equipment_borrowed', 'normal', 'feishu', 'owner', ''),
    ('equipment_returned', 'low', 'feishu', 'owner', ''),
    ('equipment_repair', 'normal', 'feishu', 'owner', ''),
    # 维修相关
    ('repair_assigned', 'normal', 'feishu', 'all', ''),
    ('repair_started', 'low', 'feishu', 'requester', ''),
    ('repair_completed', 'normal', 'feishu', 'all', ''),
    ('repair_accepted', 'low', 'feishu', 'requester', ''),
    ('repair_rejected', 'important', 'feishu', 'all', ''),
]

created = 0
for event_type, priority, channel_type, recipient_scope, remarks in rules:
    obj, was_created = NotificationRouter.objects.get_or_create(
        event_type=event_type,
        channel_type=channel_type,
        defaults={
            'priority': priority,
            'recipient_scope': recipient_scope,
            'is_active': True,
            'remarks': remarks or f'系统自动初始化规则：{event_type}',
        }
    )
    if was_created:
        created += 1

print(f'初始化完成：共创建 {created} 条路由规则，现有 {NotificationRouter.objects.count()} 条')