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
from apps.finance.models import Company, Income, Expense
from apps.finance.models_bank import BankAccount, BankStatement
from apps.crm.models import Client, Supplier


# ═══════════════════════════════════════════════════════════════════════════
# 分类规则（优先级：TX_TYPE_RULES > 摘要关键词 > 默认）
# ═══════════════════════════════════════════════════════════════════════════

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
                               'cp_override': '国家金库', 'skip_cp': False,
                               'note': '税款走暂收款通道，实际对手是国家金库'},
    '企业银行各项费用':        {'direction': 'expense', 'category': '金融服务',
                               'skip_cp': True,
                               'note': '银行手续费，不建档'},
    '批量代发付费':           {'direction': 'expense', 'category': 'skip',
                               'note': '银行批量代发手续费，直接跳过'},
    '跨行汇款-普通':          {'direction': 'expense', 'category': '金融服务',
                               'note': '跨行转账手续费'},
    '跨行汇款-实时':          {'direction': 'expense', 'category': '金融服务',
                               'note': '跨行转账手续费'},
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
                               'skip_cp': True,
                               'note': '银行费用入账'},
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
    cp_name  = (t.counterparty_name or '').strip()
    cp_type  = _classify_cp_type(cp_name)
    cp_override = ''
    skip_cp = False
    is_skip = False
    is往来  = False

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

def _upsert_counterparty(company, t: ParsedTransaction, cp_type: str, direction: str):
    """
    自动创建或更新 Client / Supplier 档案。
    同一企业可以是客户也可以是供应商（双向交易）。
    - direction=income → upsert Client（对手是客户）
    - direction=expense → upsert Supplier（对手是供应商）
    - 如果对手已存在于另一张表，同时创建双向档案
    """
    name    = t.counterparty_name.strip()
    account = t.counterparty_account.strip()
    bank    = t.counterparty_bank.strip()
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


