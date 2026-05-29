import functools
from django.db.models import F, Q, Sum
from urllib.parse import urlparse
from rest_framework import viewsets, filters, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import render
from rest_framework.permissions import AllowAny
from django_filters.rest_framework import DjangoFilterBackend, FilterSet, CharFilter, NumberFilter
from django.db import models
from django.db.models import F, Q, Sum, Sum, Count
from django.db.models.functions import TruncMonth
from django.utils import timezone
from .models import Company, Income, Expense, WageRecord, Invoice, Employee, CompanySocialConfig, EmployeeCompany, SocialRecord, Budget
from .models_bank import BankAccount, BankStatement
from .serializers import (
    CompanySerializer,
    IncomeSerializer,
    ExpenseSerializer,
    WageRecordSerializer,
    InvoiceSerializer,
    EmployeeSerializer,
    CompanySocialConfigSerializer,
    EmployeeCompanySerializer,
    BankAccountSerializer,
    SocialRecordSerializer,
    BudgetSerializer,
)
from .filters import WageRecordFilter, CompanyFilter, IncomeFilter, ExpenseFilter, InvoiceFilter
from apps.approvals.models import ApprovalFlow, ApprovalNode
from apps.approvals.flow_builder import build_approval_flow
from apps.core.auth import CSRFExemptSessionAuthentication
from apps.core.permissions import RoleRequired

# 从共享模块导入工具函数
from .views_common import (
    SafePageNumberPagination,
    get_user_companies,
    _get_user_company_id,
    _check_perm,
    _require_perms,
)


