"""
工资条邮件发送服务
- 按工资记录发送个人工资条邮件
- 支持按年月/公司/员工筛选
- 邮件内容包含工资明细（应发/扣除/实发）
"""
import logging
from decimal import Decimal
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


def get_employee_email(wage_record):
    """获取员工邮箱，按优先级尝试多种关联路径"""
    email = None
    # 1. employee_company -> employee -> email
    if wage_record.employee_company and wage_record.employee_company.employee:
        email = wage_record.employee_company.employee.email
    # 2. 直接 employee -> email
    if not email and wage_record.employee:
        email = wage_record.employee.email
    return email


def build_wage_slip_html(wage_record):
    """构建工资条HTML邮件内容"""
    r = wage_record
    year_month = f"{r.year}年{r.month}月"

    # 计算应发合计
    gross = (
        (r.base_salary or Decimal('0')) +
        (r.position_salary or Decimal('0')) +
        (r.overtime_pay or Decimal('0')) +
        (r.bonus or Decimal('0')) +
        (r.commission or Decimal('0')) +
        (r.meal_allowance or Decimal('0')) +
        (r.transport_allowance or Decimal('0')) +
        (r.communication_allowance or Decimal('0')) +
        (r.other_allowance or Decimal('0'))
    )
    total_deduct = (
        (r.social_insurance or Decimal('0')) +
        (r.housing_fund or Decimal('0')) +
        (r.tax or Decimal('0')) +
        (r.other_deductions or Decimal('0'))
    )

    def fmt(v):
        if v is None:
            return '0.00'
        if isinstance(v, Decimal):
            return f"{v:.2f}"
        return str(v)

    rows = []
    # 应发明细
    items = [
        ('基本工资', r.base_salary),
        ('岗位工资', r.position_salary),
        ('加班费', r.overtime_pay),
        ('奖金', r.bonus),
        ('提成', r.commission),
        ('餐补', r.meal_allowance),
        ('交通补贴', r.transport_allowance),
        ('通讯补贴', r.communication_allowance),
        ('其他应发', r.other_allowance),
    ]
    for label, val in items:
        if val and val > 0:
            rows.append(f'<tr><td style="padding:6px 12px;border-bottom:1px solid #eee;">{label}</td><td style="padding:6px 12px;border-bottom:1px solid #eee;text-align:right;">{fmt(val)}</td></tr>')

    deduct_items = [
        ('社保扣款', r.social_insurance),
        ('公积金扣款', r.housing_fund),
        ('个人所得税', r.tax),
        ('其他扣款', r.other_deductions),
    ]
    for label, val in deduct_items:
        if val and val > 0:
            rows.append(f'<tr style="color:#dc3545;"><td style="padding:6px 12px;border-bottom:1px solid #eee;">{label}</td><td style="padding:6px 12px;border-bottom:1px solid #eee;text-align:right;">-{fmt(val)}</td></tr>')

    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; max-width:600px; margin:0 auto; padding:20px; color:#333;">
  <div style="background:#1a7f37; color:white; padding:20px; border-radius:8px 8px 0 0;">
    <h2 style="margin:0;">💰 工资条通知</h2>
    <p style="margin:8px 0 0;">{year_month} · {r.company.name if r.company else '公司'}</p>
  </div>
  <div style="background:#f8f9fa; padding:20px; border:1px solid #ddd; border-top:none;">
    <p style="margin:0 0 16px;">Dear <strong>{r.employee_name or '员工'}</strong>，</p>
    <p style="margin:0 0 16px;">您的{r.year}年{r.month}月工资单已生成，明细如下：</p>

    <table style="width:100%; border-collapse:collapse; background:white; border-radius:6px; overflow:hidden; margin-bottom:16px;">
      <thead>
        <tr style="background:#e9ecef;">
          <th colspan="2" style="padding:10px 12px; text-align:left; font-size:14px;">应发项目</th>
        </tr>
      </thead>
      <tbody>
        {''.join(rows) if rows else '<tr><td colspan="2" style="padding:6px 12px;">—</td></tr>'}
        <tr style="font-weight:bold; background:#f8f9fa;">
          <td style="padding:8px 12px;">应发合计</td>
          <td style="padding:8px 12px;text-align:right;">{fmt(gross)}</td>
        </tr>
      </tbody>
    </table>

    <table style="width:100%; border-collapse:collapse; background:white; border-radius:6px; overflow:hidden; margin-bottom:16px;">
      <thead>
        <tr style="background:#e9ecef;">
          <th colspan="2" style="padding:10px 12px; text-align:left; font-size:14px;">扣除项目</th>
        </tr>
      </thead>
      <tbody>
        {[f'<tr><td style="padding:6px 12px;border-bottom:1px solid #eee;">{l}</td><td style="padding:6px 12px;border-bottom:1px solid #eee;text-align:right;color:#dc3545;">-{fmt(v)}</td></tr>' for l, v in deduct_items if v and v > 0]}
        <tr style="font-weight:bold; background:#f8f9fa;">
          <td style="padding:8px 12px;">扣除合计</td>
          <td style="padding:8px 12px;text-align:right;color:#dc3545;">{fmt(total_deduct)}</td>
        </tr>
      </tbody>
    </table>

    <div style="background:#1a7f37; color:white; padding:16px; border-radius:6px; text-align:center; margin-bottom:16px;">
      <div style="font-size:12px; opacity:0.8;">实发工资</div>
      <div style="font-size:28px; font-weight:bold;">¥{fmt(r.net_salary or 0)}</div>
    </div>

    <p style="font-size:12px; color:#666;">* 如有疑问，请联系公司人力资源部门<br>* 本邮件由系统自动发送，请勿直接回复</p>
  </div>
