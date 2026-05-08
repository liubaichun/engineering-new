"""
银行流水导入视图 v2.0 — CMB 36列全量解析
POST /api/finance/import/bank-statement/        — 预览（不写库）
POST /api/finance/import/bank-statement/confirm/ — 确认导入
GET  /api/finance/import/bank-statement/banks/  — 支持的银行列表
"""
import datetime, io, re, uuid
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.finance.bank_adapters import (
    ALL_ADAPTERS, detect_and_parse, parse_with_adapter, ParsedTransaction
)
from apps.finance.models import Company, Income, Expense, Invoice
from apps.finance.models_bank import BankAccount, BankStatement
from apps.crm.models import Client, Supplier


# ═══════════════════════════════════════════════════════════════════════════
# 分类规则（优先级：TX_TYPE_RULES > 摘要关键词 > 默认）
# ═══════════════════════════════════════════════════════════════════════════

# ── 0. 税务子类型判断 ─────────────────────────────────────────────────
def _detect_tax_subtype(summary: str, t) -> str:
    """
    根据摘要判断税务子类型。
    返回：税务 | 社保 | 个人所得税 | 增值税 | 企业所得税 | ...
    """
    text = ' '.join(filter(None, [
        summary,
        getattr(t, 'biz_summary', '') or '',
        getattr(t, 'other_summary', '') or '',
        getattr(t, 'ext_summary', '') or '',
        getattr(t, 'usage', '') or '',
    ])).lower()

    # 按优先级匹配
    if any(kw in text for kw in ('社保费', '社保', '养老', '失业', '生育', '医疗')):
        return '社保'
    if any(kw in text for kw in ('个税', '个人所得税', '工资薪金')):
        return '个人所得税'
    if any(kw in text for kw in ('增值税', '营改增')):
        return '增值税'
    if any(kw in text for kw in ('企业所得税', '所得', '利得')):
        return '企业所得税'
    if any(kw in text for kw in ('印花税', '城建税', '教育费', '地方教育费', '水利基金')):
        return '其他税金'
    return '税务'  # 默认


# ── 0. 往来子类型判断 ─────────────────────────────────────────────────
def _detect_往来_subtype(cp_name, summary, tx_type, t):
    """
    根据对手方、摘要、交易类型判断往来款的详细子类型。
    返回 (往来_type, 往来_remark)
    往来_type: 借款 | 投资款 | 社保退款 | 个人往来 | 待核查
    """
    summary_full = ' '.join(filter(None, [
        summary,
        getattr(t, 'biz_summary', '') or '',
        getattr(t, 'other_summary', '') or '',
        getattr(t, 'ext_summary', '') or '',
        getattr(t, 'usage', '') or '',
    ])).lower()

    # 1. 有明确"投资款"备注
    if any(kw in summary_full for kw in ('投资款', '投资', '入股', '增资')):
        return ('投资款', f'对手方:{cp_name}，摘要:{summary}，备注显示为投资款')

    # 2. 有"借款"备注
    if any(kw in summary_full for kw in ('借款', '借', '贷款', '借入')):
        return ('借款', f'对手方:{cp_name}，摘要:{summary}，备注显示为借款')

    # 3. 社保退款（IBPS对公提回贷记 + 摘要含社保）
    if tx_type == 'IBPS对公提回贷记' and '社保' in summary:
        return ('社保退款', f'社保局退款，冲减原社保支出，对手:{cp_name}，金额:{t.amount}')

    # 4. 老板/股东私人转账（马利英 or 手机转账）
    if cp_name in ('马利英',) or (tx_type == 'IBPS对公提回贷记' and summary == '手机转账'):
        # 无备注 → 待核查
        return ('待核查', f'老板/股东私人转账，对手:{cp_name}，无明确备注，金额:{t.amount}，请核实是借款还是投资款')

    # 5. 其他个人转账，无备注
    if tx_type == 'IBPS对公提回贷记':
        return ('待核查', f'个人转账，对手:{cp_name}，摘要:{summary}，无明确备注，金额:{t.amount}，请核实')

    # 6. 其他情况
    return ('个人往来', f'对手:{cp_name}，摘要:{summary}，金额:{t.amount}')


