"""
通知路由 — 按事件类型分发到 channels 渠道插件
"""
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)


def dispatch_notify(event_type, context, priority='normal', title='', content_lines=None, action_url=''):
    """
    路由通知：根据事件类型查找公司对应的渠道插件，发送给相关用户。
    """
    from apps.channels.services import ChannelNotificationService
    from apps.channels.models import ChannelPlugin

    company_id = context.get('company_id')
    if not company_id:
        logger.debug('[dispatch_notify] context 中无 company_id，跳过')
        return

    # 收集公司所有已激活渠道（按 channel_type 去重）
    channels = {ch.channel_type: ch for ch in
                ChannelPlugin.objects.filter(company_id=company_id, is_active=True, is_deleted=False)}

    if not channels:
        logger.debug(f'[dispatch_notify] 公司 {company_id} 无已激活渠道，跳过')
        return

    # 确定目标用户
    target_users = _resolve_recipients('owner', context)
    if not target_users:
        logger.debug(f'[dispatch_notify] 无通知对象: event={event_type}')
        return

    for user in target_users:
        pref = _get_user_preference(user, event_type)
        if pref and not pref.is_enabled:
            logger.debug(f'[dispatch_notify] 用户 {user.username} 已禁用 {event_type}，跳过')
            continue

        if pref and pref.allowed_channels:
            channel_types_to_send = pref.allowed_channels
        else:
            channel_types_to_send = list(channels.keys())

        for ct in channel_types_to_send:
            channel = channels.get(ct)
            if not channel:
                continue
            try:
                ChannelNotificationService._send_via_channel(
                    user=user, channel=channel, title=title,
                    content='\n'.join(content_lines or []), notification_type=event_type,
                )
            except Exception as e:
                logger.warning(f'[dispatch_notify] 发送失败 user={user.username} channel={ct}: {e}')


def _resolve_recipients(scope, context):
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
    elif scope == 'all':
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


def notify_contract_created(contract):
    from apps.core.email_service import notify_approval_created
    try:
        if hasattr(contract, 'approval_flow') and contract.approval_flow:
            notify_approval_created(contract.approval_flow)
    except Exception as e:
        logger.warning(f'[notify_contract_created] 通知失败: {e}')


def notify_contract_approved(contract):
    title = '合同审批通过'
    content_lines = [
        f'合同「{contract.name}」已审批通过。',
        f'合同金额：{contract.amount}元' if hasattr(contract, 'amount') else '',
    ]
    context = {
        'notify_target': getattr(contract, 'created_by', None),
        'company_id': getattr(contract, 'company_id', None),
    }
    dispatch_notify('contract_approved', context, title=title, content_lines=content_lines)


def notify_contract_rejected(contract):
    title = '合同审批驳回'
    content_lines = [
        f'合同「{contract.name}」已被驳回。',
        f'驳回原因：{getattr(contract, "reject_reason", "未知")}',
    ]
    context = {
        'notify_target': getattr(contract, 'created_by', None),
        'company_id': getattr(contract, 'company_id', None),
    }
    dispatch_notify('contract_rejected', context, title=title, content_lines=content_lines)


def notify_project_created(project, created_by):
    title = '新项目创建'
    content_lines = [
        f'项目「{project.name}」已创建。',
        f'负责人：{getattr(project, "owner", None) or "未指定"}',
    ]
    context = {
        'notify_target': getattr(project, 'owner', None),
        'requester': created_by,
        'company_id': getattr(project, 'company_id', None),
    }
    dispatch_notify('project_created', context, title=title, content_lines=content_lines)


def notify_project_approval_result(project, approved_by, action):
    title = f'项目审批{通过 if action == approve else 驳回}'
    content_lines = [
        f'项目「{project.name}」审批{通过 if action == approve else 驳回}。',
        f'{通过 if action == approve else 驳回}人：{getattr(approved_by, "username", str(approved_by))}',
    ]
    context = {
        'notify_target': getattr(project, 'created_by', None),
        'company_id': getattr(project, 'company_id', None),
    }
    dispatch_notify('project_approval_result', context, title=title, content_lines=content_lines)


def notify_project_progress_changed(project, old_status, new_status):
    title = '项目进度更新'
    content_lines = [
        f'项目「{project.name}」进度已更新。',
        f'{old_status} → {new_status}',
    ]
    context = {
        'notify_target': getattr(project, 'owner', None),
        'company_id': getattr(project, 'company_id', None),
    }
    dispatch_notify('project_progress_changed', context, title=title, content_lines=content_lines)


