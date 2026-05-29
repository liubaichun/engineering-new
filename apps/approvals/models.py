from django.db import models
from django.conf import settings


class ApprovalFlow(models.Model):
    """审批流主表"""

    FLOW_TYPE_CHOICES = [
        ('payment', '付款审批'),
        ('project', '立项审批'),
        ('expense', '支出审批'),
        ('income', '收入确认'),
        ('wage', '工资审批'),
        ('custom', '自定义审批'),
    ]
    STATUS_CHOICES = [
        ('draft', '草稿'),
        ('pending', '待审批'),
        ('approved', '已批准'),
        ('rejected', '已拒绝'),
        ('cancelled', '已取消'),
    ]

    name = models.CharField(verbose_name='审批名称', max_length=255)
    flow_type = models.CharField(verbose_name='审批类型', max_length=20, choices=FLOW_TYPE_CHOICES)
    status = models.CharField(verbose_name='状态', max_length=20, choices=STATUS_CHOICES, default='draft')
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='submitted_approvals',
        verbose_name='申请人',
    )
    amount = models.DecimalField(
        verbose_name='金额', max_digits=14, decimal_places=2, null=True, blank=True, help_text='审批涉及的金额'
    )
    description = models.TextField(verbose_name='审批说明', blank=True, default='')
    current_node_order = models.IntegerField(verbose_name='当前节点顺序', default=0)
    result_comment = models.TextField(verbose_name='审批结论', blank=True, default='')
    related_type = models.CharField(
        verbose_name='关联业务类型',
        max_length=50,
        default='',
        help_text='关联业务对象类型，如 expense/income/contract/project',
    )
    related_id = models.IntegerField(verbose_name='关联业务ID', default=0, help_text='关联业务对象的ID')
    company_id = models.PositiveIntegerField(
        verbose_name='所属公司', null=True, blank=True, db_index=True, help_text='所属公司ID，用于多租户隔离'
    )
    decided_at = models.DateTimeField(verbose_name='审批完成时间', null=True, blank=True)
    created_at = models.DateTimeField(verbose_name='创建时间', auto_now_add=True)
    updated_at = models.DateTimeField(verbose_name='更新时间', auto_now=True)

    class Meta:
        db_table = 'approvals_flow'
        ordering = ['-created_at']
        verbose_name = '审批流'
        verbose_name_plural = '审批流'

    def __str__(self):
        return f'{self.get_flow_type_display()} - {self.name}'


class ApprovalNode(models.Model):
    """审批节点表"""

    STATUS_CHOICES = [
        ('pending', '待审批'),
        ('approved', '已批准'),
        ('rejected', '已拒绝'),
        ('skipped', '已跳过'),
        ('expired', '已过期'),
    ]
    NODE_TYPE_CHOICES = [
        ('approver', '审批人'),
        ('delegate', '委托'),
        ('transfer', '转交'),
    ]

    flow = models.ForeignKey(ApprovalFlow, on_delete=models.CASCADE, related_name='nodes', verbose_name='所属审批流')
    node_order = models.IntegerField(verbose_name='审批顺序', default=1)
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='approval_nodes',
        verbose_name='审批人',
    )
    status = models.CharField(verbose_name='状态', max_length=20, choices=STATUS_CHOICES, default='pending')
    node_type = models.CharField(
        verbose_name='节点类型',
        max_length=20,
        choices=NODE_TYPE_CHOICES,
        default='approver',
        help_text='标识节点是审批人还是转交/委托产生的节点',
    )
    delegated_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='delegated_nodes',
        verbose_name='委托给',
    )
    comment = models.TextField(verbose_name='审批意见', blank=True, default='')
    assigned_at = models.DateTimeField(verbose_name='分配时间', auto_now_add=True)
    decided_at = models.DateTimeField(verbose_name='审批时间', null=True, blank=True)
    timeout_hours = models.IntegerField(
        verbose_name='超时小时数', null=True, blank=True, help_text='节点超时时间（小时），超时后自动过期'
    )
    company_id = models.PositiveIntegerField(
        verbose_name='所属公司', null=True, blank=True, db_index=True, help_text='所属公司ID，用于多租户隔离'
    )

    class Meta:
        db_table = 'approvals_node'
        ordering = ['node_order']
        verbose_name = '审批节点'
        verbose_name_plural = '审批节点'

    def __str__(self):
        return f'{self.flow.name} - 节点{self.node_order} - {self.approver}'


class ApprovalTemplate(models.Model):
    """审批流程模板"""

    FLOW_TYPE_CHOICES = [
        ('payment', '付款审批'),
        ('project', '立项审批'),
        ('expense', '支出审批'),
        ('income', '收入确认'),
        ('wage', '工资审批'),
        ('custom', '自定义审批'),
    ]

    name = models.CharField(verbose_name='模板名称', max_length=255)
    code = models.CharField(verbose_name='模板编码', max_length=50, unique=True)
    flow_type = models.CharField(verbose_name='审批类型', max_length=20, choices=FLOW_TYPE_CHOICES)
    description = models.TextField(verbose_name='模板说明', blank=True, default='')
    nodes = models.JSONField(
        verbose_name='节点配置',
        default=list,
        help_text='节点配置JSON数组，每个节点包含：node_order(顺序)/approver_type(admin/department_head/specific_user)/approver_id(用户ID)/timeout_hours(超时小时)/node_type(single/all_sign)',
    )
    conditions = models.JSONField(
        verbose_name='触发条件',
        default=dict,
        blank=True,
        help_text='触发条件JSON，如：{"min_amount": 5000, "max_amount": null}',
    )
    is_active = models.BooleanField(verbose_name='是否启用', default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_approval_templates',
        verbose_name='创建人',
    )
    company_id = models.PositiveIntegerField(
        verbose_name='所属公司', null=True, blank=True, db_index=True, help_text='所属公司ID，用于多租户隔离'
    )
    created_at = models.DateTimeField(verbose_name='创建时间', auto_now_add=True)
    updated_at = models.DateTimeField(verbose_name='更新时间', auto_now=True)

    class Meta:
        db_table = 'approvals_template'
        ordering = ['-created_at']
        verbose_name = '审批模板'
        verbose_name_plural = '审批模板'

    def __str__(self):
        return f'{self.name} ({self.get_flow_type_display()})'
