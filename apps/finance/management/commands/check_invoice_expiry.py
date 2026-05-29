"""
发票到期提醒 — 每日检查逾期/即将到期的发票并通知。

检测规则：
- 逾期：due_date 已过且未付款（payment_date is null）
- 即将到期：due_date 在今明7天内且未付款
- 同时检查开出发票（income）：应收款到期未收
- 收到发票（expense）：应付款到期未付

用法：./manage.py check_invoice_expiry
推荐定时：每天 9:00（crontab）
"""

import os
from datetime import date, timedelta
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = '检查发票到期情况并输出提醒'

    def handle(self, *args, **options):
        from apps.finance.models import Invoice
        from apps.core.models import User, Notification

        today = date.today()
        seven_days = today + timedelta(days=7)

        # 逾期发票：due_date < today 且未付款
        overdue = (
            Invoice.objects.filter(
                due_date__lt=today,
                payment_date__isnull=True,
            )
            .select_related('company')
            .order_by('due_date')
        )

        # 即将到期：due_date 在 [today, today+7] 且未付款
        due_soon = (
            Invoice.objects.filter(
                due_date__gte=today,
                due_date__lte=seven_days,
                payment_date__isnull=True,
            )
            .select_related('company')
            .order_by('due_date')
        )

        # 输出报告
        lines = []
        lines.append(f'【发票到期检查】{today.isoformat()}')
        lines.append(f'逾期发票：{overdue.count()} 张')
        lines.append(f'即将到期：{due_soon.count()} 张')
        lines.append('')

        has_alert = False

        if overdue.exists():
            has_alert = True
            lines.append('=' * 60)
            lines.append('⚠️ 逾期发票（已超期未付款）')
            lines.append('=' * 60)
            total_overdue = 0
            for inv in overdue:
                days_overdue = (today - inv.due_date).days
                cname = inv.company.name if inv.company else '-'
                inv_type = '开出' if inv.type == 'income' else '收到'
                amt = float(inv.amount or 0)
                total_overdue += amt
                lines.append(
                    f'  [{inv_type}] {inv.invoice_no} | {inv.counterparty} | '
                    f'¥{amt:,.2f} | 已逾期 {days_overdue} 天 | 到期日 {inv.due_date} | {cname}'
                )
            lines.append(f'  逾期总金额：¥{total_overdue:,.2f}')
            lines.append('')

        if due_soon.exists():
            has_alert = True
            lines.append('=' * 60)
            lines.append('🔔 即将到期发票（7天内）')
            lines.append('=' * 60)
            total_soon = 0
            for inv in due_soon:
                days_left = (inv.due_date - today).days
                cname = inv.company.name if inv.company else '-'
                inv_type = '开出' if inv.type == 'income' else '收到'
                amt = float(inv.amount or 0)
                total_soon += amt
                lines.append(
                    f'  [{inv_type}] {inv.invoice_no} | {inv.counterparty} | '
                    f'¥{amt:,.2f} | 剩余 {days_left} 天 | 到期日 {inv.due_date} | {cname}'
                )
            lines.append(f'  即将到期总金额：¥{total_soon:,.2f}')
            lines.append('')

        if not overdue.exists() and not due_soon.exists():
            lines.append('✅ 暂无到期/逾期发票，一切正常。')

        output = '\n'.join(lines)

        # 输出到 stdout
        self.stdout.write(output)

        # 记录到日志文件
        log_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '..', '..', 'logs'
        )
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, 'invoice_expiry.log')
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(output + '\n' + '-' * 60 + '\n')

        # 有异常时发送系统通知给所有活跃用户
        if has_alert:
            title = f'发票到期提醒（{today.isoformat()}）'
            content_parts = []
            if overdue.exists():
                content_parts.append(f'逾期 {overdue.count()} 张')
            if due_soon.exists():
                content_parts.append(f'即将到期 {due_soon.count()} 张')
            content = '，'.join(content_parts) if content_parts else '有到期发票待处理'
            for user in User.objects.filter(is_active=True):
                Notification.objects.create(
                    user=user,
                    title=title,
                    content=output[:500],
                    notification_type='invoice_expiry',
                    level='warning',
                )

        return output
