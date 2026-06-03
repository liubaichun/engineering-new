"""FactoryBoy factories for finance models"""

import factory
from decimal import Decimal
import datetime


class EmployeeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'finance.Employee'
        skip_postgeneration_save = True

    code = factory.Sequence(lambda n: f'EMP{n:04d}')
    name = factory.Sequence(lambda n: f'员工_{n:04d}')
    id_card = factory.Sequence(lambda n: f'11010119900101{n:04d}')
    phone = '13800138000'
    department = '技术部'
    position = '工程师'
    status = 'active'
    employee_loan_repayment = Decimal('0')
    other_fixed_deduction = Decimal('0')
    base_salary = Decimal('5000')
    position_salary = Decimal('3000')
    meal_allowance = Decimal('200')
    transport_allowance = Decimal('100')
    communication_allowance = Decimal('50')
    other_allowance = Decimal('0')
    leave_deduction_per_day = Decimal('200')
    late_deduction_per_time = Decimal('50')

    @factory.post_generation
    def company(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            self.company = extracted
            self.save()


class EmployeeCompanyFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'finance.EmployeeCompany'

    department = '技术部'
    position = '工程师'
    is_primary = True
    status = 'active'

    @factory.post_generation
    def employee(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            self.employee = extracted
            self.save()

    @factory.post_generation
    def company(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            self.company = extracted
            self.save()


class InvoiceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'finance.Invoice'
        skip_postgeneration_save = True

    invoice_no = factory.Sequence(lambda n: f'INV{n:08d}')
    type = 'income'  # income=收到, expense=开出
    invoice_type = 'normal'
    amount = Decimal('10000.00')
    tax_rate = Decimal('0.13')
    tax_amount = Decimal('1300.00')
    counterparty = '测试客户'
    status = 'pending'
    issue_date = factory.LazyFunction(datetime.date.today)
    is_credited = False

    @factory.post_generation
    def company(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            self.company = extracted
            self.save()


class SocialRecordFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'finance.SocialRecord'

    name = factory.Sequence(lambda n: f'员工_{n:04d}')
    id_card = factory.Sequence(lambda n: f'11010119900101{n:04d}')
    year_month = '202605'
    pension_employee = Decimal('500')
    pension_company = Decimal('1000')
    medical_employee = Decimal('200')
    medical_company = Decimal('800')
    unemployment_employee = Decimal('50')
    unemployment_company = Decimal('100')
    injury_company = Decimal('100')
    birth_company = Decimal('200')
    housing_fund_employee = Decimal('500')
    housing_fund_company = Decimal('500')
    total_employee = Decimal('1250')
    total_company = Decimal('2700')
    total = Decimal('3950')
    is_reconciled = False

    @factory.post_generation
    def company(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            self.company = extracted
            self.save()

    @factory.post_generation
    def employee(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            self.employee = extracted
            self.save()


class WageRecordFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'finance.WageRecord'

    employee_name = factory.Sequence(lambda n: f'员工_{n:04d}')
    base_salary = Decimal('5000')
    position_salary = Decimal('3000')
    gross_salary = Decimal('8500')
    social_insurance = Decimal('1250')
    housing_fund = Decimal('500')
    total_deduction = Decimal('2000')
    taxable_salary = Decimal('6500')
    tax = Decimal('195')
    net_salary = Decimal('6305')
    year = 2026
    month = 5
    status = 'draft'

    @factory.post_generation
    def company(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            self.company = extracted
            self.save()

    @factory.post_generation
    def employee(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            self.employee = extracted
            self.save()


class IncomeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'finance.Income'

    amount = Decimal('50000.00')
    date = factory.LazyFunction(datetime.date.today)
    customer = '测试客户'
    source = '银行导入'
    status = 'pending'
    summary = '测试收入'
    company = factory.SubFactory('tests.factories.core.CompanyFactory')


class ExpenseFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'finance.Expense'

    amount = Decimal('30000.00')
    date = factory.LazyFunction(datetime.date.today)
    supplier = '测试供应商'
    source = '银行导入'
    status = 'pending'
    summary = '测试支出'
    expense_category = '办公费'
    company = factory.SubFactory('tests.factories.core.CompanyFactory')