class WageRecordViewSet(viewsets.ModelViewSet):
    """工资单视图集"""
    authentication_classes = [CSRFExemptSessionAuthentication]
    permission_classes = [permissions.IsAuthenticated, RoleRequired]
    queryset = WageRecord.objects.all()
    serializer_class = WageRecordSerializer
    pagination_class = SafePageNumberPagination
    pagination_class.page_size = 200
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = WageRecordFilter
    search_fields = ['employee_name', 'employee__name', 'employee__code', 'department', 'position']
    ordering_fields = ['year', 'month', 'company__name', 'employee_name', 'net_salary']
    ordering = ['-year', '-month', '-created_at']
    action_perms = {
        None: 'finance:wage:read',
        'partial_update': 'finance:wage:update',
        'approve': 'finance:wage:approve',
        'pay': 'finance:wage:pay',
        'submit': 'finance:wage:submit',
        'years': 'finance:wage:read',
        'calc_preview': 'finance:wage:read',
        'export': 'finance:wage:read',
        'pdf': 'finance:wage:read',
        'pdf_batch': 'finance:wage:read',
        'bank_export': 'finance:wage:read',
        'wage_slips': 'finance:wage:read',
    }

    def get_queryset(self):
        qs = super().get_queryset()
        # 自动多租户：普通用户看所有关联公司数据，超管看全部
        cids = get_user_companies(self.request.user)
        if cids is not None:
            qs = qs.filter(company_id__in=cids)
        return qs.select_related(
            'company', 'approver', 'employee', 'employee_company', 'employee_company__company', 'employee_company__employee'
        ).prefetch_related('approval_flow')

    def _resolve_employee_company(self, emp_id, company_id=None):
        """将 employee ID 转换为 employee_company FK"""
        if not emp_id:
            return None
        ec_qs = EmployeeCompany.objects.filter(employee_id=emp_id)
        if company_id:
            ec_qs = ec_qs.filter(company_id=company_id)
        ec = ec_qs.order_by('-is_primary').first()
        return ec.id if ec else None

    def perform_create(self, serializer):
        data = serializer.validated_data
        company_id = data.get('company')  # 序列化器字段名是 company，不是 company_id
        emp_id = data.get('employee')
        ec_id = self._resolve_employee_company(emp_id, company_id)
        serializer.save(employee_company_id=ec_id)

    def perform_update(self, serializer):
        raw_data = getattr(self, 'request', None) and getattr(self.request, 'data', None) or {}
        company_id = serializer.validated_data.get('company')  # 序列化器字段名是 company
        emp_id = raw_data.get('employee') or serializer.validated_data.get('employee')
        ec_id = self._resolve_employee_company(emp_id, company_id)
        serializer.save(employee_company_id=ec_id)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """批准工资单"""
        wage_record = self.get_object()
        if wage_record.status != 'pending':
            return Response({'status': 'error', 'message': '只能批准待审核状态的工资单'}, status=400)
        wage_record.status = 'approved'
        wage_record.approver = request.user
        from django.utils import timezone
        wage_record.approved_at = timezone.now()
        wage_record.save()
        return Response({'status': 'success', 'message': '工资单已批准'})

    @action(detail=True, methods=['post'])
    def pay(self, request, pk=None):
        """发放工资"""
        wage_record = self.get_object()
        if wage_record.status != 'approved':
            return Response({'status': 'error', 'message': '只能发放已批准状态的工资单'}, status=400)
        wage_record.status = 'paid'
        from django.utils import timezone
        wage_record.paid_at = timezone.now()
        wage_record.save()
        return Response({'status': 'success', 'message': '工资已发放'})

    @action(detail=False, methods=['get'])
    def years(self, request):
        """返回有工资数据的年份列表"""
        qs = self.get_queryset()
        # Bugfix: distinct() on values() with JOINed queryset 会导致 PostgreSQL
        # 把所有列加入DISTINCT考量（每行都不同）。必须显式 order_by('year')
        # 强制只对year字段DISTINCT。同时用values()先收窄列。
        years = sorted(
            qs.order_by('year').values_list('year', flat=True).distinct(),
            reverse=True
        )
        return Response({'years': list(years)})

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """提交工资单进行审核"""
        wage_record = self.get_object()
        if wage_record.status != 'draft':
            return Response({'status': 'error', 'message': '只能提交草稿状态的工资单'}, status=400)
        wage_record.status = 'pending'
        wage_record.save()

        # 根据系统设置决定是否触发审批流
        from apps.core.models import SystemSetting
        try:
            trigger_approval = SystemSetting.objects.get(
                key='wage_submit_creates_approval'
            ).value == 'true'
        except SystemSetting.DoesNotExist:
            trigger_approval = False

        if trigger_approval:
            from apps.approvals.flow_builder import build_approval_flow
            gross = float(wage_record.gross_salary or 0)
            flow = build_approval_flow(
                flow_type='wage',
                amount=gross,
                name=f'工资审批-{wage_record.employee_name} {wage_record.year}年{wage_record.month}月',
                requester=request.user,
                description=f'{wage_record.employee_name} | {wage_record.year}年{wage_record.month}月 | 应发{gross:,.2f}元',
                related_id=wage_record.id,
                company=wage_record.company,
            )
            if flow:
                wage_record.approval_flow = flow
                wage_record.save(update_fields=['approval_flow'])

        return Response({'status': 'success', 'message': '工资单已提交'})

    @action(detail=False, methods=['post'])
    def calc_preview(self, request):
        """
        工资计算预览 API。
        输入当月工资数据 + 上月累计数据（前端传），
        返回和保存时完全一致的后端计算结果（累计预扣法）。
        """
        from apps.finance.models import calculate_wage_tax

        d = request.data
        # 上月累计值（前端传）
        prior_cum_tax = float(d.get('prior_cumulative_tax') or 0)
        prior_cum_gross = float(d.get('prior_cumulative_gross') or 0)
        prior_cum_social = float(d.get('prior_cumulative_social_insurance') or 0)
        prior_cum_housing = float(d.get('prior_cumulative_housing_fund') or 0)

        result = calculate_wage_tax(
            gross=d.get('gross', 0),
            social_insurance=d.get('social_insurance', 0),
            housing_fund=d.get('housing_fund', 0),
            children_education=d.get('children_education', 0),
            continuing_education=d.get('continuing_education', 0),
            serious_illness=d.get('serious_illness', 0),
            housing_loan=d.get('housing_loan', 0),
            housing_rent=d.get('housing_rent', 0),
            elderly_support=d.get('elderly_support', 0),
            infant_care=d.get('infant_care', 0),
            leave_deduction=d.get('leave_deduction', 0),
            sick_leave_deduction=d.get('sick_leave_deduction', 0),
            late_times=d.get('late_times', 0),
            late_deduction_per_time=d.get('late_deduction_per_time', 0),
            employee_loan_repayment=d.get('employee_loan_repayment', 0),
            other_deductions=d.get('other_deductions', 0),
            year=int(d.get('year', 0)),
            month=int(d.get('month', 0)),
            employee_company_id=d.get('employee_company'),
            employee_id=d.get('employee'),
            prior_cumulative_tax=prior_cum_tax,
            prior_cumulative_gross=prior_cum_gross,
            prior_cumulative_social_insurance=prior_cum_social,
            prior_cumulative_housing_fund=prior_cum_housing,
        )
        return Response(result)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """工资单汇总"""
        year = request.query_params.get('year')
        month = request.query_params.get('month')
        company_id = request.query_params.get('company')

        queryset = self.get_queryset()
        if year:
            queryset = queryset.filter(year=int(year))
        if month:
            queryset = queryset.filter(month=int(month))
        if company_id:
            queryset = queryset.filter(company_id=company_id)

        total_gross = sum(float(w.gross_salary or 0) for w in queryset)
        total_tax = sum(float(w.tax or 0) for w in queryset)
        total_net = sum(float(w.net_salary or 0) for w in queryset)
        count = queryset.count()

        # 按状态统计
        status_counts = {
            'draft': queryset.filter(status='draft').count(),
            'pending': queryset.filter(status='pending').count(),
            'approved': queryset.filter(status='approved').count(),
            'paid': queryset.filter(status='paid').count(),
        }

        return Response({
            'count': count,
            'total_gross': round(total_gross, 2),
            'total_tax': round(total_tax, 2),
            'total_net': round(total_net, 2),
            'status_counts': status_counts,
        })

    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """工资仪表盘数据"""
        from django.db.models import Sum, Count
        from django.db.models.functions import TruncMonth

        year = request.query_params.get('year')
        month = request.query_params.get('month')
        # 自动多租户：get_queryset 已过滤，无需重复处理
        # company_id 仍支持前端指定（超管可指定，普通用户被 get_queryset 限制）
        company_id = request.query_params.get('company')

        queryset = self.get_queryset()
        if year:
            queryset = queryset.filter(year=int(year))
        if month:
            queryset = queryset.filter(month=int(month))
        if company_id:
            queryset = queryset.filter(company_id=company_id)

        # 本月工资
        now = timezone.now()
        current_month_qs = self.get_queryset().filter(
            year=now.year,
            month=now.month
        )
        if company_id:
            current_month_qs = current_month_qs.filter(company_id=company_id)

        current_total = current_month_qs.aggregate(total=Sum('net_salary'))['total'] or 0
        current_count = current_month_qs.count()

        # 已发放
        paid_total = queryset.filter(status='paid').aggregate(total=Sum('net_salary'))['total'] or 0
        paid_count = queryset.filter(status='paid').count()

        # 待发放
        pending_total = queryset.filter(status='approved').aggregate(total=Sum('net_salary'))['total'] or 0
        pending_count = queryset.filter(status='approved').count()

        # 逾期
        overdue_qs = queryset.filter(status='approved', year__lt=now.year).exclude(
            year=now.year, month__lte=now.month
        )
        overdue_total = overdue_qs.aggregate(total=Sum('net_salary'))['total'] or 0
        overdue_count = overdue_qs.count()

        return Response({
            'current_total': float(current_total),
            'current_count': current_count,
            'paid_total': float(paid_total),
            'paid_count': paid_count,
            'pending_total': float(pending_total),
            'pending_count': pending_count,
            'overdue_total': float(overdue_total),
            'overdue_count': overdue_count,
        })

    @action(detail=False, methods=['get'])
    def export(self, request):
        """导出工资单 Excel"""
        from apps.core.export_excel import export_wage_records, make_export_response
        from apps.finance.models import WageRecord, EmployeeCompany
        queryset = self.get_queryset()
        year = request.GET.get('year')
        month = request.GET.get('month')
        company_id = request.GET.get('company_id')
        if year:
            queryset = queryset.filter(year=int(year))
        if month:
            queryset = queryset.filter(month=int(month))
        if company_id:
            queryset = queryset.filter(company_id=int(company_id))
        records = list(queryset.select_related(
            'employee', 'company', 'employee_company', 'employee_company__company', 'employee_company__employee'
        ))
        buf = export_wage_records(records)
        return make_export_response(buf, f'工资单_{timezone.now().strftime("%Y%m%d")}.xlsx')

    @action(detail=True, methods=['get'])
    def pdf(self, request, pk=None):
        """生成单张工资条 PDF"""
        wage_record = self.get_object()
        from apps.finance.services.wage_pdf import generate_wage_slip_pdf
        pdf_bytes = generate_wage_slip_pdf(wage_record)
        filename = f"工资条_{wage_record.employee_name}_{wage_record.year}年{wage_record.month}月.pdf"
        from django.http import HttpResponse
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    @action(detail=False, methods=['get'])
    def pdf_batch(self, request):
        """批量生成工资条 PDF（支持指定 year/month/company）"""
        from apps.finance.services.wage_pdf import generate_wage_slip_pdf
        from PyPDF2 import PdfReader, PdfWriter
        import io

        queryset = self.get_queryset()
        year = request.GET.get('year')
        month = request.GET.get('month')
        company_id = request.GET.get('company_id')
        if year:
            queryset = queryset.filter(year=int(year))
        if month:
            queryset = queryset.filter(month=int(month))
        if company_id:
            queryset = queryset.filter(company_id=int(company_id))

        records = list(queryset.select_related(
            'company', 'employee', 'employee_company', 'employee_company__company', 'employee_company__employee'
        ))

        if not records:
            return Response({'status': 'error', 'message': '没有找到符合条件的工资单'}, status=400)

        # 逐条生成 PDF，再合并
        writer = PdfWriter()
        for wr in records:
            pdf_bytes = generate_wage_slip_pdf(wr)
            reader = PdfReader(io.BytesIO(pdf_bytes))
            for page in reader.pages:
                writer.add_page(page)

        output = io.BytesIO()
        writer.write(output)
        output.seek(0)

        period_str = f"{year or '全部'}-{month or '全部'}"
        filename = f"工资条批量_{period_str}_{timezone.now().strftime('%Y%m%d')}.pdf"
        from django.http import HttpResponse
        response = HttpResponse(output.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    @action(detail=False, methods=['get'])
    def bank_export(self, request):
        """导出银行代发文件（支持工行/建行格式）
        GET ?year=&month=&company_id=&bank_type=ICBC|CCB|GENERIC
        """
        from apps.finance.services.wage_bank import (
            generate_icbc_batch_file, generate_ccb_batch_file,
            generate_generic_batch_file, make_bank_export_response
        )

        queryset = self.get_queryset().filter(status__in=['approved', 'paid'])
        year = request.GET.get('year')
        month = request.GET.get('month')
        company_id = request.GET.get('company_id')
        bank_type = request.GET.get('bank_type', 'ICBC').upper()

        if year:
            queryset = queryset.filter(year=int(year))
        if month:
            queryset = queryset.filter(month=int(month))
        if company_id:
            queryset = queryset.filter(company_id=int(company_id))

        records = list(queryset.select_related(
            'company', 'employee', 'employee_company'
        ))

        if not records:
            return Response({'status': 'error', 'message': '没有符合条件的已审批工资单'}, status=400)

        company_name = records[0].company.name if records else ''
        period_str = f"{year or '全部'}{month or '全部'}"

        if bank_type == 'ICBC':
            content = generate_icbc_batch_file(records, company_name)
            filename = f"工行代发_{period_str}_{timezone.now().strftime('%Y%m%d')}.txt"
            response = make_bank_export_response(content, filename, 'text/plain; charset=gbk')
        else:
            content = generate_ccb_batch_file(records)
            filename = f"建行代发_{period_str}_{timezone.now().strftime('%Y%m%d')}.csv"
            response = make_bank_export_response(content, filename, 'text/csv; charset=utf-8')

        return response

    @action(detail=False, methods=['get'])
    def wage_slips(self, request):
        """获取工资条页面所需数据（发送给前端渲染）"""
        queryset = self.get_queryset()
        year = request.GET.get('year')
        month = request.GET.get('month')
        company_id = request.GET.get('company_id')
        if year:
            queryset = queryset.filter(year=int(year))
        if month:
            queryset = queryset.filter(month=int(month))
        if company_id:
            queryset = queryset.filter(company_id=int(company_id))
        records = queryset.select_related(
            'company', 'employee', 'employee_company', 'employee_company__company', 'employee_company__employee'
        )[:50]  # 限制50条

        data = WageRecordSerializer(records, many=True).data
        return Response({'records': data, 'count': queryset.count()})

    @action(detail=False, methods=['post'])
    def import_excel(self, request):
        """批量导入工资 Excel（按姓名匹配员工）
        POST 上传 Excel file，form-data 字段名: file
        Query params: year=&month=&company_id=
        Excel 格式：第1行表头，数据从第2行起，必需列：姓名
        """
        from apps.finance.services.wage_import import import_wage_excel, WageImportError
        from apps.finance.models import WageRecord, Employee, EmployeeCompany

        file = request.FILES.get('file')
        if not file:
            return Response({'success': False, 'message': '请上传 Excel 文件'}, status=400)

        year = request.POST.get('year') or request.data.get('year')
        month = request.POST.get('month') or request.data.get('month')
        company_id = request.data.get('company_id')
        cids = get_user_companies(request.user)
        if company_id is None and cids:
            company_id = cids[0]  # 取第一个有权限的公司
        company_id = int(company_id) if company_id else None

        defaults = {}
        if year:
            defaults['year'] = int(year)
        if month:
            defaults['month'] = int(month)

        try:
            file_bytes = file.read()
            records, parse_errors = import_wage_excel(file_bytes, company_id or 0, defaults)
        except WageImportError as e:
            return Response({'success': False, 'message': str(e)}, status=400)
        except Exception as e:
            return Response({'success': False, 'message': f'解析失败：{str(e)}'}, status=400)

        if not records:
            return Response({
                'success': False,
                'message': 'Excel 中无有效数据行',
                'errors': [{'row': e['row'], 'message': e['message']} for e in parse_errors]
            }, status=400)

        created = 0
        skipped = []
        for rec in records:
            # 按姓名查找员工
            emp_name = rec.get('employee_name', '').strip()
            ec = None
            if company_id:
                ec = EmployeeCompany.objects.filter(
                    employee__name=emp_name, company_id=company_id
                ).select_related('employee').order_by('-is_primary').first()
            if not ec:
                ec = EmployeeCompany.objects.filter(
                    employee__name=emp_name
                ).select_related('employee').order_by('-is_primary').first()

            if not ec:
                skipped.append(f"「{emp_name}」未找到对应员工")
                continue

            # 检查是否已存在
            existing = WageRecord.objects.filter(
                company_id=company_id or ec.company_id,
                employee_company=ec,
                year=rec.get('year'),
                month=rec.get('month'),
            ).exists()
            if existing:
                skipped.append(f"「{emp_name}」{rec.get('year')}年{rec.get('month')}月工资记录已存在，跳过")
                continue

            # 构建工资记录（自动计算实发）
            from decimal import Decimal
            net = (
                Decimal(str(rec.get('base_salary') or 0)) +
                Decimal(str(rec.get('position_salary') or 0)) +
                Decimal(str(rec.get('overtime_pay') or 0)) +
                Decimal(str(rec.get('bonus') or 0)) +
                Decimal(str(rec.get('commission') or 0)) +
                Decimal(str(rec.get('meal_allowance') or 0)) +
                Decimal(str(rec.get('transport_allowance') or 0)) +
                Decimal(str(rec.get('communication_allowance') or 0)) +
                Decimal(str(rec.get('other_allowance') or 0))
            ) - (
                Decimal(str(rec.get('social_insurance') or 0)) +
                Decimal(str(rec.get('housing_fund') or 0)) +
                Decimal(str(rec.get('leave_deduction') or 0)) +
                Decimal(str(rec.get('sick_leave_deduction') or 0)) +
                Decimal(str(rec.get('other_deductions') or 0))
            )

            gross = (
                Decimal(str(rec.get('base_salary') or 0)) + Decimal(str(rec.get('position_salary') or 0)) +
                Decimal(str(rec.get('overtime_pay') or 0)) + Decimal(str(rec.get('bonus') or 0)) +
                Decimal(str(rec.get('commission') or 0)) + Decimal(str(rec.get('meal_allowance') or 0)) +
                Decimal(str(rec.get('transport_allowance') or 0)) +
                Decimal(str(rec.get('communication_allowance') or 0)) + Decimal(str(rec.get('other_allowance') or 0))
            )

            WageRecord.objects.create(
                company_id=ec.company_id,
                employee_company=ec,
                employee=ec.employee,
                employee_name=ec.employee.name,
                bank_card=rec.get('bank_card') or ec.employee.bank_card or '',
                year=rec.get('year'),
                month=rec.get('month'),
                base_salary=rec.get('base_salary') or Decimal('0'),
                position_salary=rec.get('position_salary') or Decimal('0'),
                overtime_pay=rec.get('overtime_pay') or Decimal('0'),
                bonus=rec.get('bonus') or Decimal('0'),
                commission=rec.get('commission') or Decimal('0'),
                meal_allowance=rec.get('meal_allowance') or Decimal('0'),
                transport_allowance=rec.get('transport_allowance') or Decimal('0'),
                communication_allowance=rec.get('communication_allowance') or Decimal('0'),
                other_allowance=rec.get('other_allowance') or Decimal('0'),
                social_insurance=rec.get('social_insurance') or Decimal('0'),
                housing_fund=rec.get('housing_fund') or Decimal('0'),
                leave_days=rec.get('leave_days') or 0,
                leave_deduction=rec.get('leave_deduction') or Decimal('0'),
                sick_leave_days=rec.get('sick_leave_days') or 0,
                sick_leave_deduction=rec.get('sick_leave_deduction') or Decimal('0'),
                other_deductions=rec.get('other_deductions') or Decimal('0'),
                gross_salary=gross,
                net_salary=net,
                status='draft',
            )
            created += 1

        return Response({
            'success': created > 0,
            'message': f'成功导入 {created} 条工资记录' + (f'，跳过 {len(skipped)} 条' if skipped else ''),
            'skipped': skipped[:20],
            'errors': [{'row': e['row'], 'message': e['message']} for e in parse_errors],
        })

    @action(detail=False, methods=['post'])
    def calc(self, request):
        """工资自动计算接口"""
        import re
        def calc_tax(taxable):
            if taxable <= 0:
                return 0
            thresholds = [0, 3000, 12000, 25000, 35000, 55000, 80000]
            rates = [3, 10, 20, 25, 30, 35, 45]
            quick_deductions = [0, 210, 1410, 2660, 4410, 7160, 15160]
            for i in range(len(thresholds) - 1):
                if taxable <= thresholds[i + 1]:
                    return max(0, taxable * rates[i] / 100 - quick_deductions[i])
            return max(0, taxable * 45 / 100 - 15160)

        try:
            base = float(request.data.get('base_salary') or 0)
            pos = float(request.data.get('position_salary') or 0)
            ot = float(request.data.get('overtime_pay') or 0)
            bonus = float(request.data.get('bonus') or 0)
            comm = float(request.data.get('commission') or 0)
            meal = float(request.data.get('meal_allowance') or 0)
            transport = float(request.data.get('transport_allowance') or 0)
            comm_allow = float(request.data.get('communication_allowance') or 0)
            other_allow = float(request.data.get('other_allowance') or 0)
            social = float(request.data.get('social_insurance') or 0)
            fund = float(request.data.get('housing_fund') or 0)
            leave_ded = float(request.data.get('leave_deduction') or 0)
            sick_ded = float(request.data.get('sick_leave_deduction') or 0)
            other_ded = float(request.data.get('other_deductions') or 0)

            gross = base + pos + ot + bonus + comm + meal + transport + comm_allow + other_allow
            special_ded = social + fund
            total_ded = special_ded + leave_ded + sick_ded + other_ded
            taxable = max(gross - special_ded - 5000, 0)
            tax = calc_tax(taxable)
            net = gross - total_ded - tax

            return Response({
                'gross': round(gross, 2),
                'social_insurance': round(social, 2),
                'housing_fund': round(fund, 2),
                'special_deduction': round(special_ded, 2),
                'leave_deduction': round(leave_ded, 2),
                'sick_leave_deduction': round(sick_ded, 2),
                'other_deductions': round(other_ded, 2),
                'total_deduction': round(total_ded, 2),
                'taxable_salary': round(taxable, 2),
                'tax': round(tax, 2),
                'net_salary': round(net, 2),
            })
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['post'])
    def import_records(self, request):
        """批量导入工资单 Excel"""
        from apps.core.import_excel import import_wage
        from apps.finance.models import WageRecord, Employee

        file = request.FILES.get('file')
        if not file:
            return Response({'success': False, 'message': '请上传 Excel 文件'}, status=400)

        try:
            result = import_wage(file)
        except Exception as e:
            return Response({'success': False, 'message': f'解析失败：{str(e)}'}, status=400)

        if not result.rows:
            return Response({'success': False, 'message': '解析后无有效数据行，请检查文件格式和列名'}, status=400)

        created = 0
        errors = []
        for i, row_data in enumerate(result.rows):
            try:
                year_month = row_data['year_month']  # e.g. '2026-04'
                year, month = map(int, year_month.split('-'))

                # 找员工（优先通过 EmployeeCompany 找主公司）
                employee_id = row_data.get('employee')
                employee_company_id = row_data.get('employee_company')
                company_id = row_data.get('company')

                # 如果传了员工姓名但找不到，提示警告（不阻断其他行）
                if not employee_id and row_data.get('employee_name'):
                    errors.append(f"第{i+2}行：员工「{row_data['employee_name']}」不存在，已跳过")
                    continue

                wr = WageRecord.objects.create(
                    employee_id=employee_id,
                    employee_company_id=employee_company_id,
                    company_id=company_id,
                    year=year,
                    month=month,
                    base_salary=row_data.get('basic_wage') or 0,
                    overtime_pay=row_data.get('overtime_wage') or 0,
                    bonus=row_data.get('bonus') or 0,
                    social_insurance=row_data.get('social_insurance_employee') or 0,
                    housing_fund=row_data.get('housing_fund_employee') or 0,
                    tax=row_data.get('personal_income_tax') or 0,
                    other_deductions=row_data.get('other_deductions') or 0,
                    net_salary=row_data.get('net_salary') or 0,
                    status='pending',
                )
                created += 1
            except Exception as e:
                errors.append(f"第{i+2}行：{str(e)}")

        return Response({
            'success': created > 0,
            'message': f'成功导入 {created} 条工资记录' + (f'，失败 {len(errors)} 条' if errors else ''),
            'errors': errors[:20],
        })

    @action(detail=False, methods=['post'])
    def send_wage_slip_email(self, request):
        """发送工资条邮件（参数: wage_id 单条 或 year+month+company_id 批量）"""
        from apps.core.wage_email_service import send_wage_slip_email, send_wage_slip_batch
        wage_id = request.data.get('wage_id')
        year = request.data.get('year')
        month = request.data.get('month')
        company_id = request.data.get('company_id')
        dry_run = request.data.get('dry_run', True)
        if str(dry_run).lower() in ('false', '0', 'no'):
            dry_run = False
        if wage_id:
            from apps.finance.models import WageRecord
            try:
                record = WageRecord.objects.select_related('company', 'employee', 'employee_company__employee').get(id=wage_id)
            except WageRecord.DoesNotExist:
                return Response({'success': False, 'message': f'工资记录 ID={wage_id} 不存在'}, status=404)
            ok, msg = send_wage_slip_email(record, dry_run=dry_run)
            return Response({'success': ok, 'message': msg, 'wage_id': wage_id})
        elif year and month:
            result = send_wage_slip_batch(
                year=int(year), month=int(month),
                company_id=int(company_id) if company_id else None,
                dry_run=dry_run
            )
            return Response({'success': True, **result})
        else:
            return Response({'success': False, 'message': '请提供 wage_id 或 year+month 参数'}, status=400)