# ── 1. 交易类型（列7）精准映射 ─────────────────────────────────────────
# 来自文件列7 "交易类型"，优先级最高
TX_TYPE_RULES = {
    # 支出类
    '税款':                   {'direction': 'expense', 'category': '税务',
                               'cp_override': '', 'skip_cp': False,
                               'note': '保留文件原始对手方，从摘要识别税种（社保/个税/增值税等）'},
    '企业银行各项费用':        {'direction': 'expense', 'category': '金融服务',
                               'cp_override': '银行服务费', 'skip_cp': False,
                               'note': '银行服务费，对手方统一为银行服务费'},
    '批量代发付费':           {'direction': 'expense', 'category': 'skip',
                               'note': '银行批量代发手续费，直接跳过'},
    '跨行汇款-普通':          {'direction': 'expense', 'category': '金融服务',
                               'cp_override': '银行服务费', 'skip_cp': False,
                               'note': '跨行转账手续费，对手方显示为银行服务费'},
    '跨行汇款-实时':          {'direction': 'expense', 'category': '金融服务',
                               'cp_override': '银行服务费', 'skip_cp': False,
                               'note': '跨行转账手续费，对手方显示为银行服务费'},
    '转账收费':               {'direction': 'expense', 'category': '金融服务',
                               'cp_override': '银行服务费', 'skip_cp': False,
                               'note': '转账手续费，对手方显示为银行服务费'},
    '行内汇款-普通':          {'direction': 'expense', 'category': 'skip',
                               'note': '行内转账，手续费可忽略'},
    '银承到期扣款':           {'direction': 'expense', 'category': '金融服务',
                               'note': '银承到期'},
    '贷款发放':              {'direction': 'expense', 'category': '借款还款',
                               'note': '贷款发放'},
    '贷款归还':              {'direction': 'expense', 'category': '借款还款',
                               'note': '贷款归还'},
    # 收入类
    '账户结息':              {'direction': 'income',  'category': '利息收入',
                               'cp_override': '银行', 'skip_cp': True,
                               'note': '银行结息，不建档'},
    '企业银行各项费用入账':   {'direction': 'income',  'category': '金融服务',
                               'cp_override': '银行服务费', 'skip_cp': False,
                               'note': '银行费用入账，对手方显示为银行服务费'},
    # IBPS/转账类（看摘要关键词再判断方向和类别）
    'IBPS对公提回贷记':      {'direction': 'income',  'category': 'auto',
                               'note': '看摘要关键词决定最终类别'},
    'IBPS对私提回贷记':      {'direction': 'income',  'category': 'auto',
                               'note': '看摘要关键词决定最终类别'},
    # 行内转账收方
    '行内汇款入账':          {'direction': 'income',  'category': 'auto',
                               'note': '看摘要关键词决定最终类别'},
}

# ── 2. 摘要关键词 → 支出分类（交易类型不适用时的兜底）─────────────────
SUMMARY_EXPENSE_RULES = [
    ('往来',        '往来'),
    ('对公中间业务', 'skip'),
    ('暂收款',      'skip'),
    ('备付金',      'skip'),
    ('应付利息',    'skip'),
    ('应收利息',    'skip'),
    ('货款',        '采购'),
    ('采购',        '采购'),
    ('工资',        '工资'),
    ('代发',        '工资'),
    ('社保费',      '社保公积金'),
    ('公积金',      '社保公积金'),
    ('增值税',      '税务'),
    ('个税',        '税务'),
    ('所得税',      '税务'),
    ('税费',        '税务'),
    ('税',          '税务'),
    ('服务费',      '服务费'),
    ('代理费',      '服务费'),
    ('咨询',        '咨询服务费'),
    ('技术',        '技术服务'),
    ('维护',        '技术服务'),
    ('软件',        '技术服务'),
    ('交通',        '交通差旅'),
    ('油',          '交通差旅'),
    ('过路',        '交通差旅'),
    ('停车',        '交通差旅'),
    ('餐',          '业务招待'),
    ('招待',        '业务招待'),
    ('京东',        '办公用品/网上采购'),
    ('商城',        '办公用品/网上采购'),
    ('天猫',        '办公用品/网上采购'),
    ('淘宝',        '办公用品/网上采购'),
    ('办公',        '办公费用'),
    ('文具',        '办公费用'),
    ('耗材',        '办公费用'),
    ('维修',        '维修维护'),
    ('保养',        '维修维护'),
    ('修理',        '维修维护'),
    ('水费',        '水电物业'),
    ('电费',        '水电物业'),
    ('煤气',        '水电物业'),
    ('燃气',        '水电物业'),
    ('物业',        '水电物业'),
    ('银行',        '金融服务'),
    ('手续费',      '金融服务'),
    ('网上银行',    '金融服务'),
    ('租赁',        '租赁费'),
    ('租金',        '租赁费'),
    ('快递',        '物流快递'),
    ('运输',        '物流快递'),
    ('物流',        '物流快递'),
    ('借款',        '借款还款'),
    ('还款',        '借款还款'),
    ('备用金',      '备用金'),
    ('报销',        '报销'),
    ('医疗',        '社保公积金'),
    ('养老',        '社保公积金'),
    ('失业',        '社保公积金'),
    ('生育',        '社保公积金'),
]

SUMMARY_INCOME_RULES = [
    ('社保费',     '往来'),   # 社保局退款，冲减原社保支出，不算收入
    ('手机转账',   '往来'),   # 私人转账（老板/股东/关联方），不算收入，记往来
    ('退款',        '退款'),
    ('退还款',      '退款'),
    ('货款',        '销售收款'),
    ('销售',        '销售收款'),
    ('收款',        '销售收款'),
    ('收息',        '利息收入'),
    ('结息',        '利息收入'),
    ('利息',        '利息收入'),
    ('软件',        '技术服务费'),
    ('维护',        '技术服务费'),
    ('技术',        '技术服务费'),
    ('咨询',        '咨询服务费'),
    ('培训',        '培训费'),
    ('设备',        '设备销售'),
    ('硬件',        '设备销售'),
    ('租赁',        '租赁收入'),
]

# ── 3. 交易对手主体类型 ────────────────────────────────────────────────
GOV_PATTERNS = [
    r'大学', r'医院', r'政府$', r'委员会', r'局$', r'厅$', r'处$',
    r'事业单位', r'法院', r'检察院', r'管委会',
    r'大学$', r'学院$', r'学校', r'税务局', r'管理局',
]
ENT_PATTERNS = [
    r'公司', r'有限公司', r'有限责任公司', r'集团$', r'科技$',
    r'贸易$', r'实业', r'发展$', r'Co', r'Ltd', r'Inc',
    r'银行$', r'支行$', r'分行$', r'营业部$',
]
BANK_INTERNAL_ACCOUNTS = {
    '对公中间业务收入', '网上其他收入', '网上企业银行',
    '暂收款', '应付利息', '应收利息', '备付金',
    '国家金库', '中华人民共和国国家金库',
}


# ═══════════════════════════════════════════════════════════════════════════
# 分类核心函数
# ═══════════════════════════════════════════════════════════════════════════

def _is_bank_internal(name: str) -> bool:
    """判断是否为银行内部账户（不进档案）"""
    return any(x in name for x in BANK_INTERNAL_ACCOUNTS)


def _is_tax_withhold(name: str, summary: str) -> bool:
    """判断是否为税款代扣代缴（对方=暂收款，摘要含税）"""
    return '暂收款' in name and '税' in summary


def _classify_cp_type(name: str) -> str:
    """判断对方主体类型：enterprise / government / individual"""
    if not name:
        return 'individual'
    for p in GOV_PATTERNS:
        if re.search(p, name):
            return 'government'
    for p in ENT_PATTERNS:
        if re.search(p, name):
            return 'enterprise'
    return 'individual'


