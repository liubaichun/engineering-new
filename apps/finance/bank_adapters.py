"""
银行流水解析适配器（无外部依赖版）
支持：ICBC HISTORYDETAIL / CMB ACCOUNT v2.0
"""
import datetime
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional


@dataclass
class ParsedTransaction:
    transaction_date: Optional[datetime.date] = None
    transaction_time: Optional[datetime.time] = None
    amount: Decimal = Decimal('0')
    direction: str = 'expense'   # income / expense
    balance: Optional[Decimal] = None
    counterparty_name: str = ''
    counterparty_account: str = ''
    counterparty_bank: str = ''
    summary: str = ''
    usage: str = ''
    bank_serial: str = ''
    raw_data: dict = field(default_factory=dict)

    def get_dedup_key(self) -> str:
        if self.bank_serial:
            return self.bank_serial
        date_str = self.transaction_date.isoformat() if self.transaction_date else ''
        time_str = self.transaction_time.isoformat() if self.transaction_time else ''
        return f"{date_str}_{time_str}_{self.counterparty_account}_{self.amount}"


class BankStatementAdapter(ABC):
    bank_code: str = ''
    bank_name: str = ''

    @abstractmethod
    def detect(self, ws) -> bool:
        raise NotImplementedError

    @abstractmethod
    def parse(self, ws) -> list[ParsedTransaction]:
        raise NotImplementedError

    # ── 通用解析工具 ──────────────────────────────────────────────
    def _parse_date(self, value) -> Optional[datetime.date]:
        if value is None:
            return None
        if isinstance(value, datetime.datetime):
            return value.date()
        if isinstance(value, datetime.date):
            return value
        s = str(value).strip().replace('/', '-')
        for fmt in ('%Y-%m-%d', '%Y%m%d', '%m-%d-%Y', '%d-%m-%Y'):
            try:
                return datetime.datetime.strptime(s, fmt).date()
            except ValueError:
                continue
        return None

    def _parse_time(self, value) -> Optional[datetime.time]:
        if value is None:
            return None
        if isinstance(value, datetime.time):
            return value
        if isinstance(value, datetime.datetime):
            return value.time()
        s = str(value).strip()
        for fmt in ('%H:%M:%S', '%H:%M'):
            try:
                return datetime.datetime.strptime(s, fmt).time()
            except ValueError:
                continue
        return None

    def _decimal(self, value) -> Optional[Decimal]:
        if value is None or str(value).strip() == '':
            return None
        try:
            s = str(value).replace(',', '').replace('¥', '').replace(' ', '').replace('+', '').strip()
            if s == '' or s == '-':
                return None
            return Decimal(s)
        except (ValueError, TypeError):
            return None


# ─── 工商银行 HISTORYDETAIL ─────────────────────────────────────────────
class ICBCAdapter(BankStatementAdapter):
    """
    格式：
    Row 1 (A1): [HISTORYDETAIL]
    Row 2 (A2): 凭证号|B|交易时间|C|借贷标志|D|对方单位|E|对方行号|F|用途|G|摘要|H|附言|I|个性化信息|J|余额|K
    Row 3+: 数据
    列A=凭证号, B=对方账号, C=交易时间, D=借贷标志, E=对方单位, F=对方行号,
          G=用途, H=摘要, I=附言, J=个性化信息, K=余额
    """
    bank_code = 'ICBC'
    bank_name = '工商银行'

    def detect(self, ws) -> bool:
        try:
            return str(ws.cell(1, 1).value or '').strip() == '[HISTORYDETAIL]'
        except Exception:
            return False

    def parse(self, ws) -> list[ParsedTransaction]:
        records = []
        prev_balance = None

        for row_idx in range(3, ws.max_row + 1):
            try:
                col = lambda c: ws.cell(row_idx, c).value

                direction_flag = str(col(4) or '').strip()  # D列
                balance_raw = col(11)  # K列
                balance = self._decimal(balance_raw)

                # 借贷方向
                if direction_flag == '贷':
                    direction = 'income'
                elif direction_flag == '借':
                    direction = 'expense'
                else:
                    direction = 'expense'

                # 金额：从余额变化推导
                amount = None
                if balance is not None and prev_balance is not None:
                    diff = prev_balance - balance
                    if diff > 0:
                        amount, direction = diff, 'expense'
                    elif diff < 0:
                        amount, direction = -diff, 'income'

                txn_datetime = col(3)  # C列 交易时间
                txn_date = self._parse_date(txn_datetime)
                txn_time = self._parse_time(txn_datetime)

                records.append(ParsedTransaction(
                    transaction_date=txn_date or datetime.date.today(),
                    transaction_time=txn_time,
                    amount=amount or Decimal('0'),
                    direction=direction,
                    balance=balance,
                    counterparty_name=str(col(5) or '').strip(),  # E列
                    counterparty_account=str(col(2) or '').strip(),  # B列
                    counterparty_bank=str(col(6) or '').strip(),  # F列
                    summary=str(col(8) or '').strip() or str(col(9) or '').strip(),  # H/I列
                    usage=str(col(7) or '').strip(),  # G列
                    bank_serial='',
                    raw_data={'凭证号': col(1), '借贷标志': direction_flag}
                ))

                if balance is not None:
                    prev_balance = balance

            except Exception:
                continue

        return records


