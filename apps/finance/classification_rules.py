"""
科目映射规则（classification_rules.py）
—— 将原始数据（Income/Expense/WageRecord/SocialRecord/Invoice/BankStatement）映射到
   会计科目表（Account）的查询时映射函数。

所有函数均为查询时调用，不修改原始数据。
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional, Set

from django.db.models import QuerySet, Sum
from .models import (
    Account,
    Income,
    Expense,
    WageRecord,
    SocialRecord,
    Invoice,
    BankStatement,
)


def get_internal_company_names() -> Set[str]:
    """从 Company 表动态获取所有公司名称，用于排除内部转账"""
    from .models import Company

    return set(Company.objects.values_list('name', flat=True))


def is_internal_company(name: Optional[str]) -> bool:
    """判断是否为内部公司"""
    if not name:
        return False
    return name in get_internal_company_names()


def get_account_by_code(code: str) -> Optional[Account]:
    """按编码获取全局科目"""
    try:
        return Account.objects.get(code=code, company__isnull=True)
    except Account.DoesNotExist:
        return None


# ═══════════════════════════════════════════════════════════════════
# 一、收入科目映射
# ═══════════════════════════════════════════════════════════════════


def map_income_to_account(income: Income) -> Optional[Account]:
    """将 Income 记录映射到收入科目

    映射规则：
    - income_category='main_business'  → 4001 主营业务收入
    - income_category='other_business' → 4002 其他业务收入
    - income_category='non_operating'  → 4003 营业外收入
    - 未分类的收入：检查 customer/counterparty 是否为内部公司 → 排除不映射
    """
    # 内部转账不映射
    if is_internal_company(income.customer):
        return None

    # 按 income_category 映射
    category_map = {
        'main_business': '4001',
        'other_business': '4002',
        'non_operating': '4003',
        'other_income': '4004',
        'investment_income': '4005',
    }
    code = category_map.get(income.income_category)
    if code:
        return get_account_by_code(code)

    # 未分类 → 默认归入主营业务收入
    return get_account_by_code('4001')


# ═══════════════════════════════════════════════════════════════════
# 二、支出科目映射
# ═══════════════════════════════════════════════════════════════════


def map_expense_to_account(expense: Expense) -> Optional[Account]:
    """将 Expense 记录映射到费用科目

    映射规则：
    - expense_type/expense_category 匹配已知类型
    - 内部转账不映射
    - 工资/社保类支出：5101/5102（但工资和社保另有WageRecord/SocialRecord来源）
    - 未匹配的默认归入'管理费用-其他'
    """
    # 内部转账不映射
    if is_internal_company(expense.supplier):
        return None

    cat = (expense.expense_category or '').lower()
    etype = (expense.expense_type or '').lower()

    # 成本类：采购/货款 → 5001-01 采购成本
    if etype in ('货款', '采购', 'purchase', '材料', 'main_cost'):
        return get_account_by_code('5001-01')

    # 工资 → 不映射（通过WageRecord单独核算）
    if cat == 'salary' or etype == 'salary':
        return None  # 工资由 WageRecord 映射

    # 社保 → 不映射（通过SocialRecord单独核算）
    if cat == 'social' or etype == 'social':
        return None  # 社保由 SocialRecord 映射

    # 内部往来 → 不映射（非真实费用）
    if etype == 'internal_transfer':
        return None

    # 代收代付 → 不映射（过手资金，非真实费用）
    if etype == 'agency':
        return None

    # 税费 → 5003 税金及附加
    if '税款' in cat or cat == 'tax' or etype == 'tax':
        return get_account_by_code('5003')

    # 按 expense_type 值映射
    type_to_leaf = {
        'main_cost': '5001-01',  # 主营业务成本-采购成本
        'office': '5002-03',  # 办公费用
        'travel': '5002-04',  # 差旅费用
        'admin_expense': '5002-10',  # 管理费用-其他
        'entertainment': '5002-05',  # 业务招待费
        'communication': '5002-06',  # 通讯费用
        'marketing': '5002-07',  # 市场营销
        'rd': '5002-08',  # 研发费用
        'finance_expense': '5005',  # 财务费用
        'advance': '5002-10',  # 预付款 → 其他
        'other': '5002-10',  # 其他
    }
    code = type_to_leaf.get(etype)
    if code:
        return get_account_by_code(code)

    # 按摘要关键词匹配
    summary = (expense.summary or '').lower()
    if any(kw in summary for kw in ['差旅', '机票', '酒店', '住宿', '高铁', '火车票']):
        return get_account_by_code('5002-04')  # 差旅
    if any(kw in summary for kw in ['招待', '餐饮', '餐费', '饭']):
        return get_account_by_code('5002-05')  # 业务招待
    if any(kw in summary for kw in ['办公', '文具', '打印', '耗材']):
        return get_account_by_code('5002-03')  # 办公
    if any(kw in summary for kw in ['通讯', '电话', '网费']):
        return get_account_by_code('5002-06')  # 通讯
    if any(kw in summary for kw in ['广告', '推广', '市场']):
        return get_account_by_code('5002-07')  # 市场营销

    # 未匹配 → 管理费用-其他
    return get_account_by_code('5002-10')


# ═══════════════════════════════════════════════════════════════════
# 三、工资科目映射
# ═══════════════════════════════════════════════════════════════════


def map_wage_to_account() -> Optional[Account]:
    """工资薪酬 → 5002-01 管理费用-工资薪酬"""
    return get_account_by_code('5002-01')


def get_wage_total(company_id: int, year: int, month: Optional[int] = None) -> Decimal:
    """获取指定公司月份工资总额（应发合计 gross_salary）"""
    qs = WageRecord.objects.filter(company_id=company_id, year=year).order_by('employee_id')
    if month:
        qs = qs.filter(month=month)

    # WageRecord 没有存 gross_salary 字段，需要计算
    # 使用 annotation aggregate
    total = Decimal('0')
    for wr in qs:
        calced = wr.calculate_gross_and_tax()
        total += Decimal(str(calced.get('gross_salary', 0)))
    return total


# ═══════════════════════════════════════════════════════════════════
# 四、社保科目映射
# ═══════════════════════════════════════════════════════════════════


def map_social_to_account() -> Optional[Account]:
    """社保费用 → 5002-02 管理费用-社保费用"""
    return get_account_by_code('5002-02')


def get_social_total(company_id: int, year: int, month: Optional[int] = None) -> Dict[str, Any]:
    """获取指定公司月份社保单位缴纳总额"""
    qs = SocialRecord.objects.filter(company_id=company_id, year_month__startswith=str(year))
    if month:
        ym = f'{year}{month:02d}'
        qs = qs.filter(year_month=ym)

    agg = qs.aggregate(
        total_company=Sum('total_company'),
        pension=Sum('pension_company'),
        medical=Sum('medical_company'),
        unemployment=Sum('unemployment_company'),
        injury=Sum('injury_company'),
        birth=Sum('birth_company'),
        housing_fund=Sum('housing_fund_company'),
    )
    return {
        'total_company': Decimal(str(agg['total_company'] or 0)),
        'pension': Decimal(str(agg['pension'] or 0)),
        'medical': Decimal(str(agg['medical'] or 0)),
        'unemployment': Decimal(str(agg['unemployment'] or 0)),
        'injury': Decimal(str(agg['injury'] or 0)),
        'birth': Decimal(str(agg['birth'] or 0)),
        'housing_fund': Decimal(str(agg['housing_fund'] or 0)),
    }


# ═══════════════════════════════════════════════════════════════════
# 五、发票科目映射
# ═══════════════════════════════════════════════════════════════════


def map_invoice_to_account(invoice: Any) -> Optional[Account]:
    """将 Invoice 映射到应收/应付科目

    - invoice.type='income'  → 1002 应收账款
    - invoice.type='expense' → 2001 应付账款
    """
    if invoice.invoice_type == 'income':
        return get_account_by_code('1002')  # 应收账款
    elif invoice.invoice_type == 'expense':
        return get_account_by_code('2001')  # 应付账款
    return None


def get_invoice_ar_ap_total(company_id: int, year: int, status: str = 'pending') -> Dict[str, Any]:
    """获取应收账款(AR)和应付账款(AP)汇总"""
    ar = Invoice.objects.filter(
        company_id=company_id,
        invoice_type='income',
        status=status,
        issue_date__year=year,
    ).aggregate(
        total=Sum('amount'),
        tax=Sum('tax_amount'),
    )
    ap = Invoice.objects.filter(
        company_id=company_id,
        invoice_type='expense',
        status=status,
        issue_date__year=year,
    ).aggregate(
        total=Sum('amount'),
        tax=Sum('tax_amount'),
    )
    return {
        'accounts_receivable': Decimal(str(ar['total'] or 0)),
        'ar_tax': Decimal(str(ar['tax'] or 0)),
        'accounts_payable': Decimal(str(ap['total'] or 0)),
        'ap_tax': Decimal(str(ap['tax'] or 0)),
    }


# ═══════════════════════════════════════════════════════════════════
# 六、银行余额映射
# ═══════════════════════════════════════════════════════════════════


def map_bank_to_account() -> Optional[Account]:
    """银行存款 → 1001 银行存款"""
    return get_account_by_code('1001')


def get_bank_balance(company_id: int) -> Decimal:
    """获取公司最新银行账户余额（取最后一条流水余额）"""
    last_stmt = (
        BankStatement.objects.filter(company_id=company_id)
        .order_by('-transaction_date', '-transaction_time', '-id')
        .first()
    )
    if last_stmt and last_stmt.balance is not None:
        return Decimal(str(last_stmt.balance))
    return Decimal('0')


def get_bank_account_balances(company_id: int) -> Dict[str, Any]:
    """获取各银行账户最新余额"""
    from .models import BankAccount

    result = {}
    accounts = BankAccount.objects.filter(company_id=company_id).order_by('account_name')
    for acct in accounts:
        last = (
            BankStatement.objects.filter(bank_account=acct)
            .order_by('-transaction_date', '-transaction_time', '-id')
            .first()
        )
        result[acct.account_name or acct.account_number] = (
            Decimal(str(last.balance)) if last and last.balance is not None else Decimal('0')
        )
    return result


# ═══════════════════════════════════════════════════════════════════
# 七、科目余额表（内存计算版）
# ═══════════════════════════════════════════════════════════════════


def compute_trial_balance(company_id: int, year: int) -> List[Dict[str, Any]]:
    """计算指定公司年份的科目余额表（内存计算，不持久化）

    返回按 account_type 分组的科目余额列表，每项包含：
    - account: Account 对象
    - opening_balance: 期初余额（本系统简化为0）
    - debit_amount: 本期借方发生额（费用/资产增加）
    - credit_amount: 本期贷方发生额（收入/负债增加）
    - closing_balance: 期末余额

    会计恒等式：资产 = 负债 + 所有者权益
    """
    from django.db.models import Sum
    from decimal import Decimal
    from .models import Income, Expense

    result = []
    accounts = Account.objects.filter(company__isnull=True).order_by('sort_order', 'code')

    # ── 预聚合数据 ──────────────────────────────────────────────
    # 收入按科目聚合
    income_records = (
        Income.objects.filter(company_id=company_id, date__year=year)
        .exclude(customer__in=get_internal_company_names())
        .order_by('date', 'id')
    )

    income_by_account = {}
    for inc in income_records:
        acct = map_income_to_account(inc)
        if acct:
            income_by_account.setdefault(acct.code, Decimal('0'))
            income_by_account[acct.code] += Decimal(str(inc.amount))

    # 支出按科目聚合
    expense_records = (
        Expense.objects.filter(company_id=company_id, expense_date__year=year)
        .exclude(supplier__in=get_internal_company_names())
        .order_by('expense_date', 'id')
    )

    expense_by_account = {}
    for exp in expense_records:
        acct = map_expense_to_account(exp)
        if acct:
            expense_by_account.setdefault(acct.code, Decimal('0'))
            expense_by_account[acct.code] += Decimal(str(exp.amount))

    # 工资总和（使用已计算的 gross_salary 字段）
    wage_total = Decimal('0')
    wage_records = WageRecord.objects.filter(company_id=company_id, year=year).order_by('employee_id')
    for wr in wage_records:
        wage_total += Decimal(str(wr.gross_salary or 0))

    # 社保总和
    social_agg = SocialRecord.objects.filter(company_id=company_id, year_month__startswith=str(year)).aggregate(
        total=Sum('total_company')
    )
    social_total = Decimal(str(social_agg['total'] or 0))

    # 银行余额
    bank_balance = get_bank_balance(company_id)

    # 应收/应付
    invoice_data = get_invoice_ar_ap_total(company_id, year, status='pending')

    for acct in accounts:
        debit_amount = Decimal('0')
        credit_amount = Decimal('0')

        # 收入类科目 → 贷方余额
        if acct.account_type == 'income':
            credit_amount = income_by_account.get(acct.code, Decimal('0'))

        # 费用类科目 → 借方余额
        elif acct.account_type == 'expense':
            if acct.code == '5002-01':  # 管理费用-工资薪酬
                debit_amount = wage_total
            elif acct.code == '5002-02':  # 管理费用-社保费用
                debit_amount = social_total
            elif acct.code.startswith('5002-'):  # 其他管理费子科目
                debit_amount = expense_by_account.get(acct.code, Decimal('0'))
            elif acct.code == '5003':  # 税金及附加
                # 税费汇总：发票税额 + 社保（不含工资）
                debit_amount = invoice_data.get('ap_tax', Decimal('0'))
            elif acct.code == '5001':  # 主营业务成本
                # 从支出映射到成本科目的合计
                debit_amount = expense_by_account.get(acct.code, Decimal('0'))
            elif acct.code == '5001-01':  # 采购成本
                debit_amount = expense_by_account.get(acct.code, Decimal('0'))
            elif acct.code == '5004':  # 营业外支出
                debit_amount = expense_by_account.get(acct.code, Decimal('0'))
            else:
                debit_amount = expense_by_account.get(acct.code, Decimal('0'))

        # 资产类科目 → 借方余额
        elif acct.account_type == 'asset':
            if acct.code == '1001':  # 银行存款
                debit_amount = bank_balance
            elif acct.code == '1001-01' or acct.code == '1001-02':
                # 不细分银行账户
                pass
            elif acct.code == '1002':  # 应收账款
                debit_amount = invoice_data.get('accounts_receivable', Decimal('0'))
            elif acct.code == '1003':  # 其他应收款
                pass  # 暂无数据来源

        # 负债类科目 → 贷方余额
        elif acct.account_type == 'liability':
            if acct.code == '2001':  # 应付账款
                credit_amount = invoice_data.get('accounts_payable', Decimal('0'))
            elif acct.code == '2002':  # 应付职工薪酬
                # 应付 = 应发 - 实发（待支付）
                total_paid = wage_records.aggregate(s=Sum('net_salary'))['s'] or Decimal('0')
                credit_amount = wage_total - Decimal(str(total_paid))
            elif acct.code == '2003':  # 应交税费
                credit_amount = invoice_data.get('ap_tax', Decimal('0')) - invoice_data.get('ar_tax', Decimal('0'))
            elif acct.code == '2004':  # 其他应付款
                pass

        # 权益类科目 → 贷方余额
        elif acct.account_type == 'equity':
            if acct.code == '3001':  # 实收资本
                pass  # 手动配置，暂为0
            elif acct.code == '3002':  # 未分配利润
                # 未分配利润 = 总收入 - 总费用（净利润累计）
                total_income = sum(v for k, v in income_by_account.items() if k.startswith('4'))
                total_expense = (
                    wage_total + social_total + sum(v for k, v in expense_by_account.items() if k.startswith('5'))
                )
                credit_amount = total_income - total_expense

        # 计算期末余额
        if acct.account_type in ('asset', 'expense'):
            # 借余类科目：期末 = 期初 + 借方 - 贷方
            closing_balance = debit_amount - credit_amount
        else:
            # 贷余类科目：期末 = 期初 + 贷方 - 借方
            closing_balance = credit_amount - debit_amount

        if debit_amount != 0 or credit_amount != 0 or closing_balance != 0:
            result.append(
                {
                    'account_code': acct.code,
                    'account_name': acct.name,
                    'account_type': acct.account_type,
                    'opening_balance': Decimal('0'),
                    'debit_amount': debit_amount,
                    'credit_amount': credit_amount,
                    'closing_balance': closing_balance,
                    'level': acct.level,
                    'sort_order': acct.sort_order,
                }
            )

    return result
