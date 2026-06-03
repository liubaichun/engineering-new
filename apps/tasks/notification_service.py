"""
通知路由 — 按事件类型分发到 channels 渠道插件

包括：基础路由函数 dispatch_notify + 13 个业务事件桥接函数
"""

import logging

logger = logging.getLogger(__name__)

# ================================================================
# 事件类型常量
# ================================================================
EVENT_EQUIPMENT = 'equipment'
EVENT_TASK = 'task'
EVENT_CONTRACT = 'contract'
EVENT_REPAIR = 'repair'
EVENT_PROJECT = 'project'
EVENT_FLOW = 'flow'
EVENT_FLOW_STAGE_TIMEOUT = 'flow_stage_timeout'
EVENT_WAGE = 'wage'  # 工资


def dispatch_notify(event_type, context, priority='normal', title='', content_lines=None, action_url=''):
    """
    路由通知：根据事件类型查找公司对应的渠道插件，发送给相关用户。

    流程：
        1. 获取公司ID
        2. 检查公司是否有已激活渠道
        3. 解析目标用户
        4. 过滤用户偏好（禁用/允许的渠道）
        5. 调用 send_notification() 统一发送
    """
    from apps.channels.services import send_notification
    from apps.channels.models import Channel

    company_id = context.get('company_id')
    if not company_id:
        logger.debug('[dispatch_notify] context 中无 company_id，跳过')
        return

    # 检查公司是否有已激活渠道
    channels = Channel.objects.filter(company_id=company_id, is_active=True)
    if not channels.exists():
        logger.debug(f'[dispatch_notify] 公司 {company_id} 无已激活渠道，跳过')
        return

    # 确定目标用户
    target_users = _resolve_recipients('owner', context)
    if not target_users:
        logger.debug(f'[dispatch_notify] 无通知对象: event={event_type}')
        return

    # 过滤用户偏好
    user_ids = []
    for user in target_users:
        pref = _get_user_preference(user, event_type)
        if pref is not None and not pref.is_enabled:
            logger.debug(f'[dispatch_notify] 用户 {user.username} 已禁用 {event_type}，跳过')
            continue
        user_ids.append(user.id)

    if not user_ids:
        logger.debug(f'[dispatch_notify] 所有用户都跳过了: event={event_type}')
        return

    result = send_notification(
        company_id=company_id,
        title=title,
        content='\n'.join(content_lines or []),
        user_ids=user_ids,
        notification_type=event_type,
    )

    if result.get('sent', 0) > 0:
        logger.info(f'[dispatch_notify] 发送成功: event={event_type}, sent={result["sent"]}')
    elif result.get('message') == '未配置通知渠道':
        logger.debug(f'[dispatch_notify] 公司 {company_id} 未配置通知渠道，跳过')
    else:
        logger.warning(f'[dispatch_notify] 发送结果: event={event_type}, result={result}')


def _resolve_recipients(scope, context):
    """根据 scope 从 context 中解析目标用户"""
    from django.contrib.auth import get_user_model

    User = get_user_model()

    if scope == 'owner':
        owner = context.get('notify_target')
        return [owner] if owner else []
    elif scope == 'requester':
        requester = context.get('requester')
        return [requester] if requester else []
    elif scope == 'custom':
        ids = context.get('custom_user_ids', '')
        if not ids:
            return []
        return list(User.objects.filter(id__in=ids.split(','), is_active=True))
    return []


def _get_user_preference(user, event_type):
    """获取用户对某事件类型的通知偏好"""
    from apps.notifications.models import UserNotificationPreference

    return UserNotificationPreference.objects.filter(
        user=user, event_type=event_type
    ).first()


def _get_company_id(obj):
    """从任意模型实例获取 company_id（支持 FK 字段名为 company / company_id）"""
    if hasattr(obj, 'company_id') and obj.company_id:
        return obj.company_id
    if hasattr(obj, 'company') and obj.company:
        return obj.company_id if hasattr(obj, 'company_id') else obj.company.id
    return None


# ================================================================
# 13 个业务事件桥接函数
# ================================================================

