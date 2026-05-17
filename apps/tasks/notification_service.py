"""
通知路由 — 按事件类型查表分发到外部渠道
"""
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)


def dispatch_notify(event_type, context, priority='normal', title='', content_lines=None, action_url=''):
    """
    查表路由通知：根据 event_type 查找 NotificationRouter，分发到对应渠道

    参数：
        event_type: str，如 'task_created' / 'contract_approved'
        context: dict，包含 notify_target（主送用户）、related_object 等
        priority: str，low/normal/important/critical
        title: str
        content_lines: list[str]
        action_url: str，可选
    """
    from apps.notifications.models import NotificationRouter
    from apps.channels.services import ChannelNotificationService

    company_id = context.get('company_id')

    # 1. 查找路由规则：优先公司级，fallback 全局
    routes = NotificationRouter.objects.filter(
        event_type=event_type,
        is_active=True,
    ).order_by('priority')

    # 公司级优先
    company_route = routes.filter(company_id=company_id).first()
    global_route = routes.filter(company_id__isnull=True).first()

    route = company_route or global_route
    if not route:
        logger.debug(f'[dispatch_notify] 无匹配路由规则: {event_type}')
        return

    # 2. 确定通知目标用户
    target_users = _resolve_recipients(route.recipient_scope, context)
    if not target_users:
        logger.debug(f'[dispatch_notify] 无通知对象: event={event_type}, scope={route.recipient_scope}')
        return

    # 3. 通过渠道服务发送
    for user in target_users:
        # 3a. 检查用户偏好：若禁用则跳过
        pref = _get_user_preference(user, event_type)
        if pref and not pref.is_enabled:
            logger.debug(f'[dispatch_notify] 用户 {user.username} 已禁用 {event_type}，跳过')
            continue

        # 3b. 确定渠道列表（偏好覆盖 > 路由表）
        channel_type = route.channel_type
        if pref and pref.allowed_channels:
            channel_types = pref.allowed_channels
        else:
            channel_types = [channel_type]

        for ct in channel_types:
            _send_via_channel_for_user(user, company_id, ct, event_type, title, content_lines)


def _resolve_recipients(scope, context):
    """根据 recipient_scope 从 context 解析目标用户列表"""
    from django.contrib.auth import get_user_model
    User = get_user_model()

    if scope == 'owner':
        owner = context.get('notify_target')  # 主通知对象（负责人/审批人）
        return [owner] if owner else []
    elif scope == 'requester':
        requester = context.get('requester')  # 申请人（合同创建者等）
        return [requester] if requester else []
    elif scope == 'custom':
        ids = context.get('custom_user_ids', '')
        if not ids:
            return []
        return list(User.objects.filter(id__in=ids.split(','), is_active=True))
    elif scope == 'all':
        # all = owner + requester，去重
        users = set()
        if context.get('notify_target'):
            users.add(context['notify_target'])
        if context.get('requester'):
            users.add(context['requester'])
        return list(users)
    return []


def _get_user_preference(user, event_type):
    from apps.notifications.models import UserNotificationPreference
    return UserNotificationPreference.objects.filter(user=user, event_type=event_type).first()


def _send_via_channel_for_user(user, company_id, channel_type, event_type, title, content_lines):
    from apps.channels.services import ChannelNotificationService
    from apps.channels.models import ChannelPlugin

    channel = ChannelPlugin.objects.filter(
        company_id=company_id, channel_type=channel_type, is_active=True, is_deleted=False
    ).first()
    if not channel:
        return

    try:
        ChannelNotificationService._send_via_channel(
            user=user, channel=channel, title=title,
            content='\n'.join(content_lines or []), notification_type=event_type,
        )
    except Exception as e:
        logger.warning(f'[dispatch_notify] 发送失败 user={user.username} channel={channel_type}: {e}')


import logging
from django.utils import timezone
logger = logging.getLogger(__name__)


def notify_contract_created(contract):
    """
    通知：新建合同
    contract: Contract 实例
    """
    from apps.core.email_service import notify_approval_created
    try:
        if hasattr(contract, 'approval_flow') and contract.approval_flow:
            # 如果合同需要审批，通知审批人
            notify_approval_created(contract.approval_flow)
    except Exception:
        pass
    # 同时通知合同创建者（知会）
    if contract.created_by:
        system_url = _get_system_url()
        content = [
            f'您创建了合同「{contract.name}」',
            f'合同编号：{contract.contract_no}',
            f'类型：{contract.get_counterparty_type_display()}',
        ]
        if contract.amount:
            content.append(f'金额：¥{contract.amount}')
        subject = f'【知会】合同创建成功：{contract.name}'
        try:
            from apps.core.email_service import notify_user
            notify_user(contract.created_by, subject, content, priority='normal')
        except Exception:
            pass