def _classify(t: ParsedTransaction) -> dict:
    """
    核心分类函数。
    返回 dict:
      direction, category, counterparty_override,
      skip_cp, cp_type, is_skip_record, is往来
    """
    tx_type  = (t.transaction_type or '').strip()
    summary  = (t.summary or '').strip()
    other_summary = (getattr(t, 'other_summary', '') or '').strip()
    biz_summary   = (getattr(t, 'biz_summary', '') or '').strip()
    ext_summary  = (getattr(t, 'ext_summary', '') or '').strip()
    cp_name  = (t.counterparty_name or '').strip()
    cp_type  = _classify_cp_type(cp_name)
    cp_override = ''
    skip_cp = False
    is_skip = False
    is往来  = False

    # ── 数字钱包兑回/兑出：保留原始对手方（公司自己/数字银行）────────────────
    # 数字货币是公司内部账户间划转，台账需真实记录
    all_texts = [tx_type, summary, other_summary, biz_summary, ext_summary]
    if any('兑回' in s or '兑出' in s for s in all_texts):
        direction_val = 'income' if any('兑回' in s for s in all_texts) else 'expense'
        return dict(
            direction=direction_val,
            category='数字货币',
            counterparty_override='',   # 保留文件原始对手方
            skip_cp=False,
            cp_type=cp_type,
            is_skip_record=False,
            is往来=False,
        )

    # 1) 命中交易类型规则
    rule = TX_TYPE_RULES.get(tx_type)
    if rule:
        direction = rule['direction']
        category  = rule['category']
        cp_override = rule.get('cp_override', '')
        skip_cp    = rule.get('skip_cp', False)

        # auto 类型：按摘要关键词重新判断
        if category == 'auto':
            if direction == 'income':
                for kw, cat in SUMMARY_INCOME_RULES:
                    if kw in summary:
                        category = cat
                        break
                else:
                    category = '其他收入'
            else:
                for kw, cat in SUMMARY_EXPENSE_RULES:
                    if kw in summary:
                        category = cat
                        break
                else:
                    category = '其他费用'

        # skip 整条记录（如批量代发付费）
        if category == 'skip':
            is_skip = True

        # 往来款：记 BankStatement，但不计 Income/Expense
        if category == '往来':
            is往来 = True
            往来_type, 往来_remark = _detect_往来_subtype(
                cp_name, summary, tx_type, t)
        else:
            往来_type, 往来_remark = '', ''

        # ── 后处理：税款对手方为"暂收款"时，改为"税务局"+识别具体税种 ────────
        if category == '税务' and cp_name == '暂收款':
            tax_type = _detect_tax_subtype(summary, t)
            # 从摘要提取税种，摘要本身含税种关键词（如"社保"、"个税"）
            if tax_type:
                category = tax_type
            # 对手方改为税务局
            cp_name = '税务局'
            cp_override = '税务局'

        return dict(
            direction=direction, category=category,
            counterparty_override=cp_override, skip_cp=skip_cp,
            cp_type=cp_type, is_skip_record=is_skip, is往来=is往来,
            往来_type=往来_type, 往来_remark=往来_remark,
        )

    # 2) 兜底：摘要关键词
    if cp_type == 'income':
        for kw, cat in SUMMARY_INCOME_RULES:
            if kw in summary:
                return dict(direction='income', category=cat,
                            counterparty_override='', skip_cp=False,
                            cp_type=cp_type, is_skip_record=False, is往来=False)
    else:
        for kw, cat in SUMMARY_EXPENSE_RULES:
            if kw in summary:
                if cat == '往来':
                    return dict(direction='expense', category='往来',
                                counterparty_override='', skip_cp=False,
                                cp_type=cp_type, is_skip_record=False, is往来=True)
                if cat == 'skip':
                    return dict(direction='expense', category='其他费用',
                                counterparty_override='', skip_cp=True,
                                cp_type=cp_type, is_skip_record=True, is往来=False)
                return dict(direction='expense', category=cat,
                            counterparty_override='', skip_cp=False,
                            cp_type=cp_type, is_skip_record=False, is往来=False)

    # 3) 默认
    direction = 'income' if cp_type == 'income' else 'expense'
    category  = '其他收入' if direction == 'income' else '其他费用'
    return dict(direction=direction, category=category,
                counterparty_override='', skip_cp=False,
                cp_type=cp_type, is_skip_record=False, is往来=False)


