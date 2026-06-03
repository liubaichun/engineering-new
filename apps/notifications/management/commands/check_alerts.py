"""
智能预警定时任务 — 每小时执行一次

用法：
    python manage.py check_alerts

Crontab 配置（每小时第0分）：
    0 * * * * cd /root/engineering-new && venv/bin/python manage.py check_alerts >> logs/alerts.log 2>&1

7 种预警类型：
    1. 任务超时      — Task.due_date < now 且 status ∉ (completed/cancelled)
    2. 审批超时      — ApprovalNode.status=pending 且超过 48 小时未处理
    3. 审批积压      — ApprovalNode.status=pending 且 count > 5（每人）
    4. 合同到期      — Contract.expire_date - 30days <= now <= expire_date 且 status=active
    5. 大额支出      — Expense.amount > 50000 且今日未通知过
    6. 项目状态提醒  — Project.status=active 且 end_date 已过（未结项）
    7. 工资待发放    — WageRecord.status=approved 且超过 7 天未 paid
"""

import logging
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.db.models import Count
from django.utils import timezone as dj_timezone
from django.contrib.auth import get_user_model

from apps.core.models import Notification, SystemSetting
from apps.tasks.models import Project, Task
from apps.approvals.models import ApprovalNode
from apps.crm.models import Contract
from apps.finance.models import Expense, WageRecord

User = get_user_model()
logger = logging.getLogger('check_alerts')


def already_notified(user, n_type, related_id, hours=24):
    """检测是否在最近 hours 小时内发过同类通知，避免重复轰炸"""
    cutoff = dj_timezone.now() - timedelta(hours=hours)
    return Notification.objects.filter(
        user=user, notification_type=n_type, related_id=related_id, created_at__gte=cutoff
    ).exists()


def notify(user, title, content, n_type, level='warning', related_id=None, related_type=''):
    """发送通知：写入数据库 + 外部渠道同步推送"""
    if related_id and already_notified(user, n_type, related_id, hours=24):
        return
    Notification.objects.create(
        user=user,
        title=title,
        content=content,
        notification_type=n_type,
        level=level,
        related_id=related_id,
        related_type=related_type,
    )
    logger.info(f'[通知] {user.username} <- {title}')

    # 同步发外部渠道（飞书/企微等），静默失败不影响主流程
    try:
        from apps.core.email_service import notify_user as ext_notify

        content_lines = [content] if isinstance(content, str) else content
        priority = 'important' if level in ('critical', 'error') else 'normal'
        ext_notify(user, title, content_lines, priority=priority)
    except Exception as e:
        logger.warning(f'[notify] 外部渠道通知失败 for {user.username}: {e}')