def match_counterparty(t: ParsedTransaction, company):
    """智能匹配已有的 Client / Supplier 档案。"""
    name    = t.counterparty_name.strip()
    account = t.counterparty_account.strip()

    if not name and not account:
        return '', ''

    if name:
        c = Client.objects.filter(company=company, name__contains=name).first()
        if c:
            return 'client', c.name
        s = Supplier.objects.filter(company=company, name__contains=name).first()
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
    """预览银行流水（不写库），返回完整36列解析结果。"""
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
    skip_count    = 0

    for t in transactions:
        r = _classify(t)
        direction = r['direction']
        category  = r['category']

        # 汇总
        if direction == 'income':
            total_income += t.amount
        else:
            total_expense += t.amount

        if r['is_skip_record']:
            skip_count += 1

        # 匹配已有档案
        match_type, match_name = match_counterparty(t, company)

        # 最终对手方名称（可能被 override）
        final_cp = r['counterparty_override'] or t.counterparty_name

        preview_rows.append({
            # 原始字段
            'transaction_date':    t.transaction_date.isoformat() if t.transaction_date else '',
            'transaction_time':   t.transaction_time.isoformat() if t.transaction_time else '',
            'direction':          direction,
            'direction_display':  '收入' if direction == 'income' else '支出',
            'amount':              str(t.amount),
            'balance':             str(t.balance) if t.balance else '',
            'counterparty_name':   final_cp,
            'counterparty_account':t.counterparty_account,
            'counterparty_bank':   t.counterparty_bank,
            'summary':             t.summary[:120],
            'usage':               (t.usage or '')[:120],
            'bank_serial':         t.bank_serial,
            # 扩展字段（CMB v2.0）
            'transaction_type':   getattr(t, 'transaction_type', '') or '',
            'tx_code':             getattr(t, 'tx_code', '') or '',
            'value_date':          getattr(t, 'value_date', '') or '',
            'biz_name':            getattr(t, 'biz_name', '') or '',
            'biz_summary':         getattr(t, 'biz_summary', '') or '',
            'other_summary':       getattr(t, 'other_summary', '') or '',
            'ext_summary':         getattr(t, 'ext_summary', '') or '',
            'biz_ref':             getattr(t, 'biz_ref', '') or '',
            'bill_no':             getattr(t, 'bill_no', '') or '',
            'counterparty_bank_branch': getattr(t, 'counterparty_bank_branch', '') or '',
            'counterparty_bank_code':   getattr(t, 'counterparty_bank_code', '') or '',
            'counterparty_bank_addr':    getattr(t, 'counterparty_bank_addr', '') or '',
            'info_flag':           getattr(t, 'info_flag', '') or '',
            'reverse_flag':        getattr(t, 'reverse_flag', '') or '',
            # 自动分类结果
            'auto_category':       category,
            'match_type':          match_type,
            'match_name':          match_name,
            'is_skip_record':       r['is_skip_record'],
            'is往来':              r['is往来'],
            '往来_type':           r.get('往来_type', ''),
            '往来_remark':         r.get('往来_remark', ''),
            'cp_type':             r['cp_type'],
            'note':                TX_TYPE_RULES.get(
                                      (t.transaction_type or '').strip(), {}
                                  ).get('note', ''),
            # 去重
            'dedup_key': t.bank_serial or
                         f"{t.transaction_date}_{t.counterparty_account}_{t.amount}",
        })

    return Response({
        'bank_code':    used_bank,
        'total_count':  len(transactions),
        'skip_count':   skip_count,
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
    - 往来款：只写 BankStatement（标记 is往来=True），不写 Income/Expense
    - skip_record：整条跳过（既不写 BankStatement 也不写 Income/Expense）
    - 普通记录：写 BankStatement + Income/Expense
    - 自动Upsert Client/Supplier 档案（含银行信息）
    """
    body = request.data
    company_id  = body.get('company_id')
    bank_code   = body.get('bank_code', '')
    bank_serial = body.get('bank_serial', '')
    rows        = body.get('rows', [])

    if not company_id:
        return Response({'error': '缺少 company_id'}, status=400)

    try:
        company = Company.objects.get(id=company_id)
    except Company.DoesNotExist:
        return Response({'error': '公司不存在'}, status=400)

    # 找银行账户
    bank_account = None
    if bank_code:
        bank_account = BankAccount.objects.filter(
            company=company, bank_code=bank_code
        ).first()

    imported = skipped = income_count = expense_count =往来_count = 0
    income_sum = expense_sum = Decimal('0')
    errors = []

    batch_id = uuid.uuid4().hex[:12].upper()

    for row in rows:
        try:
            t_date   = row.get('transaction_date', '')
            t_time   = row.get('transaction_time', '')
            amount   = Decimal(str(row.get('amount', '0')))
            direction= row.get('direction', '')
            category = row.get('auto_category', '其他')
            cp_name  = row.get('counterparty_name', '').strip()
            cp_account = row.get('counterparty_account', '').strip()
            cp_bank  = row.get('counterparty_bank', '').strip()
            summary  = row.get('summary', '')[:500]
            usage    = row.get('usage', '')[:500]
            serial   = row.get('bank_serial', '')
            is_skip  = row.get('is_skip_record', False)
            is往来   = row.get('is往来', False)
            cp_type  = row.get('cp_type', 'individual')

            # 扩展字段
            tx_type     = row.get('transaction_type', '')[:100]
            tx_code     = row.get('tx_code', '')[:50]
            value_date  = row.get('value_date', '')
            biz_name    = row.get('biz_name', '')[:200]
            biz_summary = row.get('biz_summary', '')[:500]
            other_sum   = row.get('other_summary', '')[:500]
            ext_sum     = row.get('ext_summary', '')[:500]
            biz_ref     = row.get('biz_ref', '')[:100]
            bill_no     = row.get('bill_no', '')[:100]
            cp_branch   = row.get('counterparty_bank_branch', '')[:200]
            cp_bcode    = row.get('counterparty_bank_code', '')[:50]
            cp_baddr    = row.get('counterparty_bank_addr', '')[:200]
            info_flag   = row.get('info_flag', '')[:10]
            rev_flag    = row.get('reverse_flag', '')[:10]

            # 解析日期时间
            if isinstance(t_date, str) and t_date:
                if 'T' in t_date:
                    t_date = t_date.split('T')[0]
                tx_date = datetime.datetime.strptime(t_date, '%Y-%m-%d').date()
            else:
                tx_date = datetime.date.today()

            tx_time = None
            if t_time:
                try:
                    if 'T' in t_time:
                        t_time = t_time.split('T')[1][:8]
                    tx_time = datetime.datetime.strptime(t_time[:8], '%H:%M:%S').time()
                except ValueError:
                    tx_time = None

            # 起息日
            vd = None
            if value_date:
                try:
                    vd = datetime.datetime.strptime(value_date[:10], '%Y-%m-%d').date()
                except ValueError:
                    pass

            # 去重
            dedup = serial or f"{tx_date}_{cp_account}_{amount}"
            if BankStatement.objects.filter(
                company=company, bank_serial=dedup
            ).exists():
                skipped += 1
                continue

            # 整条跳过（批量代发付费等）
            if is_skip:
                skipped += 1
                continue

            # ── 写 BankStatement ──────────────────────────────────────────
            bs_data = dict(
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
                usage=usage,
                source_bank=bank_code,
                import_batch=batch_id,
                # 扩展字段
                transaction_type=tx_type,
                tx_code=tx_code,
                value_date=vd,
                biz_name=biz_name,
                biz_summary=biz_summary,
                other_summary=other_sum,
                ext_summary=ext_sum,
                biz_ref=biz_ref,
                bill_no=bill_no,
                counterparty_bank_branch=cp_branch,
                counterparty_bank_code=cp_bcode,
                counterparty_bank_addr=cp_baddr,
                info_flag=info_flag,
                reverse_flag=rev_flag,
                # 往来款字段
                is_往来=is往来,
                往来_type=row.get('往来_type', ''),
                往来_remark=row.get('往来_remark', ''),
            )

            # 往来款：只写 BankStatement
            if is往来:
                BankStatement.objects.create(**bs_data)
                imported += 1
                往来_count += 1
                continue

            # ── 正常记录：写 BankStatement + Income/Expense ───────────────
            bs = BankStatement.objects.create(**bs_data)

            # 自动建档（只在有真实对手方时）
            cp_obj = None
            if cp_name and cp_type in ('enterprise', 'government') and not row.get('is_skip_counterparty'):
                # 构造 ParsedTransaction 传参
                class _T:
                    def __init__(self):
                        self.counterparty_name   = cp_name
                        self.counterparty_account = cp_account
                        self.counterparty_bank    = cp_bank
                        self.counterparty_bank_branch = cp_branch
                        self.counterparty_bank_code   = cp_bcode
                        self.counterparty_bank_addr   = cp_baddr
                        self.direction = direction
                cp_obj = _upsert_counterparty(company, _T(), cp_type, direction)

            # 写 Income / Expense
            if direction == 'income':
                Income.objects.create(
                    company=company,
                    customer=cp_name,
                    source=category,
                    amount=amount,
                    date=tx_date,
                    description=summary + (f" [流水号:{serial}]" if serial else ''),
                )
                income_count += 1
                income_sum += amount
            else:
                # ── 银行导入 category → expense_type 映射（新枚举）──────────────
                cat_to_etype = {
                    '税务':        'tax',
                    '金融服务':   'other',
                    '采购':       'other',
                    '招待':       'entertainment',
                    '差旅':       'travel',
                    '薪资':       'salary',
                    '社保':       'social',
                    '租金':       'other',
                    '物业':       'office',
                    '运费':       'other',
                    '往来':       'other',
                    '其他费用':   'other',
                    # 历史数据兼容
                    '工资':        'salary',
                    '社保公积金': 'social',
                    '报销':       'other',
                    '备用金':     'advance',
                    '税费':       'tax',
                    '借款还款':   'other',
                }
                exp_type = cat_to_etype.get(category, 'other')

                Expense.objects.create(
                    company=company,
                    supplier=cp_name,  # CharField
                    expense_type=exp_type,
                    expense_category=category,
                    amount=amount,
                    expense_date=tx_date,
                    description=summary,
                    note=(f"流水号:{serial}" if serial else ''),
                )
                expense_count += 1
                expense_sum += amount

            imported += 1

        except Exception as e:
            errors.append(f"行 {row.get('transaction_date','')} {row.get('counterparty_name','')}: {e}")

    return Response({
        'batch_id':       batch_id,
        'imported':       imported,
        'skipped':        skipped,
        'income_count':   income_count,
        'expense_count':  expense_count,
        '往来_count':    往来_count,
        'income_sum':     str(income_sum),
        'expense_sum':    str(expense_sum),
        'errors':         errors[:20],
    })