def notify_contract_approved(contract):
    """通知：合同审批通过"""
    from apps.core.email_service import notify_approval_result
    try:
        if hasattr(contract, 'approval_flow') and contract.approval_flow:
            notify_approval_result(contract.approval_flow, contract.approval_flow.approvalnode_set.filter(status='approved').first().approver, 'approved')
    except Exception:
        pass


def notify_contract_rejected(contract):
    """通知：合同审批驳回"""
    from apps.core.email_service import notify_approval_result
    try:
        if hasattr(contract, 'approval_flow') and contract.approval_flow:
            notify_approval_result(contract.approval_flow, contract.approval_flow.approvalnode_set.filter(status='rejected').first().approver, 'rejected')
    except Exception:
        pass


def notify_project_created(project, created_by):
    """
    通知：新建项目
    project: Project 实例
    created_by: User 实例
    """
    system_url = _get_system_url()
    content = [
        f'您创建了项目「{project.name}」',
        f'项目代码：{project.code}',
        f'预算：{"¥" + str(project.budget) if project.budget else "未设置"}',
    ]
    action_url = f'{system_url}/projects/{project.id}/'
    subject = f'【知会】项目创建成功：{project.name}'
    try:
        from apps.core.email_service import notify_user
        notify_user(created_by, subject, content, action_url, '查看项目', priority='normal')
    except Exception:
        pass


def notify_project_approval_result(project, approved_by, action):
    """
    通知：项目审批结果
    project: Project 实例
    approved_by: 审批人 User
    action: 'approved' | 'rejected'
    """
    if not project.owner:
        return
    system_url = _get_system_url()
    action_text_map = {'approved': '已批准 ✓', 'rejected': '已拒绝 ✗'}
    content = [
        f'您的项目「{project.name}」已被 {approved_by.username} {action_text_map.get(action, action)}',
        f'项目代码：{project.code}',
    ]
    action_url = f'{system_url}/projects/{project.id}/'
    subject = f'【项目审批】{project.name} — {action_text_map.get(action, action)}'
    try:
        from apps.core.email_service import notify_user
        notify_user(project.owner, subject, content, action_url, '查看项目', priority='important')
    except Exception:
        pass


def notify_project_progress_changed(project, old_status, new_status):
    """
    通知：项目进度/状态变更
    project: Project 实例
    """
    if not project.owner:
        return
    system_url = _get_system_url()
    content = [
        f'您的项目「{project.name}」状态已变更',
        f'原状态：{old_status} → 新状态：{new_status}',
    ]
    action_url = f'{system_url}/projects/{project.id}/'
    subject = f'【项目更新】{project.name} — {new_status}'
    try:
        from apps.core.email_service import notify_user
        notify_user(project.owner, subject, content, action_url, '查看项目', priority='normal')
    except Exception:
        pass


def notify_equipment_action(equipment, action, operator):
    """
    通知：设备领用/归还/维修
    equipment: Equipment 实例
    action: 'borrow' | 'return' | 'repair'
    operator: User 实例
    """
    if not equipment.maintainer:
        return
    system_url = _get_system_url()
    action_map = {
        'borrow': '已被领用',
        'return': '已归还',
        'repair': '已进入维修',
    }
    content = [
        f'设备「{equipment.name}」（编号：{equipment.code}）{action_map.get(action, action)}',
        f'操作人：{operator.username}',
        f'时间：{timezone.now().strftime("%Y-%m-%d %H:%M")}',
    ]
    subject = f'【设备动态】{equipment.name} — {action_map.get(action, action)}'
    try:
        from apps.core.email_service import notify_user
        notify_user(equipment.maintainer, subject, content, priority='normal')
    except Exception:
        pass


def notify_repair_action(repair_request, action, operator):
    """
    通知：维修工单状态变更
    repair_request: RepairRequest 实例
    action: 'assigned' | 'started' | 'completed' | 'accepted' | 'rejected' | 'cancelled'
    operator: User 实例
    """
    # 通知报修人
    if not repair_request.reporter:
        return
    system_url = _get_system_url()
    action_map = {
        'assigned': '已派工',
        'started': '已开始维修',
        'completed': '维修完成',
        'accepted': '已验收通过',
        'rejected': '验收不通过，已退回重修',
        'cancelled': '已被取消',
    }
    notify_targets = [repair_request.reporter]
    # 如果是派工，还通知维修负责人
    if action == 'assigned' and repair_request.assigned_to:
        notify_targets.append(repair_request.assigned_to)

    content = [
        f'您的报修单「{repair_request.request_no}」状态已更新：{action_map.get(action, action)}',
        f'设备：{repair_request.equipment.name if repair_request.equipment else "未知设备"}',
        f'操作人：{operator.username}',
        f'时间：{timezone.now().strftime("%Y-%m-%d %H:%M")}',
    ]
    subject = f'【维修动态】报修单 {repair_request.request_no} — {action_map.get(action, action)}'

    try:
        from apps.core.email_service import notify_user
        for target in set(notify_targets):
            notify_user(target, subject, content, priority='normal')
    except Exception:
        pass
    """获取用户所属公司ID"""
    if hasattr(user, 'company_id') and user.company_id:
        return user.company_id
    return None


def _send_to_user(user, title, content_lines, notification_type='task', priority='normal'):
    """通过 email_service 统一发通知"""
    if not user or not user.is_active:
        return
    try:
        from apps.core.email_service import notify_user
        notify_user(user, title, content_lines, priority=priority)
    except Exception as e:
        logger.warning(f'[TaskNotify] notify_user failed for {user.username}: {e}')


def _send_to_role(company_id, role_name, title, content_lines, notification_type='task'):
    """向公司内指定角色的所有用户发送通知"""
    if not company_id or not role_name:
        return
    try:
        from apps.core.email_service import notify_role
        notify_role(company_id, role_name, title, content_lines)
    except Exception as e:
        logger.warning(f'[TaskNotify] notify_role({role_name}) failed: {e}')


# ============================================================
# 公开 API：供 views.py / flow_engine.py 调用
# ============================================================

def notify_task_created(task, created_by=None):
    """
    任务创建通知
    触发时机：TaskViewSet.create() 成功后
    通知：assignee（任务执行人）、reporter（创建人知会）
    """
    company_id = _get_user_company_id(task.assignee) if task.assignee else None

    # 通知 assignee
    if task.assignee and task.assignee != created_by:
        title = f'📋 新任务：{task.title}'
        content = [
            f'您被分配了新任务「{task.title}」',
            f'任务编码：{task.code}',
            f'优先级：{task.get_priority_display() if task.priority else "普通"}',
            f'计划完成日期：{task.due_date.strftime("%Y-%m-%d") if task.due_date else "未设置"}',
            f'负责人：{created_by.get_full_name() if created_by else task.reporter}',
        ]
        if task.project:
            content.insert(1, f'所属项目：{task.project.name}')
        _send_to_user(task.assignee, title, content, notification_type='task', priority='normal')

    # 知会 reporter（创建人）
    if task.reporter and task.reporter != task.assignee:
        title = f'📋 任务已创建：{task.title}'
        content = [
            f'您创建的任务「{task.title}」已分配给 {task.assignee.get_full_name() if task.assignee else "待分配"}',
            f'任务编码：{task.code}',
            f'计划完成日期：{task.due_date.strftime("%Y-%m-%d") if task.due_date else "未设置"}',
        ]
        if task.project:
            content.insert(1, f'所属项目：{task.project.name}')
        _send_to_user(task.reporter, title, content, notification_type='task', priority='normal')


def notify_task_started(task, started_by):
    """
    任务开始通知
    触发时机：TaskViewSet.start() 成功后
    通知：reporter（知会任务已启动）
    """
    if task.reporter and task.reporter != started_by:
        title = f'▶️ 任务已开始：{task.title}'
        content = [
            f'任务「{task.title}」已开始处理',
            f'执行人：{started_by.get_full_name() if started_by else started_by.username}',
            f'计划完成日期：{task.due_date.strftime("%Y-%m-%d") if task.due_date else "未设置"}',
        ]
        _send_to_user(task.reporter, title, content, notification_type='task', priority='normal')


