from rest_framework import serializers
from .models import Company, Income, Expense, WageRecord, Invoice, Employee, CompanySocialConfig, EmployeeCompany, SocialRecord, Budget
from .models_bank import BankAccount, BankStatement
from apps.core.models import UserCompanyRole


# ── 公司访问校验 ──────────────────────────────────────
def _get_request_user(serializer):
    """安全地从serializer context获取当前用户"""
    request = serializer.context.get('request')
    return getattr(request, 'user', None) if request else None


def validate_company_access(serializer, attrs, field_name='company'):
    """校验用户有权操作指定公司（仅非超级用户）"""
    user = _get_request_user(serializer)
    if user and not user.is_superuser:
        val = attrs.get(field_name)
        if val:
            company_id = getattr(val, 'id', val)
            has_access = UserCompanyRole.objects.filter(
                user=user, company_id=company_id
            ).exists()
            if not has_access:
                raise serializers.ValidationError(
                    {field_name: f'无权操作该公司(ID={company_id})'}
                )
    return attrs


class CompanyAccessValidatorMixin:
    """Serializer Mixin：自动校验 company/company_id 字段的访问权限"""

    def validate_company(self, value):
        return self._check_company(value, 'company')

    def validate_company_id(self, value):
        return self._check_company(value, 'company_id')

    def _check_company(self, value, field_name):
        user = _get_request_user(self)
        if user and not user.is_superuser:
            company_id = getattr(value, 'id', value)
            if company_id:
                has_access = UserCompanyRole.objects.filter(
                    user=user, company_id=company_id
                ).exists()
                if not has_access:
                    raise serializers.ValidationError(
                        f'无权操作该公司(ID={company_id})'
                    )
        return value


# ── 脱敏工具 ──────────────────────────────────────────
def _mask(value, prefix=6, suffix=4, placeholder='****'):
    """通用脱敏：保留前 prefix 位 + placeholder + 后 suffix 位"""
    s = str(value)
    if len(s) <= prefix + suffix:
        return s[:prefix] + placeholder if len(s) > prefix else s
    return s[:prefix] + placeholder + s[-suffix:]


class MaskedCharField(serializers.CharField):
    """自动脱敏字段：写入时存完整值，读取时返回脱敏值"""
    def __init__(self, prefix=6, suffix=4, **kwargs):
        self._mask_prefix = prefix
        self._mask_suffix = suffix
        super().__init__(**kwargs)

    def to_representation(self, value):
        value = super().to_representation(value)
        if not value:
            return value
        return _mask(value, self._mask_prefix, self._mask_suffix)


# ── 脱敏专用快捷方式 ───────────────────────────────────
_id_card = lambda **kw: MaskedCharField(prefix=6, suffix=4, **kw)
_bank_card = lambda **kw: MaskedCharField(prefix=6, suffix=4, **kw)
_phone = lambda **kw: MaskedCharField(prefix=3, suffix=4, **kw)