</body>
</html>
"""
    return html


def send_wage_slip_email(wage_record, dry_run=False):
    """
    发送单条工资条邮件
    返回 (success: bool, message: str)
    """
    email = get_employee_email(wage_record)
    if not email:
        return False, f"员工 {wage_record.employee_name or wage_record.employee_id} 未登记邮箱"

    subject = f"【工资条】{wage_record.year}年{wage_record.month}月 工资单 - {wage_record.employee_name}"
    html_content = build_wage_slip_html(wage_record)
    plain_content = strip_tags(html_content)

    if dry_run:
        logger.info(f"[DryRun] Would send wage slip to {email}: {subject}")
        return True, f"[DryRun] 将发送邮件至 {email}"

    try:
        send_mail(
            subject=subject,
            message=plain_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            html_message=html_content,
            fail_silently=False,
        )
        logger.info(f"Wage slip sent to {email} for {wage_record.year}-{wage_record.month:02d}")
        return True, f"已发送至 {email}"
    except Exception as e:
        logger.error(f"Failed to send wage slip to {email}: {e}")
        return False, f"发送失败: {str(e)}"


def send_wage_slip_batch(year=None, month=None, company_id=None, employee_id=None, dry_run=False):
    """
    批量发送工资条邮件
    按条件筛选工资记录，发送邮件
    返回 dict: {total, sent, failed, results: [(wage_id, success, message)]}
    """
    from apps.finance.models import WageRecord

    queryset = WageRecord.objects.select_related(
        'company', 'employee', 'employee_company__employee'
    ).filter(status='paid')

    if year:
        queryset = queryset.filter(year=year)
    if month:
        queryset = queryset.filter(month=month)
    if company_id:
        queryset = queryset.filter(company_id=company_id)
    if employee_id:
        queryset = queryset.filter(employee_id=employee_id)

    results = []
    sent = 0
    failed = 0
    skipped = 0

    for record in queryset:
        email = get_employee_email(record)
        if not email:
            results.append((record.id, False, "无邮箱"))
            skipped += 1
            continue

        ok, msg = send_wage_slip_email(record, dry_run=dry_run)
        results.append((record.id, ok, msg))
        if ok:
            sent += 1
        else:
            failed += 1

    return {
        'total': queryset.count(),
        'sent': sent,
        'failed': failed,
        'skipped': skipped,
        'details': results,
    }