class Command(BaseCommand):
    help = '检测7种智能预警并发送通知'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='仅打印，不实际发送通知')

    def handle(self, *args, **options):
        dry = options['dry_run']
        self.stdout.write(f'[{datetime.now()}] 开始预警检测 (dry={dry})')

        if dry:
            self.stdout.write(self.style.WARNING('  DRY RUN — 不发送通知'))

        count = 0

        # ── 1. 任务超时预警 ──────────────────────────────────────────────────
        # Task.due_date 已过但仍未完成
        overdue_tasks = Task.objects.filter(
            due_date__lt=datetime.now().date(), status__in=['pending', 'in_progress', 'draft']
        ).select_related('project')

        for task in overdue_tasks:
            assignee = task.assignee
            if not assignee:
                continue
            if already_notified(assignee, 'task', task.id, hours=24):
                continue
            title = '任务超时提醒'
            content = f'您负责的任务「{task.title}」已超过截止日期 {task.due_date.strftime("%Y-%m-%d")}，请尽快处理。'
            if not dry:
                notify(assignee, title, content, 'task', 'warning', task.id, 'task')
            count += 1
            self.stdout.write(f'  [逾期任务] {task.title} -> {assignee.username}')

        # ── 2. 审批超时预警 + 超时升级 ─────────────────────────────────────────
        # 读取系统设置
        try:
            timeout_hours = int(SystemSetting.objects.get(key='approval_timeout_hours').value)
        except (SystemSetting.DoesNotExist, ValueError):
            timeout_hours = 48
        try:
            escalate_enabled = SystemSetting.objects.get(key='approval_escalate_enabled').value == 'true'
        except SystemSetting.DoesNotExist:
            escalate_enabled = True

        cutoff = dj_timezone.now() - timedelta(hours=timeout_hours)
        stale_steps = ApprovalNode.objects.filter(status='pending', assigned_at__lt=cutoff).select_related(
            'flow', 'approver'
        )

        for step in stale_steps:
            if not step.approver:
                continue
            hours_waiting = int((dj_timezone.now() - step.assigned_at).total_seconds() // 3600)
            flow_title = step.flow.name if step.flow else f'审批节点-{step.node_order}'

            # 发超时通知（每12小时一次）
            if not already_notified(step.approver, 'approval', step.id, hours=12):
                title = '审批超时提醒'
                content = f'您有一笔待审批「{flow_title}」已等待 {hours_waiting} 小时，请及时处理。'
                if not dry:
                    notify(step.approver, title, content, 'approval', 'warning', step.id, 'approval_step')
                count += 1
                self.stdout.write(f'  [审批超时] {flow_title} -> {step.approver.username}')

            # 超时升级：把节点指派给更高层级的人
            if escalate_enabled and not step.escalated_at:
                # 升级规则：找当前节点审批人的上级（is_staff 但不是当前审批人的）
                current_approver = step.approver
                # 找 is_staff 的其他人
                higher_approver = User.objects.filter(is_staff=True).exclude(id=current_approver.id).first()
                if not higher_approver:
                    higher_approver = User.objects.filter(is_superuser=True).exclude(id=current_approver.id).first()
                if higher_approver:
                    old_approver = step.approver
                    step.approver = higher_approver
                    step.assigned_at = dj_timezone.now()
                    step.escalated_at = dj_timezone.now()
                    step.comment = (step.comment or '') + f' [系统升级，来自{old_approver.username}]'
                    step.save(update_fields=['approver', 'assigned_at', 'escalated_at', 'comment'])
                    title = '审批已升级'
                    content = f'您有一笔待审批「{flow_title}」原审批人 {old_approver.username} 已超时 {hours_waiting} 小时，现已升级给您处理。'
                    if not dry:
                        notify(higher_approver, title, content, 'approval', 'warning', step.id, 'approval_step')
                    count += 1
                    self.stdout.write(
                        f'  [审批升级] {flow_title}: {old_approver.username} -> {higher_approver.username}'
                    )

        # ── 3. 审批积压预警 ─────────────────────────────────────────────────
        # 同一人待审批 > 5 笔，每12小时通知一次（用 Notification.created_at 本身做去重）
        approver_counts = (
            ApprovalNode.objects.filter(status='pending')
            .values('approver')
            .annotate(pending_count=Count('id'))
            .filter(pending_count__gt=5)
        )

        for row in approver_counts:
            approver = User.objects.filter(id=row['approver']).first()
            if not approver:
                continue
            # 审批积压去重：12小时内同类型通知已存在则跳过
            if Notification.objects.filter(
                user=approver,
                notification_type='approval',
                title__contains='审批积压',
                created_at__gte=dj_timezone.now() - timedelta(hours=12),
            ).exists():
                continue
            title = '审批积压提醒'
            content = f'您当前有 {row["pending_count"]} 笔待审批事项，建议及时处理以避免延误。'
            if not dry:
                notify(approver, title, content, 'approval', 'warning', None, 'approval_backlog')
            count += 1
            self.stdout.write(f'  [审批积压] {approver.username}: {row["pending_count"]} 笔')

        # ── 4. 合同到期预警 ─────────────────────────────────────────────────
        # Contract.expire_date 在 30 天内即将到期，或已到期但仍 active
        today = datetime.now().date()
        deadline = today + timedelta(days=30)

        expiring_contracts = (
            Contract.objects.filter(status='active', expire_date__lte=deadline)
            .exclude(
                expire_date__lt=today  # 已过期的不再提醒（30天内已提醒过）
            )
            .select_related('project', 'client', 'created_by')
        )

        for contract in expiring_contracts:
            # 通知项目负责人
            if contract.project and contract.project.owner:
                owner = contract.project.owner
                if not already_notified(owner, 'project', contract.id, hours=72):
                    days_left = (contract.expire_date - today).days
                    title = '合同到期预警'
                    content = f'合同「{contract.name}」（客户：{contract.client.name if contract.client else "无"}）将于 {contract.expire_date.strftime("%Y-%m-%d")} 到期（还剩{days_left}天），请提前做好续签或归档准备。'
                    if not dry:
                        notify(owner, title, content, 'project', 'warning', contract.id, 'contract')
                    count += 1
                    self.stdout.write(f'  [合同到期] {contract.name} -> {owner.username}')
            # 通知合同创建者
            if contract.created_by:
                creator = contract.created_by
                # 项目负责人和创建者可能是同一人，只通知一次（上面已处理重复通知）
                if not contract.project or not contract.project.owner or contract.project.owner != creator:
                    if not already_notified(creator, 'project', contract.id, hours=72):
                        days_left = (contract.expire_date - today).days
                        title = '合同到期预警'
                        content = f'合同「{contract.name}」（客户：{contract.client.name if contract.client else "无"}）将于 {contract.expire_date.strftime("%Y-%m-%d")} 到期（还剩{days_left}天），请提前做好续签或归档准备。'
                        if not dry:
                            notify(creator, title, content, 'project', 'warning', contract.id, 'contract')
                        count += 1
                        self.stdout.write(f'  [合同到期] {contract.name} -> {creator.username}')

        # ── 5. 大额支出预警 ─────────────────────────────────────────────────
        # 今日新支出 > 50000
        today = datetime.now().date()
        deadline = today + timedelta(days=30)

        large_expenses = Expense.objects.filter(amount__gt=50000, date=today).select_related('company')

        for expense in large_expenses:
            for admin in User.objects.filter(is_superuser=True):
                if not already_notified(admin, 'finance', expense.id, hours=24):
                    co_name = expense.company.name if expense.company else '未知公司'
                    title = '大额支出提醒'
                    content = f'今日有一笔大额支出：{co_name} {float(expense.amount):,.2f} 元，请关注。'
                    if not dry:
                        notify(admin, title, content, 'finance', 'warning', expense.id, 'expense')
                    count += 1
                    self.stdout.write(f'  [大额支出] {expense.amount} -> {admin.username}')

        # ── 6. 项目超期未结项提醒 ───────────────────────────────────────────
        # Project.status=active 但 end_date 已过（项目已超期但未归档/完成）
        overdue_projects = Project.objects.filter(status='active', end_date__lt=today)

        for project in overdue_projects:
            if project.owner:
                owner = project.owner
                if not already_notified(owner, 'project', project.id, hours=168):
                    title = '项目超期提醒'
                    content = f'项目「{project.name}」（{project.code}）已超过计划结束日期 {project.end_date.strftime("%Y-%m-%d")}，当前状态仍为进行中，请确认项目进展并及时归档或调整计划。'
                    if not dry:
                        notify(owner, title, content, 'project', 'warning', project.id, 'project')
                    count += 1
                    self.stdout.write(f'  [项目超期] {project.name} -> {owner.username}')

        # ── 7. 工资待发放预警 ───────────────────────────────────────────────
        # WageRecord.status=approved 超过 7 天未标记为 paid
        stale_wages = WageRecord.objects.filter(
            status='approved', updated_at__lt=dj_timezone.now() - timedelta(days=7)
        ).select_related('company')

        for wage in stale_wages:
            for admin in User.objects.filter(is_superuser=True):
                if not already_notified(admin, 'wage', wage.id, hours=72):
                    co_name = wage.company.name if wage.company else '未知公司'
                    title = '工资待发放提醒'
                    content = f'{co_name} {wage.year}年{wage.month}月工资单（{wage.employee_name}）已审批通过超过7天，请及时发放。'
                    if not dry:
                        notify(admin, title, content, 'wage', 'warning', wage.id, 'wage_record')
                    count += 1
                    self.stdout.write(f'  [工资待发] {co_name} {wage.year}-{wage.month} -> {admin.username}')

        # ── 8. 应收应付到期提醒 ───────────────────────────────────────────
        # Invoice.due_date 在 7 天内到期或已到期但未支付
        from apps.finance.models import Invoice

        today = datetime.now().date()
        near_deadline = today + timedelta(days=7)

        # 即将到期的应收/应付
        due_soon_invoices = Invoice.objects.filter(
            due_date__gte=today, due_date__lte=near_deadline, status='pending'
        ).select_related('company', 'contract')

        for inv in due_soon_invoices:
            days_left = (inv.due_date - today).days
            direction = '应收' if inv.type == 'income' else '应付'
            contract_info = f'（合同：{inv.contract.contract_no} {inv.contract.name}）' if inv.contract_id else ''
            title = f'{direction}发票到期提醒'
            content = (
                f'发票 {inv.invoice_no} 将于 {inv.due_date.strftime("%Y-%m-%d")} 到期（还剩{days_left}天），'
                f'对方：{inv.counterparty}，金额：{float(inv.amount):,.2f} 元{contract_info}'
            )
            for admin in User.objects.filter(is_superuser=True):
                if not already_notified(admin, 'invoice', inv.id, hours=24):
                    if not dry:
                        notify(admin, title, content, 'invoice', 'warning', inv.id, 'invoice')
                    count += 1
                    self.stdout.write(f'  [发票到期] {inv.invoice_no} -> {admin.username}')

        # 已逾期的应收/应付
        overdue_invoices = Invoice.objects.filter(due_date__lt=today, status='pending').select_related(
            'company', 'contract'
        )

        for inv in overdue_invoices:
            days_overdue = (today - inv.due_date).days
            direction = '应收' if inv.type == 'income' else '应付'
            contract_info = f'（合同：{inv.contract.contract_no} {inv.contract.name}）' if inv.contract_id else ''
            title = f'{direction}发票逾期提醒'
            level = 'critical' if days_overdue > 30 else 'error'
            content = (
                f'发票 {inv.invoice_no} 已逾期 {days_overdue} 天，'
                f'对方：{inv.counterparty}，金额：{float(inv.amount):,.2f} 元{contract_info}'
            )
            for admin in User.objects.filter(is_superuser=True):
                if not already_notified(admin, 'invoice', inv.id, hours=72):
                    if not dry:
                        notify(admin, title, content, 'invoice', level, inv.id, 'invoice')
                    count += 1
                    self.stdout.write(f'  [发票逾期] {inv.invoice_no} -> {admin.username}')

        self.stdout.write(self.style.SUCCESS(f'[{datetime.now()}] 预警检测完成，共发送 {count} 条通知'))
