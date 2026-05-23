"""
银行流水导入视图 v2.0 — CMB 36列全量解析
POST /api/finance/import/bank-statement/        — 预览（不写库）
POST /api/finance/import/bank-statement/confirm/ — 确认导入
GET  /api/finance/import/bank-statement/banks/  — 支持的银行列表
"""
from apps.core.audit import pause_audit, resume_audit
import datetime
import os
import re
import uuid
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from apps.core.permissions import require_perms
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.finance.bank_adapters import (
    ALL_ADAPTERS, detect_and_parse, parse_with_adapter, detect_with_adapter, ParsedTransaction,
    XlrdSheetWrapper,
)
import xlrd
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
    自动创建或更新 Client / Supplier 档案（独立事务，不干扰调用方事务）。
    同一企业可以是客户也可以是供应商（双向交易）。
    - direction=income → upsert Client（对手是客户）
    - direction=expense → upsert Supplier（对手是供应商）
    - 如果对手已存在于另一张表，同时创建双向档案
    所有 DB 操作被 try-except 包裹，失败不影响主流程。
    """
    name    = cp_name.strip()
    account = cp_account.strip()
    bank    = cp_bank.strip()
    # 注意：created_by=None 表示匿名创建，不传该字段让 ORM 使用模型默认值
    base_fields = {'counterparty_type': cp_type}

    if not name:
        return None

    # 银行信息（只更新空字段，不覆盖已有数据）
    bank_updates = {}
    if account:
        bank_updates['bank_account'] = account
    if bank:
        parsed = _parse_bank_info(bank)
        if parsed['bank_name']:
            bank_updates.setdefault('bank_name', parsed['bank_name'])
        if parsed['bank_branch']:
            bank_updates['bank_branch'] = parsed['bank_branch']

    try:
        if direction == 'income':
            # 对方是客户 → 写入Client
            client, created = Client.objects.get_or_create(
                company=company, name=name, defaults=base_fields)
            if bank_updates and created:
                for k, v in bank_updates.items():
                    if not getattr(client, k):
                        setattr(client, k, v)
                Client.objects.filter(pk=client.pk).update(**bank_updates)
            # 双向交易：如果该对手已存在于Supplier表，也建Client档案
            if Supplier.objects.filter(company=company, name=name).exists():
                Client.objects.get_or_create(
                    company=company, name=name, defaults=base_fields)
            return client
        else:
            # 对方是供应商 → 写入Supplier
            supplier, created = Supplier.objects.get_or_create(
                company=company, name=name, defaults=base_fields)
            if bank_updates and created:
                for k, v in bank_updates.items():
                    if not getattr(supplier, k):
                        setattr(supplier, k, v)
                Supplier.objects.filter(pk=supplier.pk).update(**bank_updates)
            # 双向交易：如果该对手已存在于Client表，也建Supplier档案
            if Client.objects.filter(company=company, name=name).exists():
                Supplier.objects.get_or_create(
                    company=company, name=name, defaults=base_fields)
            return supplier
    except Exception:
        return None


@api_view(['POST'])
# Payment Reconciliation — 银行流水自动核销发票
# ═══════════════════════════════════════════════════════════════════════════

def _reconcile_invoice(bs, cp_name, amount, tx_date,
                        pending_income_invoices, pending_expense_invoices,
                        date_tolerance=5):
    """
    用预加载的发票列表做内存匹配（零DB查询），核销对应的待处理发票。

    收入类流水（对方打款）→ 在 pending_income_invoices 中找
        type=income + counterparty含cp_name + 金额相等 + 日期±N天
    支出类流水（我方打款）→ 在 pending_expense_invoices 中找
        type=expense + counterparty含cp_name + 金额相等 + 日期±N天

    命中后：
      Invoice.status → 'paid'
      Invoice.payment_date → tx_date
      Invoice.matched_bank_statement → bs
      BankStatement.reconcile_status → 'matched'
      BankStatement.reconcile_time → now
    """
    from datetime import timedelta as td
    date_min = tx_date - td(days=date_tolerance)
    date_max = tx_date + td(days=date_tolerance)

    candidates = (pending_income_invoices if bs.direction == 'income'
                 else pending_expense_invoices)

    for inv in candidates:
        if inv.payment_date:  # 已核销，跳过
            continue
        if str(inv.amount) != str(amount):
            continue
        if not (date_min <= inv.issue_date <= date_max):
            continue
        # 对方名称含匹配（宽松）
        inv_cp = (inv.counterparty or '').strip()
        if inv_cp and cp_name and inv_cp.find(cp_name) >= 0:
            matched_inv = inv
            break
        # 逆向包含：cp_name 较短时，检查 inv.counterparty 是否含 cp_name
        if inv_cp and cp_name and len(cp_name) <= len(inv_cp):
            if inv_cp.find(cp_name) >= 0:
                matched_inv = inv
                break
    else:
        return  # 未匹配

    # 核销
    matched_inv.status = 'paid'
    matched_inv.payment_date = tx_date
    matched_inv.matched_bank_statement = bs
    matched_inv.save(update_fields=['status', 'payment_date', 'matched_bank_statement'])

    bs.reconcile_status = 'matched'
    bs.reconcile_time = timezone.now()
    bs.save(update_fields=['reconcile_status', 'reconcile_time'])


# 公司/组织常见后缀（人名不含这些）
COMPANY_SUFFIXES = ['公司', '集团', '有限', '责任', '企业', '工厂', '酒店',
                     '中心', '医院', '学校', '银行', '支行', '分部', '事务所',
                     '经营部', '服务部', '营业部', '办事处', '门市', '商店',
                     '科技', '实业', '商贸', '贸易', '工程', '传媒']

# 银行名称前缀（总行），用于从完整支行地址中提取总行名
BANK_NAME_PREFIXES = [
    '中国银行', '中国农业银行', '中国工商银行', '中国建设银行', '中国交通银行',
    '招商银行', '浦发银行', '光大银行', '民生银行', '中信银行', '华夏银行',
    '广发银行', '平安银行', '兴业银行', '浙商银行', '恒丰银行', '渤海银行',
    '深圳农村商业银行', '农村商业银行', '农村信用合作社', '中国邮政储蓄银行',
    '上海银行', '北京银行', '广州银行', '东莞银行', '惠州银行',
    '交通银行', '国家金库', '中国人民银行',
]

# 排除词（命中即不建档、不写进对手方字段）
EXCLUDED_CP_PATTERNS = [
    # 银行内部/系统账户（不应建档）
    '个人', '利息', '结算', '转账', '充值', '提现', '退款',
    '备用金', '内部户', '过渡户', '暂挂户', '备付金',
    '税款', '社保', '公积金', '代发', '代扣',
    '暂收款', '对公中间业务收入', '中间业务收入',
    '应付利息', '单位活期存款利息', '自动计提',
    # 政府/税务类：现在可以建真实档案了（移除了税务局/财政/国库）
    # 特殊标识后缀：去除(1)/(2)/(3)，因为龙华区税务局（1）是真实对手方
]

def _is_personal_name(name: str) -> bool:
    """判断是否为自然人姓名（2-6个汉字，无公司后缀，无数字/字母混排）。"""
    import re
    if not name:
        return False
    # 纯中文，2-6个字符（覆盖常见姓名）
    if not re.fullmatch(r'[\u4e00-\u9fff]{2,6}', name):
        return False
    # 含数字或字母 → 不是人名
    if re.search(r'[a-zA-Z0-9]', name):
        return False
    # 不含公司后缀
    for suf in COMPANY_SUFFIXES:
        if suf in name:
            return False
    return True

def _parse_bank_info(cp_bank: str) -> dict:
    """
    解析完整支行地址，返回 {bank_name, bank_branch}。
    例如：
      '中国银行上海市长宁支行' → bank_name='中国银行', bank_branch='上海市长宁支行'
      '中国农业银行'           → bank_name='中国农业银行', bank_branch=''
      '招商银行深圳分行深圳民治支行' → bank_name='招商银行', bank_branch='深圳民治支行'
      ''                       → bank_name='', bank_branch=''
    """
    if not cp_bank:
        return {'bank_name': '', 'bank_branch': ''}
    # 按前缀从长到短排序，确保优先匹配最长前缀
    for prefix in sorted(BANK_NAME_PREFIXES, key=len, reverse=True):
        if cp_bank.startswith(prefix):
            branch = cp_bank[len(prefix):]
            # 清理支行名称常见冗余词
            for redundant in ['分行', '支行', '营业部']:
                if branch.endswith(redundant):
                    branch = branch[:-len(redundant)]
            return {'bank_name': prefix, 'bank_branch': branch}
    # 没有匹配到已知银行前缀，整体作为支行名
    return {'bank_name': '', 'bank_branch': cp_bank}

def _is_excluded_counterparty(name: str) -> bool:
    """判断对手方名称是否属于不应建档的类型（银行内部账户、个人转账、自然人、空名称）。"""
    if not name or not name.strip():
        return True  # 空名称不建档
    for p in EXCLUDED_CP_PATTERNS:
        if p in name:
            return True
    # 自然人姓名（2-4字纯中文，无公司后缀）不建档
    if _is_personal_name(name):
        return True
    return False


def match_counterparty(t: ParsedTransaction, company):
    """智能匹配已有的 Client / Supplier 档案。"""
    name    = t.counterparty_name.strip()
    account = t.counterparty_account.strip()

    if not name and not account:
        return '', ''

    if name:
        # 精确匹配优先（跨公司查找，名称相同即为同一主体）
        c = Client.objects.filter(name=name).first()
        if c:
            return 'client', c.name
        s = Supplier.objects.filter(name=name).first()
        if s:
            return 'supplier', s.name

        # 排除词命中的不继续匹配（防止"个人""银行利息"类污染档案）
        if _is_excluded_counterparty(name):
            return '', ''

        # 子串包含匹配（真实客户名可能包含在对手方文本中，跨公司）
        c = Client.objects.filter(name__contains=name).first()
        if c:
            return 'client', c.name
        s = Supplier.objects.filter(name__contains=name).first()
        if s:
            return 'supplier', s.name

    if account:
        c = Client.objects.filter(contact_phone__contains=account).first()
        if c:
            return 'client', c.name

    return '', ''


# ═══════════════════════════════════════════════════════════════════════════
# API 接口
# ═══════════════════════════════════════════════════════════════════════════

@api_view(['GET'])
@require_perms('bank:import')
def list_banks(request):
    banks = [{'code': cls().bank_code, 'name': cls().bank_name}
             for cls in ALL_ADAPTERS]
    return Response({'banks': banks})


@api_view(['POST'])
@require_perms('bank:import')
def preview_bank_statement(request):
    """预览银行流水（不写库），返回11个核心字段。"""
    import base64
    import os

    content_type = request.content_type or ''
    if 'application/json' in content_type or (
        hasattr(request, 'data') and isinstance(request.data, dict)
        and 'file_base64' in request.data
    ):
        body       = request.data
        company_id = body.get('company_id')
        bank_code  = body.get('bank_code', '')
        expect_bank_code = body.get('expect_bank_code', '')  # 用户所选账户的银行类型
        try:
            raw_b64 = body.get('file_base64', '')
            content = base64.b64decode(raw_b64)
            # 调试日志
            with open('/tmp/bank_debug.log', 'a') as f:
                f.write(f'raw_b64_len={len(raw_b64)} first10={raw_b64[:10]} decoded_len={len(content)} first_bytes={content[:20].hex()}\n')
        except Exception as e:
            with open('/tmp/bank_debug.log', 'a') as f:
                f.write(f'decode_error: {e}\n')
            return Response({'error': f'文件解码失败: {e}'}, status=400)
    else:
        if 'file' not in request.FILES:
            return Response({'error': '请上传文件'}, status=400)
        company_id = request.data.get('company_id') or request.data.get('company')
        bank_code   = request.data.get('bank_code', '')
        content     = request.FILES['file'].read()
        expect_bank_code = request.data.get('expect_bank_code', '')

    if not company_id:
        return Response({'error': '缺少 company_id'}, status=400)

    try:
        company = Company.objects.get(id=company_id)
    except Company.DoesNotExist:
        return Response({'error': '公司不存在'}, status=400)

    # ── 银行账户归属校验（两层）────────────────────────────────────────
    # 用 bank_account_id 查账户，获取其所属公司和银行类型
    bank_account_id_raw = request.data.get('bank_account_id')
    # bank_account_id 可以是 None（未传）、''（清空） 或具体数字
    # 只有传了具体数字才做账户归属校验
    if bank_account_id_raw is not None and bank_account_id_raw != '' and str(bank_account_id_raw).isdigit():
        bank_account_id = int(bank_account_id_raw)
        try:
            bank_account = BankAccount.objects.select_related('company').get(id=bank_account_id)
        except BankAccount.DoesNotExist:
            return Response({'error': '银行账户不存在'}, status=400)

        # 校验1：账户所属公司 ≠ 当前选的公司
        if bank_account.company_id != int(company_id):
            return Response({
                'error': f'您选择的是 [{bank_account.company.name}] 的账户 [{bank_account.account_no}]，'
                         f'但当前选的公司是 [{company.name}]，请重新选择公司或账户'
            }, status=400)

        # 校验2：账户银行类型 ≠ 文件实际格式（支持 xlsx 和 xls）
        detected_bank = None
        import io
        try:
            # 先尝试 openpyxl（xlsx 格式）
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
            ws = wb.active
            for cls in ALL_ADAPTERS:
                if cls().detect(ws):
                    detected_bank = cls.bank_code
                    break
        except Exception:
            try:
                # 降级到 xlrd（xls 格式）
                xlrd_wb = xlrd.open_workbook(file_contents=content)
                xlrd_ws = XlrdSheetWrapper(xlrd_wb.sheet_by_index(0))
                for cls in ALL_ADAPTERS:
                    if cls().detect(xlrd_ws):
                        detected_bank = cls.bank_code
                        break
            except Exception:
                pass
        if detected_bank and detected_bank != bank_account.bank_code and detected_bank != ('PINGAN' if bank_account.bank_code == 'PA' else bank_account.bank_code):
            bank_display_map = {
                'CMB': '招商银行', 'ICBC': '工商银行', 'CCB': '建设银行',
                'BOC': '中国银行', 'ABC': '农业银行', 'COMM': '交通银行',
                'PSBC': '邮储银行', 'PINGAN': '平安银行', 'PA': '平安银行',
            }
            file_name = bank_display_map.get(detected_bank, detected_bank)
            account_name = bank_display_map.get(bank_account.bank_code, bank_account.bank_code)
            return Response({
                'error': f'您选择的账户是 [{account_name}]，但上传的文件是 [{file_name}] 格式，请重新选择正确的银行账户'
            }, status=400)

    # ── 银行格式强校验（两层合并）────────────────────────────────────────
    # 场景1：选了已有账户 → expect_bank_code = 账户银行类型
    # 场景2：新建账户+明确选银行 → bank_code = 用户所选银行
    # 两种情况都用 detect_with_adapter() 校验文件格式，不匹配则拒绝预览
    # ── 银行格式校验 ─────────────────────────────────────────────────
    # bank_account_id 传入时，validate_bank_code 必须取自账户银行类型（防止前端传空）
    _account_bank_code = ''
    if bank_account_id_raw is not None and str(bank_account_id_raw).isdigit() and bank_account:
        _account_bank_code = bank_account.bank_code

    validate_bank_code = expect_bank_code or _account_bank_code or (bank_code if bank_code not in ('', 'OTHER') else '')

    if validate_bank_code:
        matched = detect_with_adapter(content, validate_bank_code)
        if not matched:
            bank_display_map = {
                'CMB': '招商银行', 'ICBC': '工商银行', 'CCB': '建设银行',
                'BOC': '中国银行', 'ABC': '农业银行', 'COMM': '交通银行',
                'PSBC': '邮储银行', 'PINGAN': '平安银行', 'PA': '平安银行',
            }
            expected_name = bank_display_map.get(validate_bank_code, validate_bank_code)
            # 自动识别实际格式，给用户明确提示
            detected_bank = None
            try:
                import openpyxl
                wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
                ws = wb.active
                for cls in ALL_ADAPTERS:
                    if cls().detect(ws):
                        detected_bank = bank_display_map.get(cls.bank_code, cls.bank_code)
                        break
            except Exception:
                try:
                    xlrd_wb = xlrd.open_workbook(file_contents=content)
                    xlrd_ws = XlrdSheetWrapper(xlrd_wb.sheet_by_index(0))
                    for cls in ALL_ADAPTERS:
                        if cls().detect(xlrd_ws):
                            detected_bank = bank_display_map.get(cls.bank_code, cls.bank_code)
                            break
                except Exception:
                    pass
            if detected_bank:
                hint = f'您选择的是 [{expected_name}]，但上传的文件似乎是 [{detected_bank}] 格式，请重新选择正确的银行对账单'
            else:
                hint = f'您选择的是 [{expected_name}]，但上传的文件无法识别，请确认文件是银行对账单格式'
            return Response({'error': hint}, status=400)

    # ── 解析（已通过格式校验）───────────────────────────────────────────
    try:
        if validate_bank_code:
            transactions = parse_with_adapter(content, validate_bank_code)
            used_bank = validate_bank_code
        else:
            used_bank, transactions = detect_and_parse(content)
    except ValueError as e:
        return Response({'error': str(e)}, status=400)
    except Exception as e:
        return Response({'error': f'解析失败: {type(e).__name__}: {e}'}, status=500)

    # ── 公司账号精确匹配校验（选了已有账户时）────────────────────────────────
    if bank_account_id_raw is not None and str(bank_account_id_raw).isdigit() and transactions:
        file_account_no = getattr(transactions[0], 'account_no', '') if transactions else ''
        if file_account_no and file_account_no != bank_account.account_no:
            return Response({
                'error': f'上传的文件属于账号 [{file_account_no}]，'
                         f'但您选择的是 [{bank_account.account_no}]，两者不匹配，请重新选择账户或上传正确的文件'
            }, status=400)

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

    # 不截断：全部返回，让前端处理大数据量（如需分页可后续扩展）
    return Response({
        'bank_code':    used_bank,
        'total_count':  len(transactions),
        'total_income': str(total_income),
        'total_expense':str(total_expense),
        'preview_rows': preview_rows,
    })


def _safe_int(val):
    """将带逗号的数字字符串安全转为int"""
    try:
        return int(str(val).replace(',', ''))
    except (ValueError, TypeError):
        return None


@api_view(['POST'])
@require_perms('bank:import')
def confirm_bank_import(request):
    """
    确认导入银行流水 — 全原子事务版。

    架构原则：
    1. 每行数据（三张表：Income/Expense + BankStatement）在同一事务内创建，
       任一失败则整行回滚，不产生脏数据。
    2. 审计日志通过 transaction.on_commit() 延迟写入，不在 atomic 块内同步执行，
       避免审计日志失败污染主业务事务。
    3. 去重检查在事务外，避免不必要的锁。
    4. 发票核销：收入流水的对方名称 → Invoice.counterparty（含匹配），
       支出流水的对方名称 → Invoice.counterparty（含匹配）。
    5. 幂等日志：每次调用覆盖日志文件，精准定位本次问题。
    """
    pause_audit()
    try:
        body = request.data
        company_id = body.get('company_id')
        rows       = body.get('transactions', []) or body.get('rows', [])
    
        if not rows:
            return Response({'error': '没有要导入的流水记录，请先上传文件预览'}, status=400)
        if not company_id:
            return Response({'error': '缺少 company_id'}, status=400)
    
        try:
            company = Company.objects.get(id=company_id)
        except Company.DoesNotExist:
            return Response({'error': '公司不存在'}, status=400)
    
        # ── 银行账户解析 ───────────────────────────────────────────────
        bank_account = None
        ba_id = body.get('bank_account_id', '')
        ba_no = body.get('account_no', '').strip()
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
    
        # ── 预加载待核销发票
    
        # ── 预加载待核销发票（批量优化，避免N条流水触发N次DB查询）────────
        # ── 预加载待核销发票
        pending_income_invoices = list(Invoice.objects.filter(
            type='income', status='pending', company=company,
        ).exclude(payment_date__isnull=False).order_by('issue_date', 'id'))
    
        # 支出类：type=expense + status=pending + 有未付款日期
        pending_expense_invoices = list(Invoice.objects.filter(
            type='expense', status='pending', company=company,
        ).exclude(payment_date__isnull=False).order_by('issue_date', 'id'))
    
        LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs')
        os.makedirs(LOG_DIR, exist_ok=True)
        LOG_PATH = os.path.join(LOG_DIR, 'bank_import_skip.log')
        batch_id = uuid.uuid4().hex[:12].upper()
    
        with open(LOG_PATH, 'w') as _lf:
            _lf.write(f"===== confirm_bank_import START =====\n")
            _lf.write(f"company={company_id} bank_account={bank_account.id} rows={len(rows)}\n")
            _lf.write(f"batch_id={batch_id}\n")
    
        income_count = expense_count = 0
        income_sum = expense_sum = Decimal('0')
        skipped = 0
        errors = []
        from datetime import timedelta
    
        for idx, row in enumerate(rows):
            with open(LOG_PATH, 'a') as _lf:
                _lf.write(f"[{idx}] date={row.get('transaction_date','')} serial={row.get('bank_serial','')!r} "
                          f"amount={row.get('amount','')} dir={row.get('direction','')}\n")
    
            # ── 解析 ────────────────────────────────────────────────────
            t_date = row.get('transaction_date', '')
            t_time = row.get('transaction_time', '')
            try:
                amount = Decimal(str(row.get('amount', '0')))
            except Exception:
                amount = Decimal('0')
            direction  = row.get('direction', '')
            cp_name    = row.get('counterparty_name', '').strip()
            cp_account = row.get('counterparty_account', '').strip()
            cp_bank    = row.get('counterparty_bank', '').strip()
            summary    = row.get('summary', '')[:500]
            serial     = row.get('bank_serial', '')
            tx_type    = row.get('transaction_type', '')[:100]
            # 余额（去重用）
            try:
                bal = Decimal(str(row.get('balance', '0')))
            except Exception:
                bal = Decimal('0')

            # 日期解析
            if isinstance(t_date, str) and t_date:
                tx_date = datetime.datetime.strptime(
                    t_date.split('T')[0] if 'T' in t_date else t_date, '%Y-%m-%d').date()
            else:
                tx_date = datetime.date.today()
    
            # 时间解析
            tx_time = None
            if t_time:
                try:
                    t_time_clean = t_time.split('T')[1][:8] if 'T' in t_time else t_time[:8]
                    tx_time = datetime.datetime.strptime(t_time_clean, '%H:%M:%S').time()
                except ValueError:
                    tx_time = None
    
            # ── 去重（平安银行：无交易时间，靠 日期+金额+余额+对方账户 4条件判断重复） ──
            dedup = f"{tx_date}_{amount}_{bal}_{cp_account}"
            if BankStatement.objects.filter(
                company=company, transaction_date=tx_date, amount=amount,
                balance=bal, counterparty_account=cp_account
            ).exists():
                with open(LOG_PATH, 'a') as _lf:
                    _lf.write(f"  >> SKIP dedup: serial={serial!r} dedup={dedup!r}\n")
                skipped += 1
                continue
    
            # ── 档案匹配：导入时不做，由后置步骤从收支记录中提取创建 ─────────────
    
            # ── 原子事务：每行独立事务，互不污染 ─────────────────────────
            # 1:1 还原银行流水原始对手方，不做任何替换或转换
            # cp_name 为空就写空，不写"未知对手方"
            写进流水的主营对手方 = cp_name
            inc_obj, exp_obj, bs = None, None, None
            try:
                with transaction.atomic():
                    if direction == 'income':
                        inc = Income.objects.create(
                            company=company, customer=写进流水的主营对手方, source=tx_type or '网银',
                            amount=amount, date=tx_date, description=summary,
                            transaction_time=tx_time,
                            balance=Decimal(row['balance']) if row.get('balance') else None,
                            counterparty_account=cp_account, counterparty_bank=cp_bank,
                            transaction_type=tx_type, summary=summary,
                            status='received',  # 银行流水导入，已到账无需审批
                        )
                        income_count += 1
                        income_sum += amount
                        inc_obj = inc
                    else:
                        exp = Expense.objects.create(
                            company=company, supplier=写进流水的主营对手方,
                            expense_type=tx_type or '转账', expense_category='',
                            amount=amount, expense_date=tx_date, description=summary,
                            note=serial or '',
                            transaction_time=tx_time,
                            balance=Decimal(row['balance']) if row.get('balance') else None,
                            counterparty_account=cp_account, counterparty_bank=cp_bank,
                            transaction_type=tx_type, summary=summary,
                            status='confirmed',  # 银行流水导入，已确认无需审批
                        )
                        expense_count += 1
                        expense_sum += amount
                        exp_obj = exp
    
                    # BankStatement.counterparty_name：直接用原始对手方，1:1还原
                    bs_cp_name = cp_name
                    bs = BankStatement.objects.create(
                        company=company, bank_account=bank_account,
                        bank_serial=serial, transaction_date=tx_date,
                        transaction_time=tx_time, direction=direction,
                        amount=amount,
                        balance=Decimal(row['balance']) if row.get('balance') else None,
                        counterparty_name=bs_cp_name, counterparty_account=cp_account,
                        counterparty_bank=cp_bank, summary=summary,
                        import_batch=batch_id, transaction_type=tx_type,
                        matched_income=inc_obj, matched_expense=exp_obj,
                    )
    
                with open(LOG_PATH, 'a') as _lf:
                    _lf.write(f"  >>> OK idx={idx} bs_id={bs.id} inc_id={inc_obj.id if inc_obj else None} "
                              f"exp_id={exp_obj.id if exp_obj else None}\n")
    
            except Exception as e:
                import traceback
                tb = traceback.format_exc()
                with open(LOG_PATH, 'a') as _lf:
                    _lf.write(f"  *** ATOMIC_ROLLBACK idx={idx}: {e}\n")
                    _lf.write(f"  TRACE: {tb}\n")
                errors.append(f"行 {tx_date} {cp_name}: {e}")
    
            # ── 发票核销（在事务外，不阻塞主流程）────────────────────────
            if bs and amount and cp_name:
                try:
                    _reconcile_invoice(
                        bs, cp_name, amount, tx_date,
                        pending_income_invoices, pending_expense_invoices,
                        date_tolerance=5
                    )
                except Exception as rec_err:
                    errors.append(f"核销异常 {tx_date}: {rec_err}")
    
        # ── 汇总写入 ───────────────────────────────────────────────────
        with open(LOG_PATH, 'a') as _lf:
            _lf.write(f"===== confirm_bank_import END =====\n")
            _lf.write(f"imported_income={income_count} imported_expense={expense_count} "
                      f"skipped={skipped} errors={len(errors)}\n")
            for err in errors:
                _lf.write(f"  ERROR: {err}\n")
    
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
    
    finally:
        resume_audit()