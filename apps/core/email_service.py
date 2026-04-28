"""
邮件通知服务
在审批流关键节点自动发送邮件通知：
1. 审批人收到新审批请求
2. 申请人收到审批结果（通过/拒绝）
3. 审批超时催办提醒
4. 驳回重审通知
"""
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
import logging

logger = logging.getLogger(__name__)


def _can_send_mail():
    """检查是否配置了邮件发送"""
    if settings.DEBUG and 'console' in settings.EMAIL_BACKEND:
        return True  # DEBUG + console 后端，开发调试用
    if not settings.DEBUG and settings.EMAIL_HOST_USER and settings.EMAIL_HOST_PASSWORD:
        return True  # 生产环境有真实 SMTP
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
    rows = ''.join(f'<tr><td style="padding:8px 0;border-bottom:1px solid #f0f0f0;color:#374151;font-size:15px;">{line}</td></tr>' for line in content_lines)
    return f'''
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
'''


def _get_user_email(user):
    """获取用户邮箱"""
    if not user:
        return None
    email = getattr(user, 'email', None)
    if email:
        return email
    # 尝试从 related_name 找
    return None


def _send_to_user(user, subject, content_lines, action_url=None, action_text='查看详情'):
    """向指定用户发送邮件"""
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


# ─── 审批流通知 ───

def notify_approval_created(flow):
    """
    通知审批人：有新的审批请求
    flow: ApprovalFlow 实例
    """
    if not flow or not flow.requester:
        return
    system_url = _get_system_url()
    approver_list = [node.approver for node in flow.approvalnode_set.all() if node.approver and node.status == 'pending']
    if not approver_list:
        # 没有明确审批人时通知所有 staff
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
        _send_to_user(approver, subject, content, action_url, '前往审批')


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
    action_text = {
        'approved': '已批准 ✓',
        'rejected': '已拒绝 ✗',
        'cancelled': '已取消',
    }.get(action, action)
    content = [
        f'您的审批请求 <strong>{flow.name}</strong> 已被 {approved_by.username} {action_text}',
        f'类型：{flow.get_flow_type_display()}',
        f'金额：{"¥" + str(flow.amount) if flow.amount else "无"}',
    ]
    if flow.result_comment:
        content.append(f'审批意见：{flow.result_comment}')
    subject = f'【审批结果】{flow.name} - {action_text}'
    action_url = f'{system_url}/approvals/'
    _send_to_user(flow.requester, subject, content, action_url, '查看详情')


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
    _send_to_user(flow.requester, subject, content, action_url, '修改并重新提交')


def notify_urged(flow, urged_by):
    """
    通知审批人：被催办了
    flow: ApprovalFlow 实例
    urged_by: 催办人（申请人）User
    """
    pending_nodes = [node for node in flow.approvalnode_set.all() if node.status == 'pending']
    for node in pending_nodes:
        if not node.approver:
            continue
        system_url = _get_system_url()
        content = [
            f'【催办提醒】{flow.requester.username} 正在催促您审批',
            f'审批名称：{flow.name}',
            f'类型：{flow.get_flow_type_display()}',
            f'金额：{"¥" + str(flow.amount) if flow.amount else "无"}',
            f'说明：{flow.description[:100] if flow.description else "无"}',
            f'请尽快处理，避免延误',
        ]
        subject = f'【催办】{flow.name} - 请尽快审批'
        action_url = f'{system_url}/approvals/'
        _send_to_user(node.approver, subject, content, action_url, '立即审批')


def notify_approval_timeout(flow, node):
    """
    通知审批人：审批超时
    """
    if not node.approver:
        return
    system_url = _get_system_url()
    content = [
        f'【超时提醒】您有一笔审批已超时未处理',
        f'审批名称：{flow.name}',
        f'类型：{flow.get_flow_type_display()}',
        f'金额：{"¥" + str(flow.amount) if flow.amount else "无"}',
        f'节点：{node.node_type}',
        f'请立即处理或转交他人',
    ]
    subject = f'【超时】{flow.name}'
    action_url = f'{system_url}/approvals/'
    _send_to_user(node.approver, subject, content, action_url, '立即处理')
