"""
银行流水导入视图
POST /api/finance/import/bank-statement/  - 解析银行流水（预览）
POST /api/finance/import/bank-statement/confirm/ - 确认导入
GET  /api/finance/import/bank-statement/banks/ - 获取支持的银行列表
"""
import datetime
import io
import uuid
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.finance.bank_adapters import (
    ALL_ADAPTERS, detect_and_parse, parse_with_adapter,
    ParsedTransaction
)
from apps.finance.models import Company, Income, Expense
from apps.finance.models_bank import BankAccount, BankStatement


# ─── 关键词自动分类规则 ────────────────────────────────────────────────
KEYWORD_RULES = [
    # (关键词, 方向, 描述)
    ('货款', 'income', '销售收款'),
    ('销售款', 'income', '销售收款'),
    ('收款', 'income', '销售收款'),
    ('退款', 'income', '退款'),
    ('退还款', 'income', '退款'),
    ('收息', 'income', '利息收入'),
    ('结息', 'income', '利息收入'),
    ('工资', 'expense', '工资'),
    ('代发', 'expense', '工资'),
    ('采购', 'expense', '采购'),
    ('货款付出', 'expense', '采购'),
    ('税费', 'expense', '税务'),
    ('税金', 'expense', '税务'),
    ('缴税', 'expense', '税务'),
    ('服务费', 'expense', '服务费'),
    ('代理费', 'expense', '服务费'),
    ('报销', 'expense', '报销'),
    ('往来', 'expense', '往来款'),
]


def classify_transaction(t: ParsedTransaction) -> tuple[str, str]:
    """
    根据摘要关键词自动分类
    返回: (direction_override, description)
    """
    summary = t.summary + t.usage
    for keyword, direction, desc in KEYWORD_RULES:
        if keyword in summary:
            return direction, desc
    return t.direction, ''


