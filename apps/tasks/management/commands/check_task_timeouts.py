"""
任务阶段超时检测定时任务 — 每小时执行一次

用法：
    python manage.py check_task_timeouts

Crontab 配置（每小时第5分）：
    5 * * * * cd /root/engineering-new && venv/bin/python manage.py check_task_timeouts >> logs/task_timeouts.log 2>&1

检测内容：
    TaskStageInstance.status='pending' 且已超时（started_at + timeout_hours < now）
    且最近24小时内未发过同类通知
"""

import logging
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone as dj_timezone

from apps.tasks.models import TaskStageInstance


logger = logging.getLogger('check_task_timeouts')


class Command(BaseCommand):
    help = '检测任务阶段超时并发送外部渠道通知'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='仅打印，不实际发送通知')

    def handle(self, *args, **options):
        dry = options['dry_run']
        self.stdout.write(f'[{dj_timezone.now()}] 开始任务阶段超时检测 (dry={dry})')

        if dry:
            self.stdout.write(self.style.WARNING('  DRY RUN — 不发送通知'))

        count = 0

        # 查找 pending 状态且超时的阶段实例
        overdue_stages = TaskStageInstance.objects.filter(
            status='pending',
        ).select_related('node_template', 'task', 'assignee')

        for stage in overdue_stages:
            if not stage.assignee:
                continue
            if not stage.started_at:
                # 没有开始时间，不算超时（等待中）
                continue
            timeout_hours = stage.node_template.timeout_hours if stage.node_template else None
            if not timeout_hours or timeout_hours <= 0:
                continue

            deadline = stage.started_at + timedelta(hours=timeout_hours)
            if dj_timezone.now() < deadline:
                continue  # 未超时

            # 超时了，发送通知
            task_title = stage.task.title if stage.task else '未知任务'
            stage_name = stage.node_template.name if stage.node_template else '未知阶段'
            hours_overdue = int((dj_timezone.now() - deadline).total_seconds() // 3600)

            title = f'⏰ 任务阶段超时：{task_title}'
            content = [
                '您负责的任务阶段已超时',
                f'任务：「{task_title}」',
                f'阶段：{stage_name}',
                f'要求完成时间：{timeout_hours} 小时',
                f'已超时：{hours_overdue} 小时',
                '请尽快处理！',
            ]

            if dry:
                self.stdout.write(
                    f'  [超时] {task_title}/{stage_name} -> {stage.assignee.username} (已超时{hours_overdue}h)'
                )
            else:
                try:
                    from apps.tasks.notification_service import notify_stage_timeout

                    notify_stage_timeout(stage)
                    self.stdout.write(f'  [通知] {task_title}/{stage_name} -> {stage.assignee.username}')
                except Exception as e:
                    self.stderr.write(f'  [错误] {task_title}/{stage_name}: {e}')

            count += 1

        self.stdout.write(self.style.SUCCESS(f'检测完成：共 {count} 个超时阶段'))
