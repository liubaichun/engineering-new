"""
FlowEngine - 工作流引擎
负责执行流程模板，管理工作流实例
"""
from datetime import datetime
from django.utils import timezone
from apps.tasks.models import (
    Task, FlowTemplate, FlowNodeTemplate,
    TaskStageInstance, TaskFlowInstance,
    StageActivity, FlowTransition
)


class FlowEngine:
    """工作流引擎"""

    def __init__(self, task):
        self.task = task
        self.template = None
        self.instance = None

    def start_flow(self, template, started_by=None):
        """
        为任务启动一个流程实例。
        template: FlowTemplate 对象（不是ID）
        返回: TaskFlowInstance 对象
        """
        if isinstance(template, int):
            template = FlowTemplate.objects.get(id=template, is_active=True)
        elif isinstance(template, dict):
            template = FlowTemplate.objects.get(id=template.get('id'), is_active=True)

        self.template = template
        nodes = FlowNodeTemplate.objects.filter(template=template).order_by('order')

        if not nodes.exists():
            raise ValueError('流程模板没有节点')

        first_node = nodes.first()

        # 创建任务流程实例
        instance = TaskFlowInstance.objects.create(
            task=self.task,
            template=template,
            current_node=first_node,
            status='running',
            started_by=started_by,
            started_at=timezone.now(),
            company_id=self.task.company_id,
        )
        self.instance = instance

        # 创建第一个节点的阶段实例
        stage_instance = TaskStageInstance.objects.create(
            task=self.task,
            node_template=first_node,
            status='pending',
            assignee=self._resolve_assignee(first_node),
            company_id=self.task.company_id,
        )

        # 记录活动
        StageActivity.objects.create(
            stage_instance=stage_instance,
            action='create',
            actor=started_by or self.task.reporter,
            to_status='pending',
            comment=f'流程启动: {template.name}',
            company_id=self.task.company_id,
        )

        # 通知第一个阶段的处理人
        try:
            from apps.tasks.notification_service import notify_flow_started
            notify_flow_started(self.task, stage_instance, started_by)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f'[FlowEngine] notify_flow_started failed: {e}')

        return instance

    def _resolve_assignee(self, node):
        """根据节点配置解析处理人"""
        if not node.assignee_value:
            return None

        if node.assignee_type == 'user':
            from apps.core.models import User
            try:
                return User.objects.get(id=int(node.assignee_value))
            except (User.DoesNotExist, ValueError):
                return None
        elif node.assignee_type == 'role':
            from apps.core.models import User
            return User.objects.filter(roles__code=node.assignee_value).first()

        return None

    def complete_node(self, node_template_or_id, action='approve', actor=None, comment=''):
        """
        完成指定节点，流转到下一节点。
        node_template_or_id: FlowNodeTemplate 对象或 ID
        action: 'approve' 或 'reject'
        """
        if isinstance(node_template_or_id, int):
            node_template = FlowNodeTemplate.objects.get(id=node_template_or_id)
        elif isinstance(node_template_or_id, dict):
            node_template = FlowNodeTemplate.objects.get(id=node_template_or_id.get('id'))
        else:
            node_template = node_template_or_id

        # 找到当前节点实例
        current = TaskStageInstance.objects.filter(
            task=self.task,
            node_template=node_template,
            status__in=['pending', 'in_progress']
        ).first()

        if not current:
            raise ValueError('没有进行中的流程节点')

        old_status = current.status
        current.status = 'approved' if action == 'approve' else 'rejected'
        current.completed_at = timezone.now()
        current.save()

        # 记录活动
        StageActivity.objects.create(
            stage_instance=current,
            action=action,
            actor=actor,
            from_status=old_status,
            to_status=current.status,
            comment=comment,
            company_id=self.task.company_id,
        )

        # 获取下一节点
        next_node = FlowNodeTemplate.objects.filter(
            template=self.template,
            order__gt=node_template.order
        ).order_by('order').first()

        # 记录流转
        FlowTransition.objects.create(
            task=self.task,
            from_node=current.node_template,
            to_node=next_node,
            actor=actor,
            action=action,
            remark=comment,
            company_id=self.task.company_id,
        )

        if next_node:
            # 更新流程实例当前节点
            if self.instance:
                self.instance.current_node = next_node
                self.instance.save()

            # 创建下一节点实例
            next_instance = TaskStageInstance.objects.create(
                task=self.task,
                node_template=next_node,
                status='pending',
                assignee=self._resolve_assignee(next_node),
                company_id=self.task.company_id,
            )

            # 通知下一阶段处理人
            try:
                from apps.tasks.notification_service import notify_stage_completed
                notify_stage_completed(self.task, current, next_instance, action, actor)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f'[FlowEngine] notify_stage_completed failed: {e}')

            return {
                'success': True,
                'message': f'已流转到: {next_node.name}',
                'next_node': next_node.name,
                'next_instance_id': next_instance.id,
                'flow_completed': False,
            }
        else:
            # 流程结束
            if self.instance:
                self.instance.status = 'completed'
                self.instance.current_node = None
                self.instance.completed_at = timezone.now()
                self.instance.save()

            # 通知流程完成
            try:
                from apps.tasks.notification_service import notify_flow_completed
                notify_flow_completed(self.task, actor)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f'[FlowEngine] notify_flow_completed failed: {e}')

            return {
                'success': True,
                'message': '流程已完成',
                'flow_completed': True,
            }

    def reject_node(self, node_template_or_id, actor=None, comment=''):
        """拒绝节点"""
        return self.complete_node(node_template_or_id, action='reject', actor=actor, comment=comment)

    def get_flow_status(self):
        """获取任务流程状态"""
        instances = TaskStageInstance.objects.filter(task=self.task).select_related('node_template')

        if not instances.exists():
            return {
                'has_flow': False,
                'message': '该任务没有运行中的流程'
            }

        current = instances.filter(status__in=['pending', 'in_progress']).first()
        completed = instances.filter(status='approved')

        template_name = None
        if self.template:
            template_name = self.template.name
        elif instances.first():
            template_name = instances.first().node_template.template.name

        return {
            'has_flow': True,
            'template_name': template_name,
            'current_node': current.node_template.name if current else None,
            'current_status': current.status if current else None,
            'current_assignee': current.assignee.username if current and current.assignee else None,
            'completed_nodes': [
                {'name': i.node_template.name, 'completed_at': i.completed_at}
                for i in completed
            ],
            'total_nodes': instances.count(),
            'completed_count': completed.count()
        }

    def get_flow_progress(self):
        """获取流程进度百分比"""
        instances = TaskStageInstance.objects.filter(task=self.task)
        total = instances.count()
        if total == 0:
            return 0
        completed = instances.filter(status__in=['approved', 'rejected', 'skipped']).count()
        return int(completed / total * 100)

    @staticmethod
    def assign_flow_to_task(task, template, started_by=None):
        """静态方法：为任务分配流程"""
        engine = FlowEngine(task)
        return engine.start_flow(template, started_by=started_by)
