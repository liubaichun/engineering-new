"""
审批流自动触发服务
根据 Expense/Income 等业务对象的金额阈值，自动匹配 ApprovalTemplate 并创建 ApprovalFlow
"""

from decimal import Decimal
from .models import ApprovalFlow, ApprovalNode, ApprovalTemplate
from django.contrib.auth import get_user_model

User = get_user_model()
import logging

logger = logging.getLogger(__name__)


def find_matching_template(flow_type, amount):
    """
    根据业务类型和金额找到匹配的审批模板
    匹配规则：flow_type一致 + 金额在 min_amount~max_amount 范围内
    """
    templates = ApprovalTemplate.objects.filter(flow_type=flow_type, is_active=True).order_by('-created_at')

    for t in templates:
        conditions = t.conditions or {}
        min_amount = conditions.get('min_amount')
        max_amount = conditions.get('max_amount')

        if min_amount is not None and amount < Decimal(str(min_amount)):
            continue
        if max_amount is not None and amount > Decimal(str(max_amount)):
            continue
        return t
    return None


def resolve_approver(approver_type, approver_id, requester):
    """
    根据节点配置解析实际的审批人
    - 'admin': 找系统超级管理员
    - 'department_head': 找部门主管（找不到则 fallback 到 admin）
    - 'specific_user': approver_id 指定的用户（找不到则 fallback 到 admin）
    - 'requester_manager': 申请人的上级（无上级则 fallback 到 admin）
    """

    # 统一 fallback：任何情况找不到人都用 admin兜底
    def fallback():
        return User.objects.filter(is_superuser=True, is_active=True).first()

    if approver_type == 'admin':
        return User.objects.filter(is_superuser=True, is_active=True).first()
    elif approver_type == 'department_head':
        # 优先找非普通员工的第一个；找不到则用 admin 兜底
        head_users = User.objects.filter(is_active=True).exclude(username='admin')
        user = head_users.first()
        return user if user else fallback()
    elif approver_type == 'specific_user' and approver_id:
        try:
            return User.objects.get(id=approver_id, is_active=True)
        except User.DoesNotExist:
            return fallback()
    elif approver_type == 'requester_manager':
        return requester if requester else fallback()
    return requester if requester else fallback()


def create_approval_flow_for_expense(expense):
    """
    为 Expense 创建审批流
    自动匹配模板（按金额阈值），创建 ApprovalFlow + ApprovalNode
    """
    amount = expense.amount or Decimal('0')
    template = find_matching_template('expense', amount)
    if not template:
        logger.info(f'Expense {expense.id} 金额 {amount} 未匹配到审批模板，不创建审批流')
        return None

    nodes_config = template.nodes or []
    if not nodes_config:
        logger.warning(f'模板 {template.name} 没有节点配置')
        return None

    # 创建审批流
    flow = ApprovalFlow.objects.create(
        name=f'{expense.description or "支出审批"} - {expense.id}',
        flow_type='expense',
        status='pending',
        requester=expense.operator,
        amount=amount,
        description=f'支出申请：{expense.description or ""}，金额：{amount}元',
        related_type='expense',
        related_id=expense.id,
        current_node_order=1,
    )

    # 按节点配置创建审批节点
    for node_cfg in nodes_config:
        approver = resolve_approver(node_cfg.get('approver_type', 'admin'), node_cfg.get('approver_id'), flow.requester)
        ApprovalNode.objects.create(
            flow=flow,
            node_order=node_cfg.get('node_order', 1),
            approver=approver,
            node_type=node_cfg.get('node_type', 'approver'),
            timeout_hours=node_cfg.get('timeout_hours', 24),
            status='pending',
        )

    # 回填 Expense 的 approval_flow FK
    from apps.finance.models import Expense as ExpenseModel

    try:
        expense_obj = ExpenseModel.objects.get(id=expense.id)
        expense_obj.approval_flow = flow
        expense_obj.save(update_fields=['approval_flow'])
    except Exception as e:
        logger.error(f'回填 Expense {expense.id} approval_flow 失败: {e}')

    logger.info(f'Expense {expense.id} 创建审批流 {flow.id}，节点数 {flow.nodes.count()}')
    return flow


def create_approval_flow_for_income(income):
    """
    为 Income 创建审批流
    """
    amount = income.amount or Decimal('0')
    template = find_matching_template('income', amount)
    if not template:
        logger.info(f'Income {income.id} 金额 {amount} 未匹配到审批模板，不创建审批流')
        return None

    nodes_config = template.nodes or []
    if not nodes_config:
        return None

    flow = ApprovalFlow.objects.create(
        name=f'{income.description or "收入确认"} - {income.id}',
        flow_type='income',
        status='pending',
        requester=income.operator,
        amount=amount,
        description=f'收入确认：{income.description or ""}，金额：{amount}元',
        related_type='income',
        related_id=income.id,
        current_node_order=1,
    )

    for node_cfg in nodes_config:
        approver = resolve_approver(node_cfg.get('approver_type', 'admin'), node_cfg.get('approver_id'), flow.requester)
        ApprovalNode.objects.create(
            flow=flow,
            node_order=node_cfg.get('node_order', 1),
            approver=approver,
            node_type=node_cfg.get('node_type', 'approver'),
            timeout_hours=node_cfg.get('timeout_hours', 24),
            status='pending',
        )

    from apps.finance.models import Income as IncomeModel

    try:
        income_obj = IncomeModel.objects.get(id=income.id)
        income_obj.approval_flow = flow
        income_obj.save(update_fields=['approval_flow'])
    except Exception as e:
        logger.error(f'回填 Income {income.id} approval_flow 失败: {e}')

    return flow