class CompanySerializer(serializers.ModelSerializer):
    """公司序列化器"""
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Company
        fields = [
            'id', 'name', 'code', 'status', 'status_display',
            'contact_person', 'contact_phone', 'address',
            'tax_id', 'bank_name', 'bank_account',
            'remark', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class IncomeSerializer(CompanyAccessValidatorMixin, serializers.ModelSerializer):
    """收入序列化器"""
    company_name = serializers.CharField(source='company.name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True, allow_null=True)
    operator_name = serializers.CharField(source='operator.username', read_only=True, allow_null=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    source_display = serializers.SerializerMethodField()
    income_category_display = serializers.CharField(source='get_income_category_display', read_only=True)
    approval_status = serializers.SerializerMethodField()
    # 反向追溯：关联的银行流水
    bank_statement = serializers.SerializerMethodField()
    # CRM 标准化：关联客户
    client_ref_name = serializers.CharField(source='client_ref.name', read_only=True, allow_null=True)

    class Meta:
        model = Income
        fields = [
            'id', 'company', 'company_name', 'amount', 'date', 'source',
            'source_display', 'income_category', 'income_category_display', 'status', 'status_display',
            'project', 'project_name',
            'customer', 'client_ref', 'client_ref_name', 'description', 'attachment', 'operator',
            'operator_name', 'approval_flow', 'approval_status',
            'bank_statement',
            # ── 银行流水11字段扩展 ────────────────────────────────────────
            'transaction_time', 'balance',
            'counterparty_account', 'counterparty_bank',
            'transaction_type', 'summary',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'operator', 'operator_name', 'approval_flow', 'approval_status',
            'created_at', 'updated_at',
            # 银行流水来源字段，人工录入不填
            'transaction_time', 'balance',
            'counterparty_account', 'counterparty_bank',
            'transaction_type', 'summary',
        ]

    def get_approval_status(self, obj):
        try:
            if obj.approval_flow_id and obj.approval_flow:
                return obj.approval_flow.status
        except Exception:
            pass
        return None

    def get_source_display(self, obj):
        if obj.source in ('bank_import', '网银'):
            return '网银'
        # 中文来源值也显示为网银（如IBPS对公提回贷记/代发工资等）
        if obj.source and any(k in obj.source for k in ['IBPS', '代发', '转账', '提回', '贷记', '借记', '网银', '电子']):
            return '网银'
        source_map = {
            'contract': '合同收入',
            'project': '项目收入',
            'service': '服务收入',
            'other': '其他'
        }
        return source_map.get(obj.source, obj.source or '网银')

    def get_bank_statement(self, obj):
        """反向追溯：关联的银行流水摘要"""
        stmts = obj.matched_statements.all()
        return BankStatementSerializer(stmts, many=True).data

    def create(self, validated_data):
        income = super().create(validated_data)
        # 审批流由 IncomeViewSet.perform_create() 处理，这里不再创建
        return income



class ExpenseSerializer(CompanyAccessValidatorMixin, serializers.ModelSerializer):
        """支出序列化器"""
        company_name = serializers.CharField(source='company.name', read_only=True)
        project_name = serializers.CharField(source='project.name', read_only=True, allow_null=True)
        operator_name = serializers.CharField(source='operator.username', read_only=True, allow_null=True)
        expense_type_display = serializers.CharField(source='get_expense_type_display', read_only=True)
        date = serializers.SerializerMethodField()
        expense_date = serializers.DateField(help_text='支出日期', required=False, allow_null=True)
        approval_status = serializers.SerializerMethodField()
        status_display = serializers.CharField(source='get_status_display', read_only=True)
        bank_statement = serializers.SerializerMethodField()
        source_display = serializers.SerializerMethodField()
        # CRM 标准化：关联供应商
        supplier_ref_name = serializers.CharField(source='supplier_ref.name', read_only=True, allow_null=True)

        class Meta:
            model = Expense
            fields = [
                'id', 'company', 'company_name', 'amount', 'expense_type', 'expense_type_display',
                'date', 'expense_date', 'expense_category', 'source', 'source_display', 'project', 'project_name',
                'supplier', 'supplier_ref', 'supplier_ref_name', 'note', 'description', 'attachment', 'operator',
                'operator_name', 'approval_flow', 'approval_status', 'status', 'status_display',
                'bank_statement',
                # ── 银行流水11字段扩展 ────────────────────────────────────────
                'transaction_time', 'balance',
                'counterparty_account', 'counterparty_bank',
                'transaction_type', 'summary',
                'created_at', 'updated_at'
            ]
            read_only_fields = [
                'id', 'operator', 'operator_name', 'approval_status',
                'transaction_time', 'balance',
                'counterparty_account', 'counterparty_bank',
                'transaction_type', 'summary',
                'created_at', 'updated_at'
            ]

        def get_source_display(self, obj):
            if obj.source in ('bank_import', '网银'):
                return '网银'
            return obj.source or '网银'

        def get_approval_status(self, obj):
            try:
                if obj.approval_flow_id and obj.approval_flow:
                    return obj.approval_flow.status
            except Exception:
                pass
            return None

        def get_date(self, obj):
            if obj.date:
                return obj.date.isoformat()
            return None

        def get_bank_statement(self, obj):
            """反向追溯：关联的银行流水摘要"""
            stmts = obj.matched_statements.all()
            return BankStatementSerializer(stmts, many=True).data

        def create(self, validated_data):
            expense_date = validated_data.pop('expense_date', None)
            if expense_date:
                validated_data['date'] = expense_date
            expense = super().create(validated_data)
            return expense

        def update(self, instance, validated_data):
            expense_date = validated_data.pop('expense_date', None)
            if expense_date:
                instance.date = expense_date
                instance.expense_date = expense_date
            return super().update(instance, validated_data)


class WageRecordSerializer(CompanyAccessValidatorMixin, serializers.ModelSerializer):
    """工资单序列化器"""
    company_name = serializers.CharField(source='company.name', read_only=True)
    approver_name = serializers.CharField(source='approver.username', read_only=True, allow_null=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    month_display = serializers.SerializerMethodField()
    approval_flow_id = serializers.SerializerMethodField()
    # employee_company: 员工在公司任职的记录（可写，前端传来ID）
    employee_company = serializers.PrimaryKeyRelatedField(
        required=False, allow_null=True, queryset=EmployeeCompany.objects.all()
    )
    employee_company_display = serializers.SerializerMethodField()

    def to_representation(self, obj):
        return super().to_representation(obj)

    def get_approval_flow_id(self, obj):
        try:
            return obj.approval_flow.id if obj.approval_flow else None
        except Exception:
            return None

    # 优先取 employee_company（多公司任职记录），其次 employee FK，最后 employee_name 字符串
    employee_name = serializers.SerializerMethodField()
    employee_code = serializers.SerializerMethodField()
    employee_phone = serializers.SerializerMethodField()
    employee_bank_card = serializers.SerializerMethodField()
    department_name = serializers.SerializerMethodField()
    position = serializers.SerializerMethodField()
    bank_card = MaskedCharField(prefix=6, suffix=4)

    class Meta:
        model = WageRecord
        fields = [
            'id', 'company', 'company_name',
            'employee', 'employee_company', 'employee_company_display',
            'employee_name', 'employee_code', 'employee_phone',
            'employee_bank_card', 'department_name',
            'bank_card',
            # 应发项目
            'base_salary', 'position_salary', 'overtime_pay', 'bonus',
            'commission', 'meal_allowance', 'transport_allowance',
            'communication_allowance', 'other_allowance',
            # 社保公积金
            'social_insurance', 'housing_fund',
            # 其他扣款
            'leave_days', 'leave_deduction',
            'sick_leave_days', 'sick_leave_deduction',
            'late_times',
            'employee_loan_repayment', 'other_loan', 'other_deductions',
            # 专项附加扣除
            'children_education', 'continuing_education', 'serious_illness',
            'housing_loan', 'housing_rent', 'elderly_support', 'infant_care',
            # 计算项
            'gross_salary', 'total_deduction', 'taxable_salary',
            'tax', 'cumulative_tax', 'prior_cumulative_tax', 'net_salary',
            # 基本信息
            'year', 'month', 'month_display',
            'department', 'position', 'status', 'status_display',
            'approver', 'approver_name', 'approved_at', 'paid_at',
            'approval_flow', 'approval_flow_id',
            'remarks', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'approver', 'approved_at', 'paid_at', 'created_at', 'updated_at'
        ]

    # 计算字段（gross_salary, total_deduction, taxable_salary, tax, cumulative_tax, net_salary）
    # 由模型save()重新计算，前端传入的值会被忽略
    # 注意：不在这里pop了，因为validate()已正确设置employee_name，
    # 模型save()会从employee_company自动填充employee_name用于累计查询
    CALC_FIELDS = {'gross_salary', 'total_deduction', 'taxable_salary', 'tax', 'cumulative_tax', 'net_salary'}

    def create(self, validated_data):
        for f in self.CALC_FIELDS:
            validated_data.pop(f, None)
        # validate()已用employee_company正确填充employee_name，这里确保它不被覆盖
        return super().create(validated_data)

    def update(self, instance, validated_data):
        for f in self.CALC_FIELDS:
            validated_data.pop(f, None)
        return super().update(instance, validated_data)

    def get_month_display(self, obj):
        return f'{obj.month}月'

    def _get_employee_company(self, obj):
        """获取 employee_company，优先从预加载的缓存读取"""
        if hasattr(obj, '_employee_company_cache'):
            return obj._employee_company_cache
        if obj.employee_company_id and obj.employee_company_id not in (None, ''):
            try:
                return obj.employee_company
            except EmployeeCompany.DoesNotExist:
                return None
        return None

    def _safe_ec_employee(self, ec):
        """安全获取 employee，处理已删除员工导致的 DoesNotExist"""
        try:
            return ec.employee
        except EmployeeCompany.DoesNotExist:
            return None
        except Employee.DoesNotExist:
            return None

    def _safe_ec_company(self, ec):
        """安全获取 company，处理已删除公司导致的 DoesNotExist"""
        try:
            return ec.company
        except EmployeeCompany.DoesNotExist:
            return None
        except Company.DoesNotExist:
            return None

    def get_employee_company_display(self, obj):
        ec = self._get_employee_company(obj)
        if not ec:
            return None
        emp = self._safe_ec_employee(ec)
        comp = self._safe_ec_company(ec)
        if emp and comp:
            return f'{emp.name}@{comp.name}({ec.department}/{ec.position})'
        return None

    def get_employee_name(self, obj):
        ec = self._get_employee_company(obj)
        if ec:
            emp = self._safe_ec_employee(ec)
            return emp.name if emp else None
        return obj.employee.name if obj.employee else (obj.employee_name or None)

    def get_employee_code(self, obj):
        ec = self._get_employee_company(obj)
        if ec:
            emp = self._safe_ec_employee(ec)
            return emp.code if emp else None
        return obj.employee.code if obj.employee else None

    def get_employee_phone(self, obj):
        ec = self._get_employee_company(obj)
        if ec:
            emp = self._safe_ec_employee(ec)
            val = emp.phone if emp else None
        else:
            val = obj.employee.phone if obj.employee else None
        return _mask(val, 3, 4) if val else val

    def get_employee_bank_card(self, obj):
        ec = self._get_employee_company(obj)
        if ec:
            emp = self._safe_ec_employee(ec)
            val = emp.bank_card if emp else None
        else:
            val = obj.employee.bank_card if obj.employee else None
        return _mask(val, 6, 4) if val else val

    def get_department_name(self, obj):
        ec = self._get_employee_company(obj)
        if ec:
            return ec.department
        return obj.employee.department if obj.employee else obj.department

    def get_position(self, obj):
        ec = self._get_employee_company(obj)
        if ec:
            return ec.position
        return obj.employee.position if obj.employee else obj.position

    def validate(self, attrs):
        gross = float(attrs.get('gross_salary') or 0)
        net = float(attrs.get('net_salary') or 0)
        if net > gross > 0:
            raise serializers.ValidationError({
                'net_salary': f'实发工资({net})不能大于应发工资({gross})'
            })
        # 如果传了 employee_company，自动用其关联的 employee 和 employee_name 填充
        ec = attrs.get('employee_company')
        if ec:
            attrs['employee'] = ec.employee
            attrs['employee_name'] = ec.employee.name
            # 用 employee_company 里的 department/position 填充
            if not attrs.get('department'):
                attrs['department'] = ec.department
            if not attrs.get('position'):
                attrs['position'] = ec.position
        return attrs


class InvoiceSerializer(CompanyAccessValidatorMixin, serializers.ModelSerializer):
    """发票序列化器"""
    company_name = serializers.CharField(source='company.name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True, allow_null=True)
    project_id = serializers.IntegerField(source='project.id', read_only=True, allow_null=True)
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    invoice_type_display = serializers.CharField(source='get_invoice_type_display', read_only=True)
    is_credited_display = serializers.SerializerMethodField()
    matched_bank_statement_name = serializers.SerializerMethodField()
    red_invoice_for_no = serializers.SerializerMethodField()
    has_red_invoices = serializers.SerializerMethodField()
    is_negative = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = [
            'id', 'invoice_no', 'type', 'type_display', 'amount',
            'invoice_type', 'invoice_type_display', 'tax_rate', 'tax_amount',
            'counterparty', 'is_credited', 'is_credited_display',
            'credited_period',
            'counterparty_tax_id', 'counterparty_bank',
            'project', 'project_id', 'project_name', 'company', 'company_name',
            'status', 'status_display', 'issue_date', 'due_date',
            'payment_date', 'matched_bank_statement',
            'remarks', 'created_at', 'updated_at',
            'matched_bank_statement', 'matched_bank_statement_name',
            'attachment', 'attachment_name',
            'red_invoice_for', 'red_invoice_for_no', 'has_red_invoices', 'is_negative',
        ]
        extra_kwargs = {
            'invoice_no': {'required': False},
        }
        read_only_fields = ['id', 'tax_amount', 'created_at', 'updated_at']

    def get_is_credited_display(self, obj):
        return '已认证' if obj.is_credited else '未认证'

    def get_matched_bank_statement_name(self, obj):
        if obj.matched_bank_statement:
            bs = obj.matched_bank_statement
            return f'{bs.transaction_date} {bs.counterparty_name} ¥{bs.amount}'
        return None

    def get_red_invoice_for_no(self, obj):
        if obj.red_invoice_for:
            return obj.red_invoice_for.invoice_no
        return None

    def get_has_red_invoices(self, obj):
        return obj.red_invoices.exists()

    def get_is_negative(self, obj):
        return float(obj.amount or 0) < 0

    def create(self, validated_data):
        # 自动生成发票号：只从 INV-NNNNNN 标准格式中找最大数字
        if not validated_data.get('invoice_no'):
            existing_nos = list(Invoice.objects.values_list('invoice_no', flat=True))
            max_num = 0
            for no in existing_nos:
                try:
                    # 只识别 INV-000001 格式（-后是纯数字）
                    parts = no.split('-')
                    if len(parts) == 2 and parts[1].isdigit() and len(parts[1]) == 6:
                        max_num = max(max_num, int(parts[1]))
                except (ValueError, IndexError):
                    pass
            num = max_num + 1
            validated_data['invoice_no'] = f'INV-{num:06d}'
        return super().create(validated_data)


class EmployeeCompanySerializer(serializers.ModelSerializer):
    """员工-公司关联序列化器"""
    company_name = serializers.CharField(source='company.name', read_only=True)
    employee_name = serializers.CharField(source='employee.name', read_only=True)
    status_display = serializers.SerializerMethodField()

    class Meta:
        model = EmployeeCompany
        fields = [
            'id', 'employee', 'employee_name', 'company', 'company_name',
            'department', 'position', 'is_primary',
            'hire_date', 'leave_date', 'status', 'status_display',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    def get_status_display(self, obj):
        return '在职' if obj.status == 'active' else ('已离职' if obj.status == 'resigned' else obj.status)


class EmployeeSerializer(serializers.ModelSerializer):
    """员工序列化器"""
    company_name = serializers.CharField(source='company.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    has_social_insurance_display = serializers.SerializerMethodField()
    has_housing_fund_display = serializers.SerializerMethodField()
    # 多公司关联列表（只读，嵌套展示）
    companies = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = [
            'id', 'code', 'name', 'id_card', 'phone', 'bank_card', 'bank_name',
            'department', 'position', 'company', 'company_name',
            'hire_date', 'leave_date', 'status', 'status_display',
            'has_social_insurance', 'has_social_insurance_display',
            'has_housing_fund', 'has_housing_fund_display',
            'social_insurance_deduction', 'housing_fund_deduction',
            'housing_fund_employee', 'housing_fund_company',
            'base_salary', 'position_salary',
            'meal_allowance', 'transport_allowance', 'communication_allowance', 'other_allowance',
            'leave_deduction_per_day', 'late_deduction_per_time',
            'employee_loan_repayment', 'other_fixed_deduction',
            'email', 'emergency_contact', 'emergency_phone',
            'remarks',
            'companies',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'code', 'created_at', 'updated_at']

    # 脱敏字段
    id_card = _id_card()
    phone = _phone()
    bank_card = _bank_card()

    def get_has_social_insurance_display(self, obj):
        return '是' if obj.has_social_insurance else '否'

    def get_has_housing_fund_display(self, obj):
        return '是' if obj.has_housing_fund else '否'

    def get_companies(self, obj):
        links = obj.company_links.all()
        return EmployeeCompanySerializer(links, many=True, context=self.context).data

    def create(self, validated_data):
        # 自动生成员工工号
        if not validated_data.get('code'):
            all_codes = Employee.objects.filter(code__startswith='YG-').values_list('code', flat=True)
            max_num = 0
            for code in all_codes:
                try:
                    num = int(code.split('-')[-1])
                    max_num = max(max_num, num)
                except (ValueError, IndexError):
                    pass
            validated_data['code'] = f'YG-{(max_num+1):04d}'
        return super().create(validated_data)


class CompanySocialConfigSerializer(serializers.ModelSerializer):
    """公司社保公积金配置序列化器"""
    company_name = serializers.CharField(source='company.name', read_only=True)

    class Meta:
        model = CompanySocialConfig
        fields = [
            'id', 'company', 'company_name',
            'social_base',
            'pension_rate_employee', 'pension_rate_company',
            'medical_rate_employee', 'medical_rate_company',
            'unemployment_rate_employee', 'unemployment_rate_company',
            'injury_rate_company',
            'housing_fund_base',
            'housing_fund_rate_employee', 'housing_fund_rate_company',
        ]
        read_only_fields = ['id']


class SocialRecordSerializer(serializers.ModelSerializer):
    """社保申报记录序列化器"""
    company_name = serializers.CharField(source='company.name', read_only=True)
    employee_name = serializers.SerializerMethodField()
    employee_code = serializers.SerializerMethodField(allow_null=True)
    is_reconciled_display = serializers.CharField(source='get_is_reconciled_display', read_only=True)
    # 分开合计（社保 vs 公积金）
    social_total_employee = serializers.SerializerMethodField()
    social_total_company = serializers.SerializerMethodField()

    class Meta:
        model = SocialRecord
        fields = [
            'id', 'company', 'company_name',
            'employee', 'employee_name', 'employee_code', 'id_card',
            'year_month',
            # 分险种明细
            'pension_employee', 'pension_company',
            'pension_bup_employee', 'pension_bup_company',
            'medical_employee', 'medical_company',
            'unemployment_employee', 'unemployment_company',
            'injury_company', 'birth_company',
            'housing_fund_employee', 'housing_fund_company',
            # 合计
            'total_employee', 'total_company', 'total',
            'social_total_employee', 'social_total_company',
            # 核销
            'is_reconciled', 'is_reconciled_display', 'reconciled_at',
            # 其他
            'remark', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'total_employee', 'total_company', 'total',
            'created_at', 'updated_at',
        ]

    # 脱敏字段
    id_card = _id_card()

    def get_employee_name(self, obj):
        if obj.employee:
            return obj.employee.name
        if obj.name:
            return obj.name
        mask = obj.id_card[-4:] if len(obj.id_card) >= 4 else obj.id_card
        return f'未知({mask})'

    def get_employee_code(self, obj):
        if obj.employee:
            return obj.employee.code
        return None

    def get_social_total_employee(self, obj):
        return float(obj.pension_employee or 0) + float(obj.pension_bup_employee or 0) + \
               float(obj.medical_employee or 0) + float(obj.unemployment_employee or 0)

    def get_social_total_company(self, obj):
        return float(obj.pension_company or 0) + float(obj.pension_bup_company or 0) + \
               float(obj.medical_company or 0) + float(obj.unemployment_company or 0) + \
               float(obj.injury_company or 0) + float(obj.birth_company or 0)


class BankStatementSerializer(serializers.ModelSerializer):
    """银行流水序列化器"""
    company_name = serializers.CharField(source='company.name', read_only=True)
    bank_account_name = serializers.CharField(source='bank_account.account_name', read_only=True, default='')
    direction_display = serializers.CharField(source='get_direction_display', read_only=True)
    reconcile_status_display = serializers.CharField(source='get_reconcile_status_display', read_only=True, default='')
    matched_income_amount = serializers.SerializerMethodField()
    matched_expense_amount = serializers.SerializerMethodField()

    class Meta:
        model = BankStatement
        fields = [
            'id', 'company', 'company_name',
            'bank_account', 'bank_account_name',
            'transaction_date', 'transaction_time',
            'direction', 'direction_display',
            'amount', 'balance',
            'counterparty_name', 'counterparty_account', 'counterparty_bank',
            'summary', 'usage',
            'matched_income', 'matched_expense',
            'matched_income_amount', 'matched_expense_amount',
            'reconcile_status', 'reconcile_status_display',
            'source_bank', 'import_batch', 'created_at',
        ]

    def get_matched_income_amount(self, obj):
        if obj.matched_income:
            return str(obj.matched_income.amount)
        return ''

    def get_matched_expense_amount(self, obj):
        if obj.matched_expense:
            return str(obj.matched_expense.amount)
        return ''


class BankAccountSerializer(serializers.ModelSerializer):
    """银行账户序列化器"""
    bank_display = serializers.CharField(source='get_bank_code_display', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)
    statement_count = serializers.SerializerMethodField()

    class Meta:
        model = BankAccount
        fields = [
            'id', 'company', 'company_name',
            'bank_code', 'bank_display', 'bank_name',
            'account_no', 'account_name', 'is_active',
            'created_at', 'statement_count',
        ]
        read_only_fields = ['created_at']

    # 脱敏字段
    account_no = _bank_card()

    def get_statement_count(self, obj):
        return obj.statements.count()


class BudgetSerializer(serializers.ModelSerializer):
    """预算序列化器"""
    company_name = serializers.CharField(source='company.name', read_only=True)
    expense_type_display = serializers.CharField(source='get_expense_type_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True, allow_null=True)

    class Meta:
        model = Budget
        fields = [
            'id', 'company', 'company_name', 'year', 'month',
            'expense_type', 'expense_type_display',
            'budget_amount', 'note', 'created_by', 'created_by_name',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_by', 'created_by_name', 'created_at', 'updated_at']
