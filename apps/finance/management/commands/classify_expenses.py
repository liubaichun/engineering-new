"""
批量重分类支出记录的 expense_type 字段。
根据 expense_category（银行类别）和摘要关键词自动映射：
  - 税款 → tax
  - 代发工资/奖金 → salary
  - 报销款 → office
  - 其他根据摘要关键词细分
"""
from django.core.management.base import BaseCommand
from apps.finance.models import Expense


def classify_by_bank_category(cat: str) -> str:
    """根据银行导入的 expense_category 判断 expense_type"""
    cat = (cat or '').strip()
    if '税款' in cat:
        return 'tax'
    if '工资' in cat or '奖金' in cat:
        return 'salary'
    if '报销' in cat:
        return 'office'
    if '手续费' in cat or '收费' in cat:
        return 'other'  # 银行手续费 → 其他
    return ''  # 需要进一步判断


def classify_by_summary(summary: str) -> str:
    """根据摘要/附言关键词判断 expense_type"""
    s = (summary or '').lower()
    if any(kw in s for kw in ['差旅', '机票', '酒店', '住宿', '高铁', '火车票']):
        return 'travel'
    if any(kw in s for kw in ['招待', '餐饮', '餐费', '饭']):
        return 'entertainment'
    if any(kw in s for kw in ['办公', '文具', '打印', '耗材']):
        return 'office'
    if any(kw in s for kw in ['通讯', '电话', '网费']):
        return 'communication'
    if any(kw in s for kw in ['广告', '推广', '市场']):
        return 'marketing'
    if any(kw in s for kw in ['采购', '货款', '购买']):
        return 'other'  # 成本类
    return ''


class Command(BaseCommand):
    help = '批量重分类支出类型'

    def handle(self, *args, **options):
        stats = {'tax': 0, 'salary': 0, 'office': 0, 'travel': 0,
                 'entertainment': 0, 'communication': 0, 'marketing': 0,
                 'rd': 0, 'advance': 0, 'other': 0}
        
        for exp in Expense.objects.iterator():
            cat = (exp.expense_category or '').strip()
            summary = (exp.summary or '').strip()
            etype = (exp.expense_type or '').strip()
            
            # 跳过已有合理分类的记录
            if etype in ('salary', 'social', 'tax', 'advance'):
                if etype in stats:
                    stats[etype] += 1
                continue
            
            # 按 expense_category 判断
            new_type = classify_by_bank_category(cat)
            
            # 如果没判断出来，按摘要关键词判断
            if not new_type:
                new_type = classify_by_summary(summary)
            
            # 还是没判断出来 → 其他
            if not new_type:
                # 根据供应商名再试一次
                supplier = (exp.supplier or '').strip()
                if any(kw in supplier for kw in ['电信', '移动', '联通', '网通']):
                    new_type = 'communication'
                elif any(kw in supplier for kw in ['税务局', '税局']):
                    new_type = 'tax'
                else:
                    new_type = 'other'
            
            exp.expense_type = new_type
            exp.save(update_fields=['expense_type'])
            
            if new_type in stats:
                stats[new_type] += 1
            else:
                stats[new_type] = 1
        
        self.stdout.write('重分类完成：')
        for k, v in sorted(stats.items(), key=lambda x: -x[1]):
            self.stdout.write(f'  {k}: {v}条')
        self.stdout.write(f'  合计: {sum(stats.values())}条')