def match_counterparty(t: ParsedTransaction):
    """
    智能匹配对方
    返回: matched_type ('customer'/'supplier'/''), matched_name
    """
    from apps.crm.models import Client, Supplier

    name = t.counterparty_name.strip()
    account = t.counterparty_account.strip()

    if not name and not account:
        return '', ''

    # 模糊匹配：名称（优先）
    if name:
        client = Client.objects.filter(name__contains=name).first()
        if client:
            return 'customer', client.name

        supplier = Supplier.objects.filter(name__contains=name).first()
        if supplier:
            return 'supplier', supplier.name

    return '', ''


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def list_banks(request):
    """获取支持的银行列表"""
    banks = [
        {'code': a.bank_code, 'name': a.bank_name}
        for a in [cls() for cls in ALL_ADAPTERS]
    ]
    return Response({'banks': banks})


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def preview_bank_statement(request):
    """
    预览银行流水（不写入数据库）
    支持两种格式:
      1) multipart/form-data (原有方式): file + company_id
      2) application/json (新增): { company_id, bank_code, file_base64 }
    """
    import base64

    # ── 解析请求体 ───────────────────────────────────────────────────────
    content_type = request.content_type or ''

    if 'application/json' in content_type or (
        hasattr(request, 'data') and isinstance(request.data, dict) and 'file_base64' in request.data
    ):
        # JSON 方式: { company_id, bank_code?, file_base64 }
        body = request.data
        company_id = body.get('company_id')
        bank_code = body.get('bank_code', '')
        file_base64 = body.get('file_base64', '')
        try:
            content = base64.b64decode(file_base64)
        except Exception as e:
            return Response({'error': f'文件解码失败: {e}'}, status=400)
    else:
        # multipart 方式
        if 'file' not in request.FILES:
            return Response({'error': '请上传文件'}, status=400)
        company_id = request.data.get('company_id') or request.data.get('company')
        bank_code = request.data.get('bank_code', '')
        content = request.FILES['file'].read()

    if not company_id:
        return Response({'error': '缺少 company_id'}, status=400)

    try:
        company = Company.objects.get(id=company_id)
    except Company.DoesNotExist:
        return Response({'error': '公司不存在'}, status=400)

    # ── 解析银行流水 ──────────────────────────────────────────────────────
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

    # 批量匹配
    preview_rows = []
    total_income = Decimal('0')
    total_expense = Decimal('0')

    for t in transactions:
        direction, desc = classify_transaction(t)
        match_type, match_name = match_counterparty(t)

        # 方向纠正（如果关键词分类与银行方向冲突，以关键词为准）
        final_direction = direction if direction != t.direction else t.direction
        if desc:
            final_desc = desc
        else:
            final_desc = '银行转账'

        if final_direction == 'income':
            total_income += t.amount
        else:
            total_expense += t.amount

        preview_rows.append({
            'transaction_date': t.transaction_date.isoformat() if t.transaction_date else '',
            'transaction_time': t.transaction_time.isoformat() if t.transaction_time else '',
            'direction': final_direction,
            'direction_display': '收入' if final_direction == 'income' else '支出',
            'amount': str(t.amount),
            'balance': str(t.balance) if t.balance else '',
            'counterparty_name': t.counterparty_name,
            'counterparty_account': t.counterparty_account,
            'summary': t.summary[:100],
            'bank_serial': t.bank_serial,
            'auto_description': final_desc,
            'match_type': match_type,
            'match_name': match_name,
            'dedup_key': t.bank_serial or f"{t.transaction_date}_{t.counterparty_account}_{t.amount}",
        })

    return Response({
        'bank_code': used_bank,
        'total_count': len(transactions),
        'total_income': str(total_income),
        'total_expense': str(total_expense),
        'preview_rows': preview_rows[:200],  # 最多返回200条预览
        'has_more': len(transactions) > 200,
    })


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def confirm_bank_import(request):
    """
    确认导入银行流水
    POST body:
      - company_id: 公司ID
      - bank_account_id: 银行账户ID（可选，新建则传bank_code+account_no）
      - bank_code: 银行代码
      - account_no: 账号（新建账户时）
      - account_name: 账户名（新建账户时）
      - transactions: [{transaction_date, direction, amount, ...}]
      - auto_create_records: bool 是否自动生成收入/支出记录
    """
    company_id = request.data.get('company_id')
    bank_account_id = request.data.get('bank_account_id')
    bank_code = request.data.get('bank_code', '')
    account_no = request.data.get('account_no', '')
    account_name = request.data.get('account_name', '')
    transactions_data = request.data.get('transactions', [])
    auto_create = request.data.get('auto_create_records', False)

    if not company_id or not transactions_data:
        return Response({'error': '缺少必要参数'}, status=400)

    try:
        company = Company.objects.get(id=company_id)
    except Company.DoesNotExist:
        return Response({'error': '公司不存在'}, status=400)

    # 获取或创建银行账户
    bank_account: BankAccount
    if bank_account_id:
        try:
            bank_account = BankAccount.objects.get(id=bank_account_id)
        except BankAccount.DoesNotExist:
            return Response({'error': '银行账户不存在'}, status=400)
    elif account_no:
        bank_account, _ = BankAccount.objects.get_or_create(
            company=company,
            account_no=account_no,
            defaults={
                'bank_code': bank_code,
                'bank_name': dict(BankAccount.BANK_CHOICES).get(bank_code, bank_code),
                'account_name': account_name,
            }
        )
    else:
        return Response({'error': '缺少银行账户信息'}, status=400)

    # 生成批次号
    batch_no = uuid.uuid4().hex[:12]
    now = timezone.now()

    imported = 0
    skipped = 0
    errors = []
    created_income_ids = []
    created_expense_ids = []

    for item in transactions_data:
        try:
            dedup_key = item.get('dedup_key', '')
            if not dedup_key:
                dedup_key = f"{item['transaction_date']}_{item.get('counterparty_account','')}_{item['amount']}"

            # 去重检查
            existing = BankStatement.objects.filter(
                company=company,
                bank_account=bank_account,
                transaction_date=item['transaction_date'],
                amount=Decimal(item['amount']),
            ).filter(
                counterparty_account=item.get('counterparty_account', '')
            ).exists()

            if existing:
                skipped += 1
                continue

            # 创建银行流水记录
            stmt = BankStatement.objects.create(
                company=company,
                bank_account=bank_account,
                transaction_date=item['transaction_date'],
                transaction_time=item.get('transaction_time'),
                direction=item['direction'],
                amount=Decimal(item['amount']),
                balance=Decimal(item['balance']) if item.get('balance') else None,
                counterparty_name=item.get('counterparty_name', ''),
                counterparty_account=item.get('counterparty_account', ''),
                counterparty_bank=item.get('counterparty_bank', ''),
                summary=item.get('summary', ''),
                usage=item.get('usage', ''),
                bank_serial=item.get('bank_serial', ''),
                source_bank=bank_code,
                import_batch=batch_no,
            )

            # 可选：自动生成收入/支出记录
            if auto_create:
                direction = item['direction']
                description = item.get('auto_description', item.get('summary', '银行流水'))
                counterparty = item.get('counterparty_name', '')
                remark = f"[银行流水] {description} {item.get('summary', '')}"

                if direction == 'income':
                    income = Income.objects.create(
                        company=company,
                        amount=Decimal(item['amount']),
                        date=item['transaction_date'],
                        source='bank_import',
                        customer=counterparty,
                        description=remark,
                        operator=request.user,
                    )
                    stmt.matched_income = income
                    stmt.reconcile_status = 'matched'
                    stmt.save(update_fields=['matched_income', 'reconcile_status'])
                    created_income_ids.append(income.id)
                else:
                    expense = Expense.objects.create(
                        company=company,
                        amount=Decimal(item['amount']),
                        expense_date=item['transaction_date'],
                        date=item['transaction_date'],
                        expense_type='expense',
                        supplier=counterparty,
                        description=remark,
                        operator=request.user,
                    )
                    stmt.matched_expense = expense
                    stmt.reconcile_status = 'matched'
                    stmt.save(update_fields=['matched_expense', 'reconcile_status'])
                    created_expense_ids.append(expense.id)

            imported += 1

        except Exception as e:
            errors.append({'row': item.get('transaction_date', ''), 'error': str(e)})

    return Response({
        'success': True,
        'imported': imported,
        'skipped': skipped,
        'errors': errors,
        'batch_no': batch_no,
        'auto_created': {
            'income_count': len(created_income_ids),
            'expense_count': len(created_expense_ids),
        }
    })
