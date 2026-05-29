"""
CRM 自动匹配命令：将 Income/Expense 记录的客户/供应商名称与 CRM 实体关联。

用法:
    python manage.py crm_match                   # 查看当前匹配统计
    python manage.py crm_match --apply            # 执行自动匹配
    python manage.py crm_match --apply --dry-run  # 预览匹配（不写入）

匹配规则：
    - Income.customer → crm.Client.name（精确匹配）
    - Expense.supplier → crm.Supplier.name（精确匹配）
"""

from django.core.management.base import BaseCommand
from apps.finance.models import Income, Expense
from apps.crm.models import Client, Supplier


class Command(BaseCommand):
    help = '将 Income/Expense 客户/供应商名称与 CRM 实体自动关联'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='执行匹配')
        parser.add_argument('--dry-run', action='store_true', help='预览匹配结果但不写入')

    def handle(self, *args, **options):
        apply_matches = options.get('apply', False)
        dry_run = options.get('dry_run', False)

        # ── 1. Income → CRM Client ────────────────────────────────────────
        self.stdout.write('\n=== Income 客户 → CRM Client ===')
        client_map = {c.name.strip(): c.id for c in Client.objects.all()}
        income_unmatched = Income.objects.filter(client_ref__isnull=True).exclude(customer='')

        matched, skipped = 0, 0
        for inc in income_unmatched.iterator(chunk_size=200):
            name = (inc.customer or '').strip()
            if not name:
                skipped += 1
                continue
            cid = client_map.get(name)
            if cid:
                if apply_matches and not dry_run:
                    Income.objects.filter(id=inc.id).update(client_ref_id=cid)
                matched += 1
            else:
                skipped += 1

        total_income = Income.objects.count()
        linked_income = Income.objects.filter(client_ref__isnull=False).count()
        self.stdout.write(f'  Income 总数: {total_income}')
        self.stdout.write(f'  已关联 CRM: {linked_income}')
        if apply_matches:
            if dry_run:
                self.stdout.write(f'  预览匹配: {matched} 条可匹配')
            else:
                self.stdout.write(f'  本次匹配: {matched} 条 | 跳过(无匹配): {skipped}')

        # ── 2. Expense → CRM Supplier ─────────────────────────────────────
        self.stdout.write('\n=== Expense 供应商 → CRM Supplier ===')
        supplier_map = {s.name.strip(): s.id for s in Supplier.objects.all()}
        exp_unmatched = Expense.objects.filter(supplier_ref__isnull=True).exclude(supplier='')

        matched2, skipped2 = 0, 0
        for exp in exp_unmatched.iterator(chunk_size=200):
            name = (exp.supplier or '').strip()
            if not name:
                skipped2 += 1
                continue
            sid = supplier_map.get(name)
            if sid:
                if apply_matches and not dry_run:
                    Expense.objects.filter(id=exp.id).update(supplier_ref_id=sid)
                matched2 += 1
            else:
                skipped2 += 1

        total_expense = Expense.objects.count()
        linked_expense = Expense.objects.filter(supplier_ref__isnull=False).count()
        self.stdout.write(f'  Expense 总数: {total_expense}')
        self.stdout.write(f'  已关联 CRM: {linked_expense}')
        if apply_matches:
            if dry_run:
                self.stdout.write(f'  预览匹配: {matched2} 条可匹配')
            else:
                self.stdout.write(f'  本次匹配: {matched2} 条 | 跳过(无匹配): {skipped2}')

        # ── 3. CRM 中未在 Income/Expense 中出现的名称 ─────────────────────
        self.stdout.write('\n=== CRM 中未使用的客户名称 ===')
        used_client_names = set(
            Income.objects.filter(client_ref__isnull=False).values_list('client_ref__name', flat=True).distinct()
        )
        unused_clients = Client.objects.exclude(name__in=used_client_names)
        for c in unused_clients:
            self.stdout.write(f'  ⚠️  {c.name} — 未产生收入记录')

        self.stdout.write('\n=== CRM 中未使用的供应商名称 ===')
        used_supplier_names = set(
            Expense.objects.filter(supplier_ref__isnull=False).values_list('supplier_ref__name', flat=True).distinct()
        )
        unused_suppliers = Supplier.objects.exclude(name__in=used_supplier_names)
        for s in unused_suppliers:
            self.stdout.write(f'  ⚠️  {s.name} — 未产生支出记录')

        self.stdout.write('\n✅ 完成')