def notify_equipment_action(equipment, action, user):
    """
    设备借出/归还/维修 → 通知保管人

    调用来源：apps/equipment/views.py
        notify_equipment_action(equipment, 'borrow', request.user)
        notify_equipment_action(equipment, 'return', request.user)
        notify_equipment_action(equipment, 'repair', request.user)
    """
    company_id = _get_company_id(equipment)
    if not company_id:
        logger.debug('[notify_equipment_action] 无 company_id，跳过')
        return

    action_labels = {
        'borrow': '借出',
        'return': '归还',
        'repair': '维修',
    }
    label = action_labels.get(action, action)

    # 设备没有保管人字段，通知项目负责人
    from apps.tasks.models import Project
    project = None
    if hasattr(equipment, 'project_id') and equipment.project_id:
        project = Project.objects.filter(id=equipment.project_id).first()

    notify_target = project.owner if project else None
    if not notify_target:
        logger.debug('[notify_equipment_action] 无通知对象，跳过')
        return

    dispatch_notify(
        event_type=EVENT_EQUIPMENT,
        context={'company_id': company_id, 'notify_target': notify_target},
        title=f'设备{label}通知',
        content_lines=[
            f'设备：{equipment.name}（{equipment.code}）',
            f'操作：{label}',
            f'操作人：{user.get_full_name() or user.username}',
        ],
    )


def notify_task_created(instance, created_by):
    """
    任务创建 → 通知负责人（assignee）

    调用来源：
        apps/equipment/views_task.py → notify_task_created(instance, created_by)
        apps/tasks/views_task.py → notify_task_created(instance, created_by)
    """
    company_id = _get_company_id(instance)
    if not company_id:
        logger.debug('[notify_task_created] 无 company_id，跳过')
        return

    assignee = instance.assignee if hasattr(instance, 'assignee') else None
    if not assignee:
        logger.debug('[notify_task_created] 无负责人（assignee），跳过')
        return

    dispatch_notify(
        event_type=EVENT_TASK,
        context={'company_id': company_id, 'notify_target': assignee},
        title='新任务通知',
        content_lines=[
            f'任务：{instance.title}',
            f'创建人：{created_by.get_full_name() or created_by.username}',
        ],
    )


def notify_task_started(task, started_by):
    """
    任务开始 → 通知任务创建人（reporter）

    调用来源：
        apps/equipment/views_task.py → notify_task_started(task, started_by=request.user)
        apps/tasks/views_task.py → notify_task_started(task, started_by=request.user)
    """
    company_id = _get_company_id(task)
    if not company_id:
        logger.debug('[notify_task_started] 无 company_id，跳过')
        return

    reporter = task.reporter if hasattr(task, 'reporter') else None
    if not reporter:
        logger.debug('[notify_task_started] 无 reporter，跳过')
        return

    dispatch_notify(
        event_type=EVENT_TASK,
        context={'company_id': company_id, 'notify_target': reporter},
        title='任务已开始',
        content_lines=[
            f'任务：{task.title}',
            f'执行人：{started_by.get_full_name() or started_by.username} 已开始处理',
        ],
    )


def notify_task_completed(task, completed_by):
    """
    任务完成 → 通知任务创建人（reporter）

    调用来源：
        apps/equipment/views_task.py → notify_task_completed(task, completed_by=request.user)
        apps/tasks/views_task.py → notify_task_completed(task, completed_by=request.user)
    """
    company_id = _get_company_id(task)
    if not company_id:
        logger.debug('[notify_task_completed] 无 company_id，跳过')
        return

    reporter = task.reporter if hasattr(task, 'reporter') else None
    if not reporter:
        logger.debug('[notify_task_completed] 无 reporter，跳过')
        return

    dispatch_notify(
        event_type=EVENT_TASK,
        context={'company_id': company_id, 'notify_target': reporter},
        title='任务已完成',
        content_lines=[
            f'任务：{task.title}',
            f'完成人：{completed_by.get_full_name() or completed_by.username}',
        ],
    )


def notify_contract_created(contract):
    """
    合同创建 → 通知合同负责人（created_by / 项目负责人）

    调用来源：apps/crm/views.py → notify_contract_created(instance)
    """
    company_id = _get_company_id(contract)
    if not company_id:
        logger.debug('[notify_contract_created] 无 company_id，跳过')
        return

    # 合同没有专属负责人字段，优先通知创建人
    notify_target = None
    if hasattr(contract, 'created_by') and contract.created_by:
        notify_target = contract.created_by

    if not notify_target:
        logger.debug('[notify_contract_created] 无通知对象，跳过')
        return

    dispatch_notify(
        event_type=EVENT_CONTRACT,
        context={'company_id': company_id, 'notify_target': notify_target},
        title='合同创建通知',
        content_lines=[
            f'合同：{contract.name}（{contract.contract_no}）',
            f'金额：{contract.amount}',
        ],
    )