def notify_task_completed(task, completed_by):
    """
    任务完成通知
    触发时机：TaskViewSet.complete() 成功后
    通知：reporter（知会任务已完成）、可能还有项目经理
    """
    # 知会 reporter
    if task.reporter and task.reporter != completed_by:
        title = f'✅ 任务已完成：{task.title}'
        content = [
            f'任务「{task.title}」已完成',
            f'执行人：{completed_by.get_full_name() if completed_by else completed_by.username}',
            f'完成时间：{task.completed_at.strftime("%Y-%m-%d %H:%M") if task.completed_at else timezone.now().strftime("%Y-%m-%d %H:%M")}',
        ]
        if task.project:
            content.append(f'所属项目：{task.project.name}')
        _send_to_user(task.reporter, title, content, notification_type='task', priority='normal')


def notify_flow_started(task, stage_instance, started_by):
    """
    流程启动通知
    触发时机：FlowEngine.start_flow() 末尾
    通知：第一个阶段的 assignee
    """
    if not stage_instance.assignee or stage_instance.assignee == started_by:
        return

    title = f'🔄 流程待处理：{task.title}'
    content = [
        f'您有一个流程待处理',
        f'任务：「{task.title}」',
        f'流程模板：{stage_instance.node_template.template.name if stage_instance.node_template else ""}',
        f'当前节点：{stage_instance.node_template.name if stage_instance.node_template else ""}',
    ]
    if stage_instance.node_template.timeout_hours:
        content.append(f'要求完成时间：{stage_instance.node_template.timeout_hours} 小时')

    _send_to_user(stage_instance.assignee, title, content, notification_type='task', priority='normal')


def notify_stage_completed(task, stage_instance, next_stage_instance, action, actor):
    """
    阶段完成通知（流转到下一节点时）
    触发时机：FlowEngine.complete_node() 创建下一节点后
    通知：
      - 上一个阶段的处理人（知会上一阶段已完成）
      - 下一阶段的处理人（通知有新任务待处理）
    """
    # 知会上一个 assignee（可选，取消注释可开启）
    # if stage_instance.assignee and stage_instance.assignee != actor:
    #     title = f'✅ 阶段已完成：{stage_instance.node_template.name}'
    #     content = [f'您的处理阶段「{stage_instance.node_template.name}」已通过']

    # 通知下一阶段 assignee
    if next_stage_instance and next_stage_instance.assignee:
        title = f'🔄 流程待处理：{task.title}'
        content = [
            f'您有一个流程待处理',
            f'任务：「{task.title}」',
            f'当前节点：{next_stage_instance.node_template.name if next_stage_instance.node_template else ""}',
            f'由 {actor.get_full_name() if actor else actor.username} 提交',
        ]
        if next_stage_instance.node_template.timeout_hours:
            content.append(f'要求完成时间：{next_stage_instance.node_template.timeout_hours} 小时')
        _send_to_user(
            next_stage_instance.assignee, title, content,
            notification_type='task', priority='normal'
        )


def notify_flow_completed(task, completed_by):
    """
    流程完成通知
    触发时机：FlowEngine.complete_node() 流程结束时
    通知：task.reporter（任务创建人）
    """
    if task.reporter and task.reporter != completed_by:
        title = f'🎉 流程已完成：{task.title}'
        content = [
            f'任务「{task.title}」的全部流程已完成',
            f'执行人：{completed_by.get_full_name() if completed_by else completed_by.username}',
            f'完成时间：{timezone.now().strftime("%Y-%m-%d %H:%M")}',
        ]
        _send_to_user(task.reporter, title, content, notification_type='task', priority='normal')


def notify_stage_timeout(stage_instance):
    """
    阶段超时通知
    触发时机：check_task_timeouts cronjob
    通知：stage assignee + 主管
    """
    if not stage_instance.assignee:
        return

    task = stage_instance.task
    title = f'⏰ 任务阶段超时：{task.title}'
    content = [
        f'您有一个任务阶段已超时',
        f'任务：「{task.title}」',
        f'阶段：{stage_instance.node_template.name if stage_instance.node_template else ""}',
        f'要求完成时间：{stage_instance.node_template.timeout_hours} 小时',
        f'请尽快处理！',
    ]

    # 发给执行人
    _send_to_user(stage_instance.assignee, title, content, notification_type='task', priority='important')

    # TODO: 发给主管（需要知道 assignee 的上级）
    # 可以通过 UserCompanyRole 找主管，或留到 NotificationRouter 阶段实现