from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Project(models.Model):
    """项目模型"""
    
    STATUS_CHOICES = [
        ('draft', '草稿'),
        ('active', '进行中'),
        ('completed', '已完成'),
        ('archived', '已归档'),
    ]
    
    name = models.CharField(verbose_name='项目名称', max_length=200)
    code = models.CharField(verbose_name='项目代码', max_length=50, unique=True)
    description = models.TextField(verbose_name='描述', blank=True, default='')
    status = models.CharField(verbose_name='状态', max_length=20, choices=STATUS_CHOICES, default='draft')
    owner = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='owned_projects', verbose_name='负责人'
    )
    start_date = models.DateTimeField(verbose_name='开始日期', null=True, blank=True)
    end_date = models.DateTimeField(verbose_name='结束日期', null=True, blank=True)
    progress = models.DecimalField(
        verbose_name='进度%', max_digits=5, decimal_places=2, default=0,
        help_text='项目完成进度，0-100'
    )
    budget = models.DecimalField(
        verbose_name='预算', max_digits=14, decimal_places=2, null=True, blank=True,
        help_text='项目预算金额'
    )
    company = models.ForeignKey(
        'finance.Company', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='projects', verbose_name='所属公司'
    )
    created_at = models.DateTimeField(verbose_name='创建时间', auto_now_add=True)
    updated_at = models.DateTimeField(verbose_name='更新时间', auto_now=True)
    
    class Meta:
        db_table = 'tasks_project'
        verbose_name = '项目'
        verbose_name_plural = '项目'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.code} - {self.name}"

    @property
    def calculated_progress(self):
        """根据任务完成情况自动计算项目进度（排除已取消任务）"""
        tasks = self.tasks.exclude(status='cancelled')
        total = tasks.count()
        if total == 0:
            return 0
        completed = tasks.filter(status='completed').count()
        return round(completed / total * 100, 1)


class Task(models.Model):
    """任务模型"""
    
    PRIORITY_CHOICES = [
        ('low', '低'),
        ('medium', '中'),
        ('high', '高'),
        ('critical', '紧急'),
    ]
    
    STATUS_CHOICES = [
        ('pending', '待开始'),
        ('in_progress', '进行中'),
        ('completed', '已完成'),
        ('cancelled', '已取消'),
    ]
    
    title = models.CharField(verbose_name='任务标题', max_length=500)
    code = models.CharField(verbose_name='任务编号', max_length=50)
    description = models.TextField(verbose_name='描述', blank=True, default='')
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE,
        related_name='tasks', verbose_name='所属项目'
    )
    priority = models.CharField(verbose_name='优先级', max_length=20, choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField(verbose_name='状态', max_length=20, choices=STATUS_CHOICES, default='pending')
    assignee = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_tasks', verbose_name='处理人'
    )
    reporter = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reported_tasks', verbose_name='报告人'
    )
    due_date = models.DateTimeField(verbose_name='截止日期', null=True, blank=True)
    completed_at = models.DateTimeField(verbose_name='完成时间', null=True, blank=True)
    created_at = models.DateTimeField(verbose_name='创建时间', auto_now_add=True)
    updated_at = models.DateTimeField(verbose_name='更新时间', auto_now=True)
    
    class Meta:
        db_table = 'tasks_task'
        verbose_name = '任务'
        verbose_name_plural = '任务'
        ordering = ['-created_at']
        unique_together = ['project', 'code']
    
    def __str__(self):
        return f"{self.project.code}-{self.code} {self.title}"


class FlowTemplate(models.Model):
    """流程模板"""
    
    TYPE_CHOICES = [
        ('development', '开发流程'),
        ('approval', '审批流程'),
        ('custom', '自定义'),
    ]
    
    name = models.CharField(verbose_name='模板名称', max_length=200)
    code = models.CharField(verbose_name='模板代码', max_length=50, unique=True)
    type = models.CharField(verbose_name='类型', max_length=20, choices=TYPE_CHOICES, default='development')
    description = models.TextField(verbose_name='描述', blank=True, default='')
    is_active = models.BooleanField(verbose_name='是否启用', default=True)
    created_at = models.DateTimeField(verbose_name='创建时间', auto_now_add=True)
    updated_at = models.DateTimeField(verbose_name='更新时间', auto_now=True)
    
    class Meta:
        db_table = 'tasks_flow_template'
        verbose_name = '流程模板'
        verbose_name_plural = '流程模板'
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class FlowNodeTemplate(models.Model):
    """流程节点模板"""
    
    NODE_TYPE_CHOICES = [
        ('start', '开始'),
        ('task', '任务节点'),
        ('approval', '审批节点'),
        ('condition', '条件节点'),
        ('end', '结束'),
    ]
    
    template = models.ForeignKey(
        FlowTemplate, on_delete=models.CASCADE,
        related_name='nodes', verbose_name='所属模板'
    )
    name = models.CharField(verbose_name='节点名称', max_length=200)
    code = models.CharField(verbose_name='节点代码', max_length=50)
    node_type = models.CharField(verbose_name='节点类型', max_length=20, choices=NODE_TYPE_CHOICES, default='task')
    description = models.TextField(verbose_name='描述', blank=True, default='')
    assignee_type = models.CharField(
        verbose_name=' assignee type', max_length=20, 
        choices=[('user', '指定用户'), ('role', '指定角色'), ('field', '字段值')],
        default='user'
    )
    assignee_value = models.CharField(verbose_name=' assignee value', max_length=200, blank=True, default='')
    order = models.IntegerField(verbose_name='顺序', default=0)
    timeout_hours = models.IntegerField(verbose_name='超时时间(小时)', default=0)
    created_at = models.DateTimeField(verbose_name='创建时间', auto_now_add=True)
    
    class Meta:
        db_table = 'tasks_flow_node_template'
        verbose_name = '流程节点模板'
        verbose_name_plural = '流程节点模板'
        ordering = ['template', 'order']
        unique_together = ['template', 'code']
    
    def __str__(self):
        return f"{self.template.code} - {self.code}: {self.name}"