def notify_equipment_action(equipment, action, operator):
    action_map = {
        'borrow': ('设备借出', '设备「{name}」已被「{operator}」借出。'),
        'return': ('设备归还', '设备「{name}」已被「{operator}」归还。'),
        'repair': ('设备报修', '设备「{name}」已提交报修申请。'),
    }
    info = action_map.get(action, (f'设备操作({action})', f'设备「{equipment.name}」发生了操作：{action}'))
    title, tmpl = info
    content_lines = [tmpl.format(name=equipment.name, operator=getattr(operator, 'username', str(operator)))]
    context = {
        'notify_target': getattr(equipment, 'keeper', None),
        'requester': operator,
        'company_id': getattr(equipment, 'company_id', None),
    }
    dispatch_notify(f'equipment_{action}', context, title=title, content_lines=content_lines)


def notify_repair_action(repair_request, action, operator):
    action_map = {
        'create': ('报修提交', '维修单「{no}」已提交，请等待分配。'),
        'assign': ('维修派工', '维修单「{no}」已分配给「{operator}」。'),
        'start': ('维修开始', '维修单「{no}」已开始维修。'),
        'complete': ('维修完成', '维修单「{no}」已完成维修，请确认。'),
        'accept': ('维修验收', '维修单「{no}」已验收通过。'),
        'reject': ('维修拒收', '维修单「{no}」已被拒收，原因：{reason}'),
    }
    info = action_map.get(action, (f'维修操作({action})', f'维修单发生了操作：{action}'))
    title, tmpl = info
    reason = getattr(repair_request, 'reject_reason', '') if action == 'reject' else ''
    content_lines = [tmpl.format(
        no=getattr(repair_request, 'request_no', repair_request.id),
        operator=getattr(operator, 'username', str(operator)),
        reason=reason,
    )]
    context = {
        'notify_target': getattr(repair_request, 'requester', None),
        'requester': operator,
        'company_id': getattr(repair_request, 'company_id', None),
    }
    dispatch_notify(f'repair_{action}', context, title=title, content_lines=content_lines)


def notify_task_created(task, created_by=None):
    title = '新任务创建'
    content_lines = [
        f'任务「{task.name}」已创建。',
        f'负责人：{getattr(task, "assignee", None) or "未分配"}',
    ]
    context = {
        'notify_target': getattr(task, 'assignee', None),
        'requester': created_by,
        'company_id': getattr(task, 'company_id', None),
    }
    dispatch_notify('task_created', context, title=title, content_lines=content_lines)


def notify_task_started(task, started_by):
    title = '任务开始'
    content_lines = [f'任务「{task.name}」已开始执行。']
    context = {
        'notify_target': getattr(task, 'creator', None),
        'requester': started_by,
        'company_id': getattr(task, 'company_id', None),
    }
    dispatch_notify('task_started', context, title=title, content_lines=content_lines)


def notify_task_completed(task, completed_by):
    title = '任务完成'
    content_lines = [f'任务「{task.name}」已完成。']
    context = {
        'notify_target': getattr(task, 'creator', None),
        'requester': completed_by,
        'company_id': getattr(task, 'company_id', None),
    }
    dispatch_notify('task_completed', context, title=title, content_lines=content_lines)


def notify_flow_started(task, stage_instance, started_by):
    title = '流程启动'
    content_lines = [
        f'流程「{getattr(task, "name", task)}」已启动。',
        f'当前阶段：{getattr(stage_instance, "name", "未知")}',
    ]
    context = {
        'notify_target': getattr(stage_instance, 'owner', None),
        'requester': started_by,
        'company_id': getattr(task, 'company_id', None),
    }
    dispatch_notify('flow_started', context, title=title, content_lines=content_lines)


def notify_stage_completed(task, stage_instance, next_stage_instance, action, actor):
    title = '阶段完成'
    current = getattr(stage_instance, 'name', '未知')
    next_name = getattr(next_stage_instance, 'name', '结束') if next_stage_instance else '结束'
    content_lines = [
        f'任务「{getattr(task, "name", task)}」阶段「{current}」已完成。',
        f'下一阶段：{next_name}',
    ]
    context = {
        'notify_target': getattr(next_stage_instance, 'owner', None) if next_stage_instance else None,
        'requester': actor,
        'company_id': getattr(task, 'company_id', None),
    }
    dispatch_notify('stage_completed', context, title=title, content_lines=content_lines)


def notify_flow_completed(task, completed_by):
    title = '流程完成'
    content_lines = [f'流程「{getattr(task, "name", task)}」已全部完成。']
    context = {
        'notify_target': getattr(task, 'creator', None),
        'requester': completed_by,
        'company_id': getattr(task, 'company_id', None),
    }
    dispatch_notify('flow_completed', context, title=title, content_lines=content_lines)


def notify_stage_timeout(stage_instance):
    title = '⚠️ 阶段超时预警'
    content_lines = [
        f'阶段「{getattr(stage_instance, "name", "未知")}」已超时。',
        f'请尽快处理。',
    ]
    context = {
        'notify_target': getattr(stage_instance, 'owner', None),
        'company_id': getattr(stage_instance, 'company_id', None),
    }
    dispatch_notify('stage_timeout', context, title=title, content_lines=content_lines, priority='critical')