# ═══════════════════════════════════════════════════════════════════════════
# 交易对手档案处理（统一 Client/Supplier，含银行信息）
# ═══════════════════════════════════════════════════════════════════════════

def _upsert_counterparty(company, cp_name: str, cp_account: str, cp_bank: str, cp_type: str, direction: str):
    """
    自动创建或更新 Client / Supplier 档案。
    同一企业可以是客户也可以是供应商（双向交易）。
    - direction=income → upsert Client（对手是客户）
    - direction=expense → upsert Supplier（对手是供应商）
    - 如果对手已存在于另一张表，同时创建双向档案
    """
    name    = cp_name.strip()
    account = cp_account.strip()
    bank    = cp_bank.strip()
    defaults = {'counterparty_type': cp_type, 'created_by': None}

    if not name:
        return None

    # 银行信息（只更新空字段，不覆盖已有数据）
    bank_updates = {}
    if account:
        bank_updates['bank_account'] = account
    if bank:
        bank_updates['bank_name'] = bank

    if direction == 'income':
        # 对方是客户 → 写入Client
        client, created = Client.objects.get_or_create(
            company=company, name=name, defaults=defaults)
        if bank_updates:
            for k, v in bank_updates.items():
                if not getattr(client, k):
                    setattr(client, k, v)
            client.save(update_fields=list(bank_updates.keys()))

        # 如果该对手已存在于Supplier表，也建Client档案（双向交易）
        if Supplier.objects.filter(company=company, name=name).exists():
            if not Client.objects.filter(company=company, name=name).exists():
                Client.objects.get_or_create(company=company, name=name, defaults={**defaults, **bank_updates})
        return client

    else:
        # 对方是供应商 → 写入Supplier
        supplier, created = Supplier.objects.get_or_create(
            company=company, name=name, defaults=defaults)
        if bank_updates:
            for k, v in bank_updates.items():
                if not getattr(supplier, k):
                    setattr(supplier, k, v)
            supplier.save(update_fields=list(bank_updates.keys()))

        # 如果该对手已存在于Client表，也建Supplier档案（双向交易）
        if Client.objects.filter(company=company, name=name).exists():
            if not Supplier.objects.filter(company=company, name=name).exists():
                Supplier.objects.get_or_create(company=company, name=name, defaults={**defaults, **bank_updates})
        return supplier


# ═══════════════════════════════════════════════════════════════════════════
# Payment Reconciliation — 银行流水自动核销发票
# ═══════════════════════════════════════════════════════════════════════════