def notify_contract_rejected(contract):
    """
    合同驳回 → 通知创建人

    调用来源：apps/crm/views.py → notify_contract_rejected(contract)
    """
    company_id = _get_company_id(contract)
    if not company_id:
        logger.debug('[notify_contract_rejected] 无 company_id，跳过')
        return

    notify_target = None
    if hasattr(contract, 'created_by') and contract.created_by:
        notify_target = contract.created_by

    if not notify_target:
        logger.debug('[notify_contract_rejected] 无通知对象，跳过')
        return

    dispatch_notify(
        event_type=EVENT_CONTRACT,
        context={'company_id': company_id, 'notify_target': notify_target},
        title='合同已驳回',
        content_lines=[
            f'合同：{contract.name}（{contract.contract_no}）',
            '状态：已驳回，请查看原因后重新提交',
        ],
    )


def notify_contract_approved(contract):
    """
    合同生效 → 通知创建人

    调用来源：apps/crm/views.py → notify_contract_approved(contract)
    """
    company_id = _get_company_id(contract)
    if not company_id:
        logger.debug('[notify_contract_approved] 无 company_id，跳过')
        return

    notify_target = None
    if hasattr(contract, 'created_by') and contract.created_by:
        notify_target = contract.created_by

    if not notify_target:
        logger.debug('[notify_contract_approved] 无通知对象，跳过')
        return

    dispatch_notify(
        event_type=EVENT_CONTRACT,
        context={'company_id': company_id, 'notify_target': notify_target},
        title='合同已生效',
        content_lines=[
            f'合同：{contract.name}（{contract.contract_no}）',
            f'金额：{contract.amount}',
            '状态：已生效',
        ],
    )


def notify_repair_action(obj, action, user):
    """
    维修进度更新 → 通知报修人

    调用来源：apps/repair/views.py
        notify_repair_action(obj, 'assigned', request.user)
        notify_repair_action(obj, 'started', request.user)
        notify_repair_action(obj, 'completed', request.user)
        notify_repair_action(obj, 'accepted', request.user)
        notify_repair_action(obj, 'rejected', request.user)
        notify_repair_action(obj, 'cancelled', request.user)
    """
    company_id = _get_company_id(obj)
    if not company_id:
        logger.debug('[notify_repair_action] 无 company_id，跳过')
        return

    action_labels = {
        'assigned': '已派工',
        'started': '维修中',
        'completed': '维修完成',
        'accepted': '验收通过',
        'rejected': '验收不通过',
        'cancelled': '已取消',
    }
    label = action_labels.get(action, action)

    # 通知报修人
    notify_target = obj.reporter if hasattr(obj, 'reporter') and obj.reporter else None
    if not notify_target:
        logger.debug('[notify_repair_action] 无报修人（reporter），跳过')
        return

    dispatch_notify(
        event_type=EVENT_REPAIR,
        context={'company_id': company_id, 'notify_target': notify_target},
        title=f'维修单更新：{label}',
        content_lines=[
            f'报修单号：{obj.request_no}',
            f'设备：{obj.equipment.name if obj.equipment else "—"}',
            f'状态更新：{label}',
            f'操作人：{user.get_full_name() or user.username}',
        ],
    )


def notify_project_created(instance, user):
    """
    项目创建 → 通知项目负责人（owner）

    调用来源：apps/tasks/views_project.py → notify_project_created(instance, self.request.user)
    """
    company_id = _get_company_id(instance)
    if not company_id:
        logger.debug('[notify_project_created] 无 company_id，跳过')
        return

    notify_target = instance.owner if hasattr(instance, 'owner') and instance.owner else None
    if not notify_target:
        logger.debug('[notify_project_created] 无项目负责人（owner），跳过')
        return

    dispatch_notify(
        event_type=EVENT_PROJECT,
        context={'company_id': company_id, 'notify_target': notify_target},
        title='新项目通知',
        content_lines=[
            f'项目：{instance.name}（{instance.code}）',
            f'创建人：{user.get_full_name() or user.username}',
        ],
    )


