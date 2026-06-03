"""
清理操作审计日志 — 删除指定天数前的过期记录。

用法：
  python manage.py clean_audit_logs                         # 默认清理 90 天前的
  python manage.py clean_audit_logs --days 30               # 清理 30 天前的
  python manage.py clean_audit_logs --days 90 --dry-run     # 只统计不删除
  python manage.py clean_audit_logs --batch-size 10000      # 每批删除量（默认 5000）
"""

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, connection
from django.utils import timezone

from apps.core.models import OperationAuditLog


class Command(BaseCommand):
    help = '清理过期操作审计日志'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days', type=int, default=90,
            help='保留 N 天内的日志（默认 90 天）',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='仅统计待删除数量，不实际删除',
        )
        parser.add_argument(
            '--batch-size', type=int, default=5000,
            help='每批删除量（默认 5000）',
        )

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        batch_size = options['batch_size']

        if days < 1:
            raise CommandError('--days 必须 >= 1')

        cutoff = timezone.now() - timedelta(days=days)

        total = OperationAuditLog.objects.filter(
            created_at__lt=cutoff
        ).count()

        if total == 0:
            self.stdout.write(self.style.SUCCESS(f'没有 {days} 天前的日志需要清理'))
            return

        self.stdout.write(
            f'保留最近 {days} 天（{cutoff.date()} 之后）的日志\n'
            f'待删除记录数: {self.style.WARNING(str(total))}'
        )

        if dry_run:
            self.stdout.write(self.style.SUCCESS('--dry-run 模式，未实际删除'))
            return

        # 分批删除
        deleted_total = 0
        while True:
            ids = list(
                OperationAuditLog.objects
                .filter(created_at__lt=cutoff)
                .values_list('id', flat=True)[:batch_size]
            )
            if not ids:
                break
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "DELETE FROM core_operation_audit_log WHERE id = ANY(%s)",
                        [ids],
                    )
                    deleted = cursor.rowcount
            deleted_total += deleted
            self.stdout.write(f'  已删除 {deleted_total}/{total} 条')

        self.stdout.write(self.style.SUCCESS(
            f'清理完成！共删除 {deleted_total} 条过期审计日志'
        ))