def _reconcile_bank_statement(bs: BankStatement):
    """
    银行流水写入后，自动核销对应发票。

    收入类流水（对方打款）→ 核销 type='income' 的待收款发票（AR）
    支出类流水（我方打款）→ 核销 type='expense' 的待付款发票（AP）

    匹配逻辑（三个条件全部满足）：
    1. 对方名称包含匹配（Invoice.counterparty 包含 BankStatement.counterparty_name）
    2. 金额完全相等
    3. 日期容差 ±5天

    核销动作：
    - Invoice.status → 'paid'
    - Invoice.payment_date → 交易日期
    - Invoice.matched_bank_statement → 本条 BankStatement
    - BankStatement.reconcile_status → 'matched'
    - BankStatement.reconcile_time → now
    - BankStatement.matched_income / matched_expense → 对应记录
    """
    direction = bs.direction
    cp_name = (bs.counterparty_name or '').strip()
    amount = bs.amount
    tx_date = bs.transaction_date

    if direction == 'income':
        # 收入类：找 type='income' + status='pending' 的待收款发票
        candidates = Invoice.objects.filter(
            type='income',
            status='pending',
            company=bs.company,
        ).exclude(payment_date__isnull=False)  # 排除已核销的

        # 过滤：对方名称匹配（包含匹配，宽松）
        if cp_name:
            candidates = candidates.filter(counterparty__icontains=cp_name)

        # 金额匹配
        candidates = candidates.filter(amount=amount)

        # 日期容差 ±5天
        from datetime import timedelta
        date_min = tx_date - timedelta(days=5)
        date_max = tx_date + timedelta(days=5)
        candidates = candidates.filter(issue_date__range=(date_min, date_max))

        # 取最早的一条
        matched = candidates.order_by('issue_date', 'id').first()

        if matched:
            # 核销收入发票（AR）
            matched.status = 'paid'
            matched.payment_date = tx_date
            matched.matched_bank_statement = bs
            matched.save(update_fields=['status', 'payment_date', 'matched_bank_statement'])

            # 更新流水核销标记
            bs.reconcile_status = 'matched'
            bs.reconcile_time = timezone.now()
            bs.matched_income = Income.objects.filter(
                company=bs.company,
                customer=cp_name,
                amount=amount,
                date=tx_date
            ).first()
            bs.save(update_fields=[
                'reconcile_status', 'reconcile_time', 'matched_income'
            ])
            return matched, 'ar'
        return None, None

    else:
        # 支出类：找 type='expense' + status='pending' 的待付款发票
        candidates = Invoice.objects.filter(
            type='expense',
            status='pending',
            company=bs.company,
        ).exclude(payment_date__isnull=False)

        if cp_name:
            candidates = candidates.filter(counterparty__icontains=cp_name)

        candidates = candidates.filter(amount=amount)

        from datetime import timedelta
        date_min = tx_date - timedelta(days=5)
        date_max = tx_date + timedelta(days=5)
        candidates = candidates.filter(issue_date__range=(date_min, date_max))

        matched = candidates.order_by('issue_date', 'id').first()

        if matched:
            matched.status = 'paid'
            matched.payment_date = tx_date
            matched.matched_bank_statement = bs
            matched.save(update_fields=['status', 'payment_date', 'matched_bank_statement'])

            bs.reconcile_status = 'matched'
            bs.reconcile_time = timezone.now()
            bs.matched_expense = Expense.objects.filter(
                company=bs.company,
                supplier=cp_name,
                amount=amount,
                expense_date=tx_date
            ).first()
            bs.save(update_fields=[
                'reconcile_status', 'reconcile_time', 'matched_expense'
            ])
            return matched, 'ap'
        return None, None


def match_counterparty(t: ParsedTransaction, company):
    """智能匹配已有的 Client / Supplier 档案。"""
    name    = t.counterparty_name.strip()
    account = t.counterparty_account.strip()

    if not name and not account:
        return '', ''

    if name:
        c = Client.objects.filter(company=company, name=name).first()
        if c:
            return 'client', c.name
        s = Supplier.objects.filter(company=company, name=name).first()
        if s:
            return 'supplier', s.name

    if account:
        c = Client.objects.filter(company=company, contact_phone__contains=account).first()
        if c:
            return 'client', c.name

    return '', ''


