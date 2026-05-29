"""
审批超时检测定时任务
用法:
  python manage.py check_approval_timeouts          # 执行检测
  python manage.py check_approval_timeouts --dry-run # 仅预览不修改
  python manage.py check_approval_timeouts --hours=24 # 自定义超时阈值(小时)
"""

from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.approvals.models import ApprovalNode, ApprovalFlow


class Command(BaseCommand):
    help = '检测审批超时节点，标记为超时状态'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='仅预览不修改')
        parser.add_argument('--hours', type=int, default=0, help='额外超时阈值(小时),0表示使用节点自身timeout_hours')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        extra_hours = options['hours']

        now = timezone.now()
        self.stdout.write(f'[{now}] 开始检测超时节点...' + (' (DRY RUN)' if dry_run else ''))

        # 查找 pending 状态且可超时的节点
        pending_nodes = ApprovalNode.objects.filter(status__in=['pending', 'approved']).select_related(
            'flow', 'approver'
        )

        expired_count = 0
        processed_ids = []

        for node in pending_nodes:
            if not node.assigned_at:
                continue

            # 使用节点配置的 timeout_hours，如果没有则用默认 72 小时
            timeout_hours = node.timeout_hours or 72
            deadline = node.assigned_at + timedelta(hours=timeout_hours)

            # 如果额外指定了 hours，在节点超时基础上叠加
            if extra_hours > 0:
                deadline += timedelta(hours=extra_hours)

            if now > deadline:
                expired_count += 1
                processed_ids.append(node.id)
                status_label = '超时' if node.status == 'pending' else '超时(已批准)'

                self.stdout.write(
                    f'  [{node.id}] {node.flow.flow_type} '
                    f'| 节点{node.id} | {status_label} '
                    f'| 分配时间:{node.assigned_at} | 超时阈值:{timeout_hours}h'
                )

                if not dry_run:
                    node.status = 'expired'
                    node.save(update_fields=['status', 'decided_at'])

        self.stdout.write(
            self.style.SUCCESS(
                f'\n完成: 发现 {expired_count} 个超时节点' + (' (未执行修改)' if dry_run else ' (已全部标记)')
            )
        )

        if not dry_run and expired_count > 0:
            # 检查是否有超时节点的 flow 需要特殊处理
            timeout_flows = ApprovalFlow.objects.filter(nodes__status='expired').distinct()
            self.stdout.write(f'涉及 {timeout_flows.count()} 条审批流含超时节点')