class TaskStageInstance(models.Model):
    """任务阶段实例 - 流程模板在具体任务上的实例化"""
    
    STATUS_CHOICES = [
        ('pending', '待处理'),
        ('in_progress', '进行中'),
        ('approved', '已通过'),
        ('rejected', '已拒绝'),
        ('skipped', '已跳过'),
    ]
    
    task = models.ForeignKey(
        Task, on_delete=models.CASCADE,
        related_name='stage_instances', verbose_name='所属任务'
    )
    node_template = models.ForeignKey(
        FlowNodeTemplate, on_delete=models.CASCADE,
        related_name='stage_instances', verbose_name='节点模板'
    )
    status = models.CharField(verbose_name='状态', max_length=20, choices=STATUS_CHOICES, default='pending')
    assignee = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='stage_assignments', verbose_name='处理人'
    )
    started_at = models.DateTimeField(verbose_name='开始时间', null=True, blank=True)
    completed_at = models.DateTimeField(verbose_name='完成时间', null=True, blank=True)
    remark = models.TextField(verbose_name='备注', blank=True, default='')
    created_at = models.DateTimeField(verbose_name='创建时间', auto_now_add=True)
    updated_at = models.DateTimeField(verbose_name='更新时间', auto_now=True)
    
    class Meta:
        db_table = 'tasks_task_stage_instance'
        verbose_name = '任务阶段实例'
        verbose_name_plural = '任务阶段实例'
        ordering = ['task', 'node_template__order']
    
    def __str__(self):
        return f"{self.task.code} - {self.node_template.name} ({self.get_status_display()})"


class TaskFlowInstance(models.Model):
    """任务流程实例 - 流程模板在具体任务上的完整实例"""
    
    STATUS_CHOICES = [
        ('pending', '待启动'),
        ('running', '运行中'),
        ('completed', '已完成'),
        ('cancelled', '已取消'),
        ('suspended', '已暂停'),
    ]
    
    task = models.OneToOneField(
        Task, on_delete=models.CASCADE,
        related_name='flow_instance', verbose_name='所属任务'
    )
    template = models.ForeignKey(
        FlowTemplate, on_delete=models.SET_NULL, null=True,
        related_name='instances', verbose_name='流程模板'
    )
    current_node = models.ForeignKey(
        FlowNodeTemplate, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='current_in', verbose_name='当前节点'
    )
    status = models.CharField(verbose_name='状态', max_length=20, choices=STATUS_CHOICES, default='pending')
    started_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='started_flows', verbose_name='启动人'
    )
    started_at = models.DateTimeField(verbose_name='启动时间', null=True, blank=True)
    completed_at = models.DateTimeField(verbose_name='完成时间', null=True, blank=True)
    created_at = models.DateTimeField(verbose_name='创建时间', auto_now_add=True)
    updated_at = models.DateTimeField(verbose_name='更新时间', auto_now=True)
    
    class Meta:
        db_table = 'tasks_task_flow_instance'
        verbose_name = '任务流程实例'
        verbose_name_plural = '任务流程实例'
    
    def __str__(self):
        return f"{self.task.code} - {self.template.name if self.template else '无模板'} ({self.get_status_display()})"


class StageActivity(models.Model):
    """阶段活动记录"""
    
    ACTION_CHOICES = [
        ('create', '创建'),
        ('start', '开始'),
        ('submit', '提交'),
        ('approve', '批准'),
        ('reject', '拒绝'),
        ('transfer', '转交'),
        ('comment', '评论'),
    ]
    
    stage_instance = models.ForeignKey(
        TaskStageInstance, on_delete=models.CASCADE,
        related_name='activities', verbose_name='阶段实例'
    )
    action = models.CharField(verbose_name='动作', max_length=20, choices=ACTION_CHOICES)
    actor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='stage_actions', verbose_name='操作人'
    )
    comment = models.TextField(verbose_name='评论', blank=True, default='')
    from_status = models.CharField(verbose_name='原状态', max_length=20, blank=True, default='')
    to_status = models.CharField(verbose_name='新状态', max_length=20, blank=True, default='')
    created_at = models.DateTimeField(verbose_name='创建时间', auto_now_add=True)
    
    class Meta:
        db_table = 'tasks_stage_activity'
        verbose_name = '阶段活动记录'
        verbose_name_plural = '阶段活动记录'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.stage_instance} - {self.get_action_display()} by {self.actor}"


class FlowTransition(models.Model):
    """流程流转记录 - 记录任务在不同阶段之间的流转"""
    
    task = models.ForeignKey(
        Task, on_delete=models.CASCADE,
        related_name='transitions', verbose_name='所属任务'
    )
    from_node = models.ForeignKey(
        FlowNodeTemplate, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='transitions_from', verbose_name='源节点'
    )
    to_node = models.ForeignKey(
        FlowNodeTemplate, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='transitions_to', verbose_name='目标节点'
    )
    actor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='flow_transitions', verbose_name='操作人'
    )
    action = models.CharField(verbose_name='动作', max_length=50, blank=True, default='')
    remark = models.TextField(verbose_name='备注', blank=True, default='')
    created_at = models.DateTimeField(verbose_name='创建时间', auto_now_add=True)
    
    class Meta:
        db_table = 'tasks_flow_transition'
        verbose_name = '流程流转记录'
        verbose_name_plural = '流程流转记录'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.task.code}: {self.from_node} -> {self.to_node}"