# ═══════════════════════════════════════════════════════════════════════════
# API 接口
# ═══════════════════════════════════════════════════════════════════════════

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def list_banks(request):
    banks = [{'code': cls().bank_code, 'name': cls().bank_name}
             for cls in ALL_ADAPTERS]
    return Response({'banks': banks})


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def preview_bank_statement(request):
    """预览银行流水（不写库），返回11个核心字段。"""
    import base64

    content_type = request.content_type or ''
    if 'application/json' in content_type or (
        hasattr(request, 'data') and isinstance(request.data, dict)
        and 'file_base64' in request.data
    ):
        body       = request.data
        company_id = body.get('company_id')
        bank_code  = body.get('bank_code', '')
        try:
            content = base64.b64decode(body.get('file_base64', ''))
        except Exception as e:
            return Response({'error': f'文件解码失败: {e}'}, status=400)
    else:
        if 'file' not in request.FILES:
            return Response({'error': '请上传文件'}, status=400)
        company_id = request.data.get('company_id') or request.data.get('company')
        bank_code   = request.data.get('bank_code', '')
        content     = request.FILES['file'].read()

    if not company_id:
        return Response({'error': '缺少 company_id'}, status=400)

    try:
        company = Company.objects.get(id=company_id)
    except Company.DoesNotExist:
        return Response({'error': '公司不存在'}, status=400)

    try:
        if bank_code:
            transactions = parse_with_adapter(content, bank_code)
            used_bank = bank_code
        else:
            used_bank, transactions = detect_and_parse(content)
    except ValueError as e:
        return Response({'error': str(e)}, status=400)
    except Exception as e:
        return Response({'error': f'解析失败: {type(e).__name__}: {e}'}, status=500)

    preview_rows  = []
    total_income  = Decimal('0')
    total_expense = Decimal('0')

    for t in transactions:
        direction = t.direction

        if direction == 'income':
            total_income += t.amount
        else:
            total_expense += t.amount

        # 客户/供应商智能匹配
        match_type, match_name = match_counterparty(t, company)

        # 自动分类描述
        category = direction == 'income' and '收入' or '支出'
        if hasattr(t, 'auto_category') and t.auto_category:
            category = t.auto_category
        elif hasattr(t, 'category') and t.category:
            category = t.category

        preview_rows.append({
            'transaction_date':    t.transaction_date.isoformat() if t.transaction_date else '',
            'transaction_time':   t.transaction_time.isoformat() if t.transaction_time else '',
            'direction':          direction,
            'direction_display':  '收入' if direction == 'income' else '支出',
            'amount':             str(t.amount),
            'balance':            str(t.balance) if t.balance else '',
            'counterparty_name':  t.counterparty_name,
            'counterparty_account': t.counterparty_account,
            'counterparty_bank':  t.counterparty_bank,
            'summary':            t.summary[:200] if t.summary else '',
            'bank_serial':        t.bank_serial,
            'transaction_type':   t.transaction_type,
            'auto_description':   category,
            'match_type':         match_type,
            'match_name':         match_name,
        })

    return Response({
        'bank_code':    used_bank,
        'total_count':  len(transactions),
        'total_income': str(total_income),
        'total_expense':str(total_expense),
        'preview_rows': preview_rows[:200],
        'has_more':     len(transactions) > 200,
    })


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def confirm_bank_import(request):
    """
    确认导入银行流水。
    原则：文件有多少行就写多少行，不跳、不过滤、不分类。
    每行 → BankStatement + Income（贷）或 Expense（借）。
    source / expense_category 直接存文件的原始交易类型文本。
    """
    body = request.data
    company_id = body.get('company_id')
    bank_code  = body.get('bank_code', '')
    rows       = body.get('transactions', []) or body.get('rows', [])

    if not rows:
        return Response({'error': '没有要导入的流水记录，请先上传文件预览'}, status=400)
    if not company_id:
        return Response({'error': '缺少 company_id'}, status=400)

    try:
        company = Company.objects.get(id=company_id)
    except Company.DoesNotExist:
        return Response({'error': '公司不存在'}, status=400)

    # ── 银行账户（优先级：bank_account_id > account_no 精确查找 > 新建） ──
    bank_account = None
    ba_id   = body.get('bank_account_id', '')
    ba_no   = body.get('account_no', '').strip()
    ba_name = body.get('account_name', '').strip()
    ba_code = body.get('bank_code', '')

    if ba_id:
        bank_account = BankAccount.objects.filter(id=ba_id, company=company).first()
        if not bank_account:
            return Response({'error': '所选银行账户不存在'}, status=400)
    elif ba_no:
        bank_account = BankAccount.objects.filter(company=company, account_no=ba_no).first()
        if not bank_account and ba_name:
            bank_account, _ = BankAccount.objects.get_or_create(
                company=company, account_no=ba_no,
                defaults={'bank_code': ba_code or 'OTHER', 'bank_name': '', 'account_name': ba_name}
            )
    else:
        return Response({'error': '请选择已有银行账户，或填写新账户的账号和户名'}, status=400)

    income_count = expense_count = 0
    income_sum = expense_sum = Decimal('0')
    skipped = 0
    errors = []
    batch_id = uuid.uuid4().hex[:12].upper()

    for row in rows:
        try:
            t_date     = row.get('transaction_date', '')
            t_time     = row.get('transaction_time', '')
            amount     = Decimal(str(row.get('amount', '0')))
            direction  = row.get('direction', '')
            cp_name    = row.get('counterparty_name', '').strip()
            cp_account = row.get('counterparty_account', '').strip()
            cp_bank    = row.get('counterparty_bank', '').strip()
            summary    = row.get('summary', '')[:500]
            serial     = row.get('bank_serial', '')
            tx_type    = row.get('transaction_type', '')[:100]

            # 解析日期
            if isinstance(t_date, str) and t_date:
                if 'T' in t_date:
                    t_date = t_date.split('T')[0]
                tx_date = datetime.datetime.strptime(t_date, '%Y-%m-%d').date()
            else:
                tx_date = datetime.date.today()

            # 解析时间
            tx_time = None
            if t_time:
                try:
                    if 'T' in t_time:
                        t_time = t_time.split('T')[1][:8]
                    tx_time = datetime.datetime.strptime(t_time[:8], '%H:%M:%S').time()
                except ValueError:
                    tx_time = None

            # 去重
            dedup = serial or f"{tx_date}_{cp_account}_{amount}"
            if BankStatement.objects.filter(company=company, bank_serial=dedup).exists():
                skipped += 1
                continue

            # ── 智能匹配客户/供应商 ─────────────────────────────
            # 只有匹配到真实档案才写入customer/supplier，
            # "个人""银行利息"等对手方不写入，避免污染档案字段
            _row = type('ParsedTransaction', (), {
                'counterparty_name': cp_name,
                'counterparty_account': cp_account,
            })()
            match_type, match_name = match_counterparty(_row, company)

            # ── 写 Income / Expense ─────────────────────────────
            if direction == 'income':
                inc = Income.objects.create(
                    company=company,
                    customer=match_name if match_type == 'client' else '',
                    source=tx_type,
                    amount=amount,
                    date=tx_date,
                    description=summary,
                    # ── 银行流水11字段扩展 ─────────────────────────────
                    transaction_time=tx_time,
                    balance=Decimal(row['balance']) if row.get('balance') else None,
                    counterparty_account=cp_account,
                    counterparty_bank=cp_bank,
                    transaction_type=tx_type,
                    summary=summary,
                )
                income_count += 1
                income_sum += amount
                inc_obj, exp_obj = inc, None
            else:
                exp = Expense.objects.create(
                    company=company,
                    supplier=match_name if match_type == 'supplier' else '',
                    expense_type='other',
                    expense_category=tx_type,
                    amount=amount,
                    expense_date=tx_date,
                    description=summary,
                    note=f"流水号:{serial}" if serial else '',
                    # ── 银行流水11字段扩展 ─────────────────────────────
                    transaction_time=tx_time,
                    balance=Decimal(row['balance']) if row.get('balance') else None,
                    counterparty_account=cp_account,
                    counterparty_bank=cp_bank,
                    transaction_type=tx_type,
                    summary=summary,
                )
                expense_count += 1
                expense_sum += amount
                inc_obj, exp_obj = None, exp

            # ── 写 BankStatement ──────────────────────────────────────
            bs = BankStatement.objects.create(
                company=company,
                bank_account=bank_account,
                bank_serial=dedup,
                transaction_date=tx_date,
                transaction_time=tx_time,
                direction=direction,
                amount=amount,
                balance=Decimal(row['balance']) if row.get('balance') else None,
                counterparty_name=cp_name,
                counterparty_account=cp_account,
                counterparty_bank=cp_bank,
                summary=summary,
                import_batch=batch_id,
                transaction_type=tx_type,
                matched_income=inc_obj,
                matched_expense=exp_obj,
            )

            # ── 自动核销发票 ─────────────────────────────────────────
            try:
                _reconcile_bank_statement(bs)
            except Exception as rec_err:
                errors.append(f"核销异常 {tx_date}: {rec_err}")

        except Exception as e:
            errors.append(f"行 {row.get('transaction_date','')} {row.get('counterparty_name','')}: {e}")

    return Response({
        'batch_no':    batch_id,
        'imported':    income_count + expense_count,
        'skipped':     skipped,
        'auto_created': {
            'income_count':  income_count,
            'expense_count': expense_count,
        },
        'income_sum':   str(income_sum),
        'expense_sum':  str(expense_sum),
        'errors':       errors[:20],
    })