# ─── 招商银行 ACCOUNT v2.0 ──────────────────────────────────────────────
class CMBAdapter(BankStatementAdapter):
    """
    格式：
    前13行为元数据，第13行(索引12)为表头，第14行开始为数据
    表头：交易日|交易时间|流水号|借方金额|贷方金额|余额|收(付)方名称|...
    """
    bank_code = 'CMB'
    bank_name = '招商银行'

    def detect(self, ws) -> bool:
        try:
            # CMB v2.0特征：Row5='对账单'(col2), Row6='接口版本' 2.0
            for row in range(1, 15):
                for col in range(1, 10):
                    val = str(ws.cell(row, col).value or '')
                    if val == '对账单':
                        # 确认是v2.0（旁边有'接口版本'）
                        for c in range(1, 6):
                            v2 = str(ws.cell(row + 1, c).value or '')
                            if v2 == '2.0':
                                return True
            return False
        except Exception:
            return False

    def parse(self, ws) -> list[ParsedTransaction]:
        # 找表头行（包含'交易日'的行，同时有'流水号'）
        header_row = None
        for r in range(1, ws.max_row + 1):
            row_vals = [str(ws.cell(r, c).value or '') for c in range(1, ws.max_column + 1)]
            has_txrq = any('交易日' in v for v in row_vals)
            has_lsh = any('流水号' in v for v in row_vals)
            if has_txrq and has_lsh:
                header_row = r
                break

        if header_row is None:
            return []

        # 读取表头
        headers = [str(ws.cell(header_row, c).value or '').strip() for c in range(1, ws.max_column + 1)]
        col_idx = {h: c for c, h in enumerate(headers, start=1)}

        def get_col(row, name):
            c = col_idx.get(name)
            return ws.cell(row, c).value if c else None

        records = []
        for row_idx in range(header_row + 1, ws.max_row + 1):
            try:
                debit = self._decimal(get_col(row_idx, '借方金额'))
                credit = self._decimal(get_col(row_idx, '贷方金额'))

                if debit is not None and debit > 0:
                    amount, direction = debit, 'expense'
                elif credit is not None and credit > 0:
                    amount, direction = credit, 'income'
                else:
                    continue

                txn_date = self._parse_date(get_col(row_idx, '交易日'))
                if not txn_date:
                    continue

                records.append(ParsedTransaction(
                    transaction_date=txn_date,
                    transaction_time=self._parse_time(get_col(row_idx, '交易时间')),
                    amount=amount,
                    direction=direction,
                    balance=self._decimal(get_col(row_idx, '余额')),
                    counterparty_name=str(get_col(row_idx, '收(付)方名称') or '').strip(),
                    counterparty_account=str(get_col(row_idx, '收(付)方账号') or '').strip(),
                    counterparty_bank=str(get_col(row_idx, '收(付)方开户行名') or '').strip(),
                    summary=str(get_col(row_idx, '摘要') or '').strip(),
                    usage=str(get_col(row_idx, '其它摘要') or '').strip(),
                    bank_serial=str(get_col(row_idx, '流水号') or '').strip(),
                    raw_data=dict(zip(headers, [ws.cell(row_idx, c).value for c in range(1, len(headers) + 1)]))
                ))
            except Exception:
                continue

        return records


# ─── 适配器注册表 ───────────────────────────────────────────────────────
ALL_ADAPTERS = [CMBAdapter, ICBCAdapter]  # CMB在前（更具体，先检测）


def detect_and_parse(file_content: bytes):
    """自动识别格式并解析，返回 (bank_code, transactions)"""
    import openpyxl
    wb = openpyxl.load_workbook(file_content, data_only=True)
    ws = wb.active

    for adapter_cls in ALL_ADAPTERS:
        adapter = adapter_cls()
        if adapter.detect(ws):
            return adapter_cls.bank_code, adapter.parse(ws)

    raise ValueError("无法识别银行格式，请确认文件为工商银行或招商银行对账单")


def parse_with_adapter(file_content: bytes, bank_code: str):
    """用指定银行适配器解析"""
    adapters = {a.bank_code: a for a in [cls() for cls in ALL_ADAPTERS]}
    if bank_code not in adapters:
        raise ValueError(f"不支持的银行: {bank_code}")
    import openpyxl
    wb = openpyxl.load_workbook(file_content, data_only=True)
    return adapters[bank_code].parse(wb.active)