def notify_flow_started(task, stage_instance, started_by):
    """
    流程启动 → 通知第一个阶段的处理人

    调用来源：apps/tasks/flow_engine.py → notify_flow_started(self.task, stage_instance, started_by)
    """
    company_id = _get_company_id(task)
    if not company_id:
        logger.debug('[notify_flow_started] 无 company_id，跳过')
        return

    notify_target = stage_instance.assignee if hasattr(stage_instance, 'assignee') else None
    if not notify_target:
        logger.debug('[notify_flow_started] 无阶段处理人，跳过')
        return

    dispatch_notify(
        event_type=EVENT_FLOW,
        context={'company_id': company_id, 'notify_target': notify_target},
        title='流程审批通知',
        content_lines=[
            f'任务：{task.title}',
            f'阶段：{stage_instance.node_template.name if stage_instance.node_template else "—"}',
            f'发起人：{started_by.get_full_name() or started_by.username}',
            '请及时处理',
        ],
    )


def notify_stage_completed(task, current, next_instance, action, actor):
    """
    阶段完成/流转 → 通知下一阶段处理人

    调用来源：apps/tasks/flow_engine.py → notify_stage_completed(self.task, current, next_instance, action, actor)
    """
    company_id = _get_company_id(task)
    if not company_id:
        logger.debug('[notify_stage_completed] 无 company_id，跳过')
        return

    notify_target = next_instance.assignee if hasattr(next_instance, 'assignee') else None
    if not notify_target:
        logger.debug('[notify_stage_completed] 无下一阶段处理人，跳过')
        return

    dispatch_notify(
        event_type=EVENT_FLOW,
        context={'company_id': company_id, 'notify_target': notify_target},
        title='流程阶段流转',
        content_lines=[
            f'任务：{task.title}',
            f'上一阶段：{current.node_template.name if current.node_template else "—"}',
            f'下一阶段：{next_instance.node_template.name if next_instance.node_template else "—"}',
            f'操作：{action}',
            f'处理人：{actor.get_full_name() or actor.username}',
            '请及时处理',
        ],
    )


def notify_flow_completed(task, actor):
    """
    流程完成 → 通知任务创建人（reporter）

    调用来源：apps/tasks/flow_engine.py → notify_flow_completed(self.task, actor)
    """
    company_id = _get_company_id(task)
    if not company_id:
        logger.debug('[notify_flow_completed] 无 company_id，跳过')
        return

    notify_target = task.reporter if hasattr(task, 'reporter') and task.reporter else None
    if not notify_target:
        logger.debug('[notify_flow_completed] 无 reporter，跳过')
        return

    dispatch_notify(
        event_type=EVENT_FLOW,
        context={'company_id': company_id, 'notify_target': notify_target},
        title='流程已完成',
        content_lines=[
            f'任务：{task.title}',
            '状态：流程已全部完成',
        ],
    )


def notify_stage_timeout(stage):
    """
    阶段超时 → 通知阶段处理人（assignee）

    调用来源：apps/tasks/management/commands/check_task_timeouts.py
        notify_stage_timeout(stage)
    """
    company_id = _get_company_id(stage)
    if not company_id:
        logger.debug('[notify_stage_timeout] 无 company_id，跳过')
        return

    notify_target = stage.assignee if hasattr(stage, 'assignee') and stage.assignee else None
    if not notify_target:
        logger.debug('[notify_stage_timeout] 无 assignee，跳过')
        return

    task_title = stage.task.title if hasattr(stage, 'task') and stage.task else '—'

    dispatch_notify(
        event_type=EVENT_FLOW_STAGE_TIMEOUT,
        context={'company_id': company_id, 'notify_target': notify_target},
        title='流程阶段超时提醒',
        content_lines=[
            f'任务：{task_title}',
            '当前阶段已超时，请尽快处理',
        ],
    )


def notify_wage_paid(wage_record, operator):
    """
    工资发放 → 通知审批人和操作人

    调用来源：apps/finance/views_wage.py → notify_wage_paid(wage_record, request.user)
    """
    company_id = _get_company_id(wage_record)
    if not company_id:
        logger.debug('[notify_wage_paid] 无 company_id，跳过')
        return

    # 通知该工资单的审批人（approver）
    notify_target = None
    if hasattr(wage_record, 'approver') and wage_record.approver:
        notify_target = wage_record.approver

    if not notify_target:
        logger.debug('[notify_wage_paid] 无审批人（approver），跳过')
        return

    dispatch_notify(
        event_type=EVENT_WAGE,
        context={'company_id': company_id, 'notify_target': notify_target},
        title='工资发放通知',
        content_lines=[
            f'员工：{wage_record.employee_name}',
            f'期间：{wage_record.year}年{wage_record.month}月',
            f'实发金额：¥{wage_record.net_salary}',
            f'操作人：{operator.get_full_name() or operator.username}',
        ],
    )
