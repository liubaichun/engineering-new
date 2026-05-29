"""重新分类 expense_type 字段——基于公对公原则

核心规则：
  1. 供应商是真实公司名的 → 不可能是财务费用
  2. 供应商为空 + 银行术语 → 财务费用（手续费/年费/回单等）
  3. 技术服务费/服务费 + 有公司供应商 → 主营业务成本
  4. 费用报销/报销款 → 管理费用（不知道具体用途）
  5. 其他银行相关 + 无供应商 → 财务费用
"""

from django.core.management.base import BaseCommand
from apps.finance.models import Expense

# 银行常见公司（这些是银行自身，不是业务往来）
BANK_ENTITIES = ['网上电子汇划收入', '对公中间业务收入', '对公工行证书收入']


def _is_real_company(supplier):
    """判断供应商是否是一个真实公司（不是空的/银行内部记账名）"""
    if not supplier or not supplier.strip():
        return False
    s = supplier.strip()
    if s in BANK_ENTITIES:
        return False
    # 银行类关键词
    bank_keywords = ['银行', '收入', '证书', '手续费']
    if any(k in s for k in bank_keywords) and len(s) < 10:
        return False
    return True


class Command(BaseCommand):
    help = '重新分类支出类型——基于公对公原则'

    def handle(self, *args, **options):
        total = Expense.objects.count()
        changes = {
            'finance_to_main': 0,
            'finance_to_admin': 0,
            'other_to_main': 0,
            'other_to_admin': 0,
            'other_to_internal': 0,
            'other_to_agency': 0,
            'kept': 0,
        }

        for exp in Expense.objects.iterator():
            desc = (exp.description or '').strip()
            supplier = (exp.supplier or '').strip()
            original = exp.expense_type
            new_type = self._classify(desc, supplier, original, exp)

            if new_type and new_type != original:
                exp.expense_type = new_type
                exp.save(update_fields=['expense_type'])
                key = f'{original}_to_{new_type}'
                changes[key] = changes.get(key, 0) + 1
            else:
                changes['kept'] += 1

        self.stdout.write(f'总记录: {total}条')
        self.stdout.write('分类变更:')
        for k, v in changes.items():
            if v > 0 and k != 'kept':
                self.stdout.write(f'  {k}: {v}条')
        self.stdout.write(f'  未变更: {changes["kept"]}条')

        # 最终分布
        from collections import Counter

        final = Counter(Expense.objects.values_list('expense_type', flat=True))
        choices = dict(Expense._meta.get_field('expense_type').choices)
        self.stdout.write('\n最终分布:')
        for t, c in final.most_common():
            display = choices.get(t, t)
            self.stdout.write(f'  {display:10s} ({t:20s}) {c}条')

    def _classify(self, desc, supplier, original, exp):
        # ─── 规则1: 银行纯手续费（无公司供应商）→ 财务费用 ───
        bank_terms = [
            '手续费',
            '年费',
            '账户管理费',
            '批量代发付费',
            '批量代发',
            '网银支付',
            '代发代扣',
            '回单',
            '支票手续费',
            '财智账户卡',
        ]
        if any(k in desc for k in bank_terms):
            if not _is_real_company(supplier):
                return 'finance_expense'
            # 供应商是公司名 → 不是银行手续费，走下方规则

        # ─── 规则2: 技术服务费/服务费 + 有公司供应商 → 主营业务成本 ───
        service_terms = [
            '技术服务费',
            '服务费',
            '中标服务费',
            '招标服务费',
            '代理服务费',
            '测试化验',
            '委托业务',
            '维保服务费',
            '专用材料',
        ]
        if any(k in desc for k in service_terms):
            if _is_real_company(supplier):
                return 'main_cost'

        # ─── 规则3: 团建服务费 → 管理费用 ───
        if '团建' in desc:
            return 'admin_expense'

        # ─── 规则4: 缴税类 → 税费 ───
        if any(k in desc for k in ['缴税', '实时缴税', '批量缴税', '代理国库']):
            return 'tax'

        # ─── 规则5: 货款/采购/材料 → 主营业务成本 ───
        if any(k in desc for k in ['货款', '采购', '材料']):
            return 'main_cost'

        # ─── 规则6: 往来/借款/备用金/还款 → 内部往来 ───
        if any(k in desc for k in ['往来', '借款', '备用金', '还款']):
            return 'internal_transfer'

        # ─── 规则7: 离职补偿 → 管理费用 ───
        if any(k in desc for k in ['离职补偿', '经济补偿']):
            return 'admin_expense'

        # ─── 规则8: 社保托收 → 代收代付 ───
        if '托收' in desc:
            return 'agency'

        # ─── 规则9: 费用报销/报销款 → 管理费用 ───
        if any(k in desc for k in ['费用报销', '报销款', '报销', '费用']):
            return 'admin_expense'

        # ─── 规则10: 生育津贴 → 内部往来 ───
        if '生育津贴' in desc:
            return 'internal_transfer'

        # ─── 规则11: 年终奖/工资 → 工资薪酬 ───
        if any(k in desc for k in ['年终奖', '工资']):
            return 'salary'

        # ─── 规则12: 房费/房租/物业 → 管理费用 ───
        if any(k in desc for k in ['房费', '房租', '物业']):
            return 'admin_expense'

        # ─── 规则13: 差旅 → 差旅费用 ───
        if any(k in desc for k in ['差旅', '出差']):
            return 'travel'

        # ─── 规则14: 办公/文具 → 办公费用 ───
        if any(k in desc for k in ['办公', '文具', '打印纸', '耗材']):
            return 'office'

        # ─── 规则15: 空description但有公司供应商 → 看银行流水摘要 ───
        if not desc and _is_real_company(supplier):
            bs = exp.matched_statements.first()
            if bs and bs.summary:
                bs_desc = bs.summary.strip()
                # 用银行摘要再走一遍分类
                return self._classify(bs_desc, supplier, original, exp)
            # 银行摘要也没有 → 供应商是公司，大概率是主营业务成本
            return 'main_cost'

        # ─── 规则16: 空description且供应商为空 ───
        if not desc and not _is_real_company(supplier):
            bs = exp.matched_statements.first()
            if bs and bs.summary:
                bs_desc = bs.summary.strip()
                return self._classify(bs_desc, supplier, original, exp)

        # 默认：保持原分类
        return None
