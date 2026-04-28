"""
智能审批流构建器 - 按金额自动路由 + 超时升级

用法：
    from apps.approvals.flow_builder import build_approval_flow
    flow = build_approval_flow(
        flow_type='expense',   # expense / income / wage
        amount=25000,
        name='支出-采购设备',
        requester=user,
        description='...',
        related_id=123,
    )
"""
from decimal import Decimal
from django.contrib.auth import get_user_model
from .models import ApprovalFlow, ApprovalNode, ApprovalTemplate
from apps.core.models import SystemSetting

User = get_user_model()


def get_setting(key, default='false'):
    """读取系统设置"""
    try:
        return SystemSetting.objects.get(key=key).value
    except SystemSetting.DoesNotExist:
        return default


def is_auto_approval_enabled():
    return get_setting('approval_auto_enabled', 'true') == 'true'


def is_multi_level_enabled():
    return get_setting('multi_level_approval_enabled', 'true') == 'true'


def find_best_template(flow_type, amount):
    """
    找最匹配的审批模板。
    规则：conditions.min_amount <= amount < conditions.max_amount（max=None 表示无上限）
    多层匹配时取 min_amount 最大的（最精确匹配）。
    """
    amount = Decimal(str(amount)) if amount else Decimal('0')

    candidates = ApprovalTemplate.objects.filter(
        flow_type=flow_type,
        is_active=True,
    ).filter(
        conditions__min_amount__lte=float(amount)
    ).order_by('-conditions__min_amount')

    for tpl in candidates:
        min_amt = tpl.conditions.get('min_amount', 0) or 0
        max_amt = tpl.conditions.get('max_amount')
        if max_amt is None or float(amount) < float(max_amt):
            return tpl
    return None


def resolve_approver(approver_type, approver_id, company=None):
    """
    将 approver_type 解析为实际审批用户。
    类型：
      - specific_user : 直接用 approver_id
      - admin         : 公司管理员
      - department_head : 部门负责人
      - manager       : 总经理
      - board         : 董事会成员（is_superuser）
      - requester_head : 申请人的上级
    """
    if approver_type == 'specific_user' and approver_id:
        return User.objects.filter(id=approver_id).first()

    if approver_type == 'board':
        return User.objects.filter(is_superuser=True).first()

    if approver_type == 'manager':
        return User.objects.filter(is_staff=True, is_superuser=False).first()

    # admin / department_head / requester_head → 找公司管理员或第一个 staff
    admin = User.objects.filter(is_staff=True).first()
    if not admin:
        admin = User.objects.filter(is_superuser=True).first()
    return admin


def build_approval_flow(flow_type, amount, name, requester=None,
                         description='', related_id=None, company=None):
    """
    构建审批流：
      1. 若智能审批关闭 → 返回 None（不创建审批流，业务直接放行）
      2. 若多级审批关闭 → 创建单节点审批流
      3. 否则 → 按金额匹配模板，创建完整多级节点链
    """
    if not is_auto_approval_enabled():
        return None  # 智能审批关闭，不触发审批流

    amount = Decimal(str(amount)) if amount else Decimal('0')

    # 不需要审批的金额下限
    min_threshold_map = {'expense': 0, 'income': 5000, 'wage': 0}
    if float(amount) < min_threshold_map.get(flow_type, 0):
        return None  # 金额过小，跳过审批

    # 创建审批流主记录
    flow = ApprovalFlow.objects.create(
        name=name,
        flow_type=flow_type,
        status='pending',
        requester=requester,
        amount=amount,
        description=description,
        related_id=related_id or 0,
    )

    use_multi_level = is_multi_level_enabled()
    template = find_best_template(flow_type, amount) if use_multi_level else None

    if template and template.nodes:
        # 模板驱动：按模板配置创建节点
        nodes_created = 0
        for node_cfg in template.nodes:
            approver = resolve_approver(
                node_cfg.get('approver_type'),
                node_cfg.get('approver_id'),
                company,
            )
            if not approver:
                continue
            ApprovalNode.objects.create(
                flow=flow,
                node_order=node_cfg.get('node_order', nodes_created + 1),
                approver=approver,
                status='pending',
                node_type=node_cfg.get('node_type', 'approver'),
                timeout_hours=node_cfg.get('timeout_hours', 48),
            )
            nodes_created += 1
    else:
        # 回退：单级审批（仅一个 admin 审批）
        approver = User.objects.filter(is_staff=True).first()
        if not approver:
            approver = User.objects.filter(is_superuser=True).first()
        if approver:
            ApprovalNode.objects.create(
                flow=flow,
                node_order=1,
                approver=approver,
                status='pending',
                node_type='approver',
                timeout_hours=int(get_setting('approval_timeout_hours', '48')),
            )

    # 更新当前节点
    first_node = ApprovalNode.objects.filter(flow=flow).order_by('node_order').first()
    if first_node:
        flow.current_node_order = first_node.node_order
        flow.save(update_fields=['current_node_order'])

    return flow
