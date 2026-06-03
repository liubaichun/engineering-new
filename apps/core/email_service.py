"""
通知服务 — 审批流关键节点自动发送通知（多渠道：邮件 + 飞书/企微/钉钉/Webhook）
1. 审批人收到新审批请求
2. 申请人收到审批结果（通过/拒绝）
3. 审批超时催办提醒
4. 驳回重审通知
"""

from django.conf import settings
from django.core.mail import send_mail
from django.utils.html import strip_tags
import logging

logger = logging.getLogger(__name__)


def _can_send_mail():
    """检查是否配置了邮件发送"""
    if settings.DEBUG and 'console' in settings.EMAIL_BACKEND:
        return True
    if not settings.DEBUG and settings.EMAIL_HOST_USER and settings.EMAIL_HOST_PASSWORD:
        return True
    return False


def _get_system_url():
    """获取系统访问地址"""
    hosts = settings.ALLOWED_HOSTS
    if '43.156.139.37' in hosts:
        return 'http://43.156.139.37:8001'
    if hosts and hosts[0] != '*':
        return f'http://{hosts[0]}:8001'
    return 'http://localhost:8001'


def _build_html_content(subject, content_lines, action_url=None, action_text='查看详情'):
    """构建 HTML 邮件内容"""
    action_block = ''
    if action_url and action_text:
        action_block = f'''
        <tr>
            <td style="padding: 20px 0;">
                <a href="{action_url}" style="display:inline-block;background:#2563eb;color:#ffffff;text-decoration:none;padding:12px 24px;border-radius:6px;font-weight:bold;">
                    {action_text}
                </a>
            </td>
        </tr>
        '''
    rows = ''.join(
        f'<tr><td style="padding:8px 0;border-bottom:1px solid #f0f0f0;color:#374151;font-size:15px;">{line}</td></tr>'
        for line in content_lines
    )
    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f5f7fa;font-family:Arial,sans-serif;">
    <div style="max-width:600px;margin:40px auto;background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
        <div style="background:#2563eb;padding:24px 32px;">
            <h1 style="margin:0;color:#ffffff;font-size:20px;font-weight:bold;">{subject}</h1>
        </div>
        <div style="padding:24px 32px;">
            <table style="width:100%;border-collapse:collapse;">
                {rows}
                {action_block}
            </table>
        </div>
        <div style="background:#f9fafb;padding:16px 32px;text-align:center;color:#9ca3af;font-size:12px;">
            本邮件由企业信息化管理系统自动发送 · 请勿直接回复
        </div>
    </div>
</body>
</html>
"""


def _get_user_email(user):
    """获取用户邮箱"""
    if not user:
        return None
    return getattr(user, 'email', None) or None


def _send_email_to_user(user, subject, content_lines, action_url=None, action_text='查看详情'):
    """发送邮件通知（内部函数）"""
    if not _can_send_mail():
        logger.debug(f'[Email] Mock send to {user}: {subject}')
        return False
    email = _get_user_email(user)
    if not email:
        logger.debug(f'[Email] No email for user {user}')
        return False
    try:
        html = _build_html_content(subject, content_lines, action_url, action_text)
        send_mail(
            subject=subject,
            message=strip_tags(html),
            html_message=html,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
        logger.info(f'[Email] Sent to {email}: {subject}')
        return True
    except Exception as e:
        logger.error(f'[Email] Failed to send to {email}: {e}')
        return False


def _send_to_binding_channel(binding, subject, content_str):
    """通过用户的通知绑定渠道发送消息（统一走 channels 新框架）"""
    try:
        from apps.channels.services import send_notification

        # 从 channel 关联的 company 获取公司ID
        company_id = binding.channel.company_id
        if not company_id:
            company_id = getattr(binding.user, 'current_company_id', None)

        result = send_notification(
            company_id=company_id,
            title=subject,
            content=content_str,
            user_ids=[binding.user_id],
            notification_type='approval',
        )
        if result.get('sent', 0) > 0:
            logger.info(f'[Notify] 通过 {binding.channel.channel_type} 发送给 {binding.user.username}')
        else:
            logger.warning(f'[Notify] 发送失败: {result.get("details", "未知原因")}')
        return result.get('sent', 0) > 0
    except Exception as e:
        logger.warning(f'[Notify] 异常: binding={binding.id}, {e}')
        return False


def notify_user(user, subject, content_lines, action_url=None, action_text='查看详情', priority='normal'):
    """
    向用户发送多渠道通知（邮件 + 所有已绑定通知渠道）
    priority: 'important' 强制发送所有渠道，'normal' 仅发送用户设置"接收全部"的渠道
    """
    if not user:
        return

    # 1. 邮件（始终尝试）
    _send_email_to_user(user, subject, content_lines, action_url, action_text)

    # 2. 通知渠道（走新的 channels 框架，按绑定偏好发送）
    try:
        from apps.channels.models import ChannelBinding

        bindings = ChannelBinding.objects.filter(
            user=user,
            is_active=True,
            channel__is_active=True,
            status='active',
        ).select_related('channel')

        if not bindings:
            return

        # 将 content_lines 转为纯文本
        content_str = '\n'.join(
            line.replace('<strong>', '').replace('</strong>', '').replace('<br>', '\n').replace('<br/>', '\n')
            for line in content_lines
        )

        # 优先级：'important' 强制发所有渠道，'normal' 按用户偏好（暂不检查receive_all，后续通过迁移数据补齐）
        for binding in bindings:
            _send_to_binding_channel(binding, subject, content_str)
    except Exception as e:
        logger.warning(f'[Notify] Failed to dispatch channel notifications for user {user}: {e}')


# ─── 审批流通知 ───


def notify_approval_created(flow):
    """
    通知审批人：有新的审批请求
    flow: ApprovalFlow 实例
    """
    if not flow or not flow.requester:
        return
    system_url = _get_system_url()
    approver_list = [
        node.approver for node in flow.approvalnode_set.all() if node.approver and node.status == 'pending'
    ]
    if not approver_list:
        from django.contrib.auth import get_user_model

        User = get_user_model()
        approver_list = list(User.objects.filter(is_staff=True).exclude(id=flow.requester_id)[:5])

    content = [
        f'<strong>{flow.requester.username}</strong> 提交了一个审批请求',
        f'审批名称：{flow.name}',
        f'类型：{flow.get_flow_type_display()}',
        f'金额：{"¥" + str(flow.amount) if flow.amount else "无"}',
        f'说明：{flow.description[:100] if flow.description else "无"}',
    ]
    action_url = f'{system_url}/approvals/'
    subject = f'【待审批】{flow.name}'
    for approver in approver_list:
        notify_user(approver, subject, content, action_url, '前往审批', priority='important')


def notify_transfer(flow, original_approver, new_approver, comment):
    """
    通知审批转交
    flow: ApprovalFlow 实例
    original_approver: 原审批人（转出人）
    new_approver: 新审批人（接收人）
    """
    system_url = _get_system_url()
    # 通知新审批人
    content_new = [
        f'<strong>{original_approver.username}</strong> 将一笔审批转交给您',
        f'审批名称：{flow.name}',
        f'类型：{flow.get_flow_type_display()}',
        f'金额：{"¥" + str(flow.amount) if flow.amount else "无"}',
        f'转交说明：{comment or "无"}',
    ]
    action_url = f'{system_url}/approvals/'
    subject = f'【待审批】{flow.name}（有人转交给您）'
    notify_user(new_approver, subject, content_new, action_url, '前往审批', priority='normal')

    # 通知原审批人（知会）
    content_old = [
        f'您已将审批「{flow.name}」转交给 <strong>{new_approver.username}</strong>',
        f'转交说明：{comment or "无"}',
    ]
    subject_old = f'【知会】您转交的审批「{flow.name}」已被接收'
    notify_user(original_approver, subject_old, content_old, priority='normal')


def notify_delegate(flow, original_approver, delegate_user, comment):
    """
    通知审批委托
    flow: ApprovalFlow 实例
    original_approver: 原审批人（委托人）
    delegate_user: 被委托人
    """
    system_url = _get_system_url()
    # 通知被委托人
    content_new = [
        f'<strong>{original_approver.username}</strong> 委托您审批',
        f'审批名称：{flow.name}',
        f'类型：{flow.get_flow_type_display()}',
        f'金额：{"¥" + str(flow.amount) if flow.amount else "无"}',
        f'委托说明：{comment or "无"}',
    ]
    action_url = f'{system_url}/approvals/'
    subject = f'【待审批】{flow.name}（受托审批）'
    notify_user(delegate_user, subject, content_new, action_url, '前往审批', priority='normal')

    # 通知原审批人（知会，可撤回）
    content_old = [
        f'您已将审批「{flow.name}」委托给 <strong>{delegate_user.username}</strong>',
        f'委托说明：{comment or "无"}',
        '注意：您仍可撤回委托',
    ]
    subject_old = f'【知会】您委托的审批「{flow.name}」已被接收'
    notify_user(original_approver, subject_old, content_old, priority='normal')


def notify_approval_result(flow, approved_by, action):
    """
    通知申请人：审批结果
    flow: ApprovalFlow 实例
    approved_by: 审批人 User
    action: 'approved' | 'rejected' | 'cancelled'
    """
    if not flow or not flow.requester:
        return
    system_url = _get_system_url()
    action_text_map = {
        'approved': '已批准 ✓',
        'rejected': '已拒绝 ✗',
        'cancelled': '已取消',
    }
    action_text = action_text_map.get(action, action)
    content = [
        f'您的审批请求 <strong>{flow.name}</strong> 已被 {approved_by.username} {action_text}',
        f'类型：{flow.get_flow_type_display()}',
        f'金额：{"¥" + str(flow.amount) if flow.amount else "无"}',
    ]
    if flow.result_comment:
        content.append(f'审批意见：{flow.result_comment}')
    subject = f'【审批结果】{flow.name} - {action_text}'
    action_url = f'{system_url}/approvals/'
    notify_user(flow.requester, subject, content, action_url, '查看详情', priority='important')


def notify_rejected_to_requester(flow, rejected_by, comment):
    """
    通知申请人：被驳回重审
    flow: ApprovalFlow 实例
    rejected_by: 驳回人 User
    comment: 驳回原因
    """
    if not flow or not flow.requester:
        return
    system_url = _get_system_url()
    content = [
        f'您的审批请求 <strong>{flow.name}</strong> 被 {rejected_by.username} 驳回重审',
        f'类型：{flow.get_flow_type_display()}',
        f'金额：{"¥" + str(flow.amount) if flow.amount else "无"}',
        f'驳回原因：{comment or "未填写"}',
        '请修改后重新提交',
    ]
    subject = f'【需修改】{flow.name} - 已被驳回'
    action_url = f'{system_url}/approvals/'
    notify_user(flow.requester, subject, content, action_url, '修改并重新提交', priority='important')


def notify_urged(flow, urged_by):
    """
    通知审批人：被催办了
    flow: ApprovalFlow 实例
    urged_by: 催办人（申请人）User
    """
    pending_nodes = [node for node in flow.approvalnode_set.all() if node.status == 'pending' and node.approver]
    system_url = _get_system_url()
    for node in pending_nodes:
        content = [
            f'【催办提醒】{flow.requester.username} 正在催促您审批',
            f'审批名称：{flow.name}',
            f'类型：{flow.get_flow_type_display()}',
            f'金额：{"¥" + str(flow.amount) if flow.amount else "无"}',
            f'说明：{flow.description[:100] if flow.description else "无"}',
            '请尽快处理，避免延误',
        ]
        subject = f'【催办】{flow.name} - 请尽快审批'
        action_url = f'{system_url}/approvals/'
        notify_user(node.approver, subject, content, action_url, '立即审批', priority='important')


def notify_approval_timeout(flow, node):
    """
    通知审批人：审批超时
    """
    if not node.approver:
        return
    system_url = _get_system_url()
    content = [
        '【超时提醒】您有一笔审批已超时未处理',
        f'审批名称：{flow.name}',
        f'类型：{flow.get_flow_type_display()}',
        f'金额：{"¥" + str(flow.amount) if flow.amount else "无"}',
        f'节点：{node.node_type}',
        '请立即处理或转交他人',
    ]
    subject = f'【超时】{flow.name}'
    action_url = f'{system_url}/approvals/'
    notify_user(node.approver, subject, content, action_url, '立即处理', priority='important')
