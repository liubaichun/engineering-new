# ViewSet 公司隔离规范 v1.0

## 一、问题定义

### 1.1 现状
43服务器权限系统采用 UMP（UserModulePermission）位掩码方案，支持用户在同一平台下拥有多家公司权限。但 20 个 ViewSet 的 `get_queryset()` 仍使用旧 `user.company_id` 单公司字段做数据隔离，导致多公司用户的 `company_id=None` 时过滤全部失效，回退到 `Model.objects.all()`。

### 1.2 影响范围
| 影响维度 | 说明 |
|---------|------|
| 受影响 ViewSet | 20 个（详见附录A） |
| 受影响模块 | 公司、员工、工资、收入、支出、发票、银行、社保、预算、应收应付、设备、物料、报修、文件、审批、审计日志、报表 |
| 受影响用户 | company_id=None 的多公司用户 |

### 1.3 严重程度
**P0** — 数据隔离完全失效，用户可以看到所有公司的数据。

---

## 二、修复规范（硬性标准）

### 2.1 所有 ViewSet 必须遵循的标准

**标准1：使用 `get_module_companies()` 替代 `user.company_id`**

```python
from apps.core.permissions import get_module_companies

def get_queryset(self):
    if not self.request.user.is_authenticated:
        return self.queryset.model.objects.none()
    companies = get_module_companies(self.request.user, '<正确的模块名>', 'read')
    if companies is None:
        return super().get_queryset()
    return super().get_queryset().filter(company_id__in=companies)
```

**标准2：模块名必须与 UMP 表一致**
- 必须使用 `modules.py` 中 `register_module()` 注册的 `name` 字段
- 不能使用 ViewSet 的类别名或任意字符串
- 正确示例：`get_module_companies(user, 'company', 'read')` — 模块名"company"而非"finance_company"

**标准3：对于关联字段不是直接 company_id 的模型**

查询字段不是直接 `company_id` 的，需要特化处理：

```python
# 当模型用 project__company_id 时
from django.db.models import Q

def get_queryset(self):
    if not self.request.user.is_authenticated:
        return self.queryset.model.objects.none()
    companies = get_module_companies(self.request.user, '<模块名>', 'read')
    if companies is None:
        return super().get_queryset()
    return super().get_queryset().filter(project__company_id__in=companies)
```

**标准4：对于没有 company_id 字段的系统级 ViewSet**
- 如 `UserViewSet`（用户管理）、`CompanyRoleViewSet`（角色管理）等不涉及公司级数据的 ViewSet，不需要加过滤
- 但需要在注释中说明"此 ViewSet 不涉及公司数据，无需隔离"

### 2.2 禁止使用的模式

```python
# ❌ 禁止：使用 user.company_id
if hasattr(user, 'company') and user.company_id:
    return Company.objects.filter(id=user.company_id)
return Company.objects.all()

# ❌ 禁止：使用 get_user_companies()（跨模块）
from apps.finance.views_common import get_user_companies
companies = get_user_companies(user)

# ❌ 禁止：完全不做过滤
queryset = Model.objects.all()
```

### 2.3 特殊处理规则

**对于 ReportViewSet（报表）**：
- 报表有传递 company_id 参数的路径
- 需要在参数校验后，用 `get_module_companies` 验证用户对该公司有权限

**对于 Export/Import 功能**：
- `@action` 方法中如果手动构造 QuerySet，也必须使用 `get_module_companies` 过滤

**对于 BudgetViewSet（预算）**：
- 预算的过滤字段可能是 `company_id`，直接套用标准模式即可

---

## 三、操作流程（分步实施）

### Phase 1：ViewSet 过滤修复（按优先级）

**Step 1：Finance 模块（6个文件，10个ViewSet）**

| 文件 | ViewSet | 模块名 | 操作 |
|------|---------|--------|------|
| finance/views_company.py | CompanyViewSet | company | 替换get_queryset |
| finance/views_employee.py | EmployeeViewSet | employee | 替换get_queryset |
| finance/views_employee.py | EmployeeCompanyViewSet | employee | 替换get_queryset |
| finance/views_bank.py | BankAccountViewSet | bank | 替换get_queryset |
| finance/views_social.py | CompanySocialConfigViewSet | social_security | 替换get_queryset |
| finance/views_social.py | SocialRecordViewSet | social_security | 替换get_queryset |
| finance/views_income.py | IncomeViewSet | income | 替换get_queryset |
| finance/views_expense.py | ExpenseViewSet | expense | 替换get_queryset |
| finance/views_invoice.py | InvoiceViewSet | invoice | 替换get_queryset |
| finance/views_wage.py | WageRecordViewSet | wage | 替换get_queryset |
| finance/views_budget.py | BudgetViewSet | budget | 替换get_queryset |
| finance/views_arap.py | ARAPViewSet | arap | 替换get_queryset |
| finance/views_report.py | ReportViewSet | report | 替换get_queryset |

**Step 2：其他模块（4个文件，5个ViewSet）**

| 文件 | ViewSet | 模块名 |
|------|---------|--------|
| equipment/views.py | EquipmentViewSet | equipment |
| material/views.py | MaterialViewSet | material |
| repair/views.py | RepairRequestViewSet | repair |
| files/views.py | CompanyFileViewSet | file |
| approvals/views.py | ApprovalFlowViewSet | approval |

**Step 3：Core 模块（2个文件，2个ViewSet）**

| 文件 | ViewSet | 模块名 |
|------|---------|--------|
| core/views_log.py | OperationAuditLogViewSet | audit_log |
| core/views_settings.py | FinanceCompanyViewSet | company |

### Phase 2：iframe 闪退修复

| 文件 | 修改内容 |
|------|---------|
| static/js/app.js | checkAuth首行加 iframe 检测 |
| templates/system/index.html | 子页面用轻量模板 |

### Phase 3：权限矩阵UI增强

| 文件 | 修改内容 |
|------|---------|
| templates/core/permission_matrix.html | 只显示目标用户UCR角色的公司 |

### Phase 4：清理+验证

1. 删除 liubc 用户在 2/4/6 公司的 UCR 和 UMP（保留公司3百川）
2. 运行 `scripts/test_permission_security.py` 验证隔离
3. 运行 HTTP 验证脚本
4. 用浏览器登录 liubc 账户全模块验收

---

## 四、验证标准

### 4.1 验证1：API 返回数据隔离

登录 liubc 后，以下 API 必须只返回 company_id=3（百川）的数据：

| API | 预期条数 | 预期公司 |
|-----|---------|---------|
| /api/finance/companies/ | 1 | 仅百川[3] |
| /api/finance/employees/ | 4 | 仅百川[3] |
| /api/finance/incomes/ | 96 | 仅百川[3] |
| /api/finance/expenses/ | 367 | 仅百川[3] |
| /api/finance/invoices/ | 1105 | 仅百川[3] |
| /api/finance/wages/ | 25 | 仅百川[3] |
| /api/crm/clients/ | 20 | 仅百川[3] |
| /api/crm/suppliers/ | 17 | 仅百川[3] |

### 4.2 验证2：页面交互

| 检查项 | 预期 |
|--------|------|
| 员工管理页 - 公司筛选下拉 | 仅显示百川 |
| 员工管理页 - 数据列表 | 仅显示百川的4个员工 |
| 工资管理页 - 公司筛选 | 仅显示百川 |
| 系统管理 - 公司管理Tab | 仅显示百川 |
| 快速切换Tab 5次 | 不闪退到登录页 |

### 4.3 验证3：超级用户不受影响

登录 admin 账户后，仍然可以看到所有 4 家公司的数据。

---

## 五、附录

### 附录A：所有受影响的 ViewSet 完整清单

| # | ViewSet | 文件 | 模块名 | 当前过滤 | 需修复? |
|---|---------|------|--------|---------|--------|
| 1 | CompanyViewSet | finance/views_company.py | company | user.company_id | ✅ |
| 2 | EmployeeViewSet | finance/views_employee.py | employee | user.company_id | ✅ |
| 3 | EmployeeCompanyViewSet | finance/views_employee.py | employee | user.company_id | ✅ |
| 4 | BankAccountViewSet | finance/views_bank.py | bank | user.company_id | ✅ |
| 5 | CompanySocialConfigViewSet | finance/views_social.py | social_security | user.company_id | ✅ |
| 6 | SocialRecordViewSet | finance/views_social.py | social_security | user.company_id | ✅ |
| 7 | IncomeViewSet | finance/views_income.py | income | get_user_companies() | ✅ |
| 8 | ExpenseViewSet | finance/views_expense.py | expense | get_user_companies() | ✅ |
| 9 | InvoiceViewSet | finance/views_invoice.py | invoice | get_user_companies() | ✅ |
| 10 | WageRecordViewSet | finance/views_wage.py | wage | get_user_companies() | ✅ |
| 11 | BudgetViewSet | finance/views_budget.py | budget | 无过滤 | ✅ |
| 12 | ARAPViewSet | finance/views_arap.py | arap | user.company_id | ✅ |
| 13 | ReportViewSet | finance/views_report.py | report | get_user_companies() | ✅ |
| 14 | EquipmentViewSet | equipment/views.py | equipment | user.company_id | ✅ |
| 15 | MaterialViewSet | material/views.py | material | user.company_id | ✅ |
| 16 | RepairRequestViewSet | repair/views.py | repair | user.company_id | ✅ |
| 17 | CompanyFileViewSet | files/views.py | file | user.company_id | ✅ |
| 18 | ApprovalFlowViewSet | approvals/views.py | approval | user.company_id | ✅ |
| 19 | OperationAuditLogViewSet | core/views_log.py | audit_log | user.company_id | ✅ |
| 20 | FinanceCompanyViewSet | core/views_settings.py | company | 无过滤 | ✅ |

### 附录B：已有测试工具清单

| 工具 | 用途 | 在修复中的使用阶段 |
|------|------|-------------------|
| scripts/test_permission_security.py | 权限安全测试 | Phase 4 验证 |
| scripts/verify_permission_complete.py | 权限完整性验证 | Phase 4 验证 |
| scripts/permission_fix/fix_permission_bugs.py | 补充缺失权限码 | 已执行过，不需重复 |
| scripts/delete_ucp.py | 删除UCP记录 | Phase 4清理用 |

### 附录C：Module 注册名称对照表

每个 viewset 需要使用的正确模块名（对应 UMP 表中的 module__name）：

| 模块 | 模块名 | 对应的 ViewSet |
|------|--------|---------------|
| 公司管理 | company | CompanyViewSet, FinanceCompanyViewSet |
| 员工管理 | employee | EmployeeViewSet, EmployeeCompanyViewSet |
| 收入管理 | income | IncomeViewSet |
| 支出管理 | expense | ExpenseViewSet |
| 发票管理 | invoice | InvoiceViewSet |
| 工资管理 | wage | WageRecordViewSet |
| 银行流水 | bank | BankAccountViewSet |
| 社保管理 | social_security | CompanySocialConfigViewSet, SocialRecordViewSet |
| 预算管理 | budget | BudgetViewSet |
| 应收应付 | arap | ARAPViewSet |
| 财务报表 | report | ReportViewSet |
| 设备管理 | equipment | EquipmentViewSet |
| 物料管理 | material | MaterialViewSet |
| 审批管理 | approval | ApprovalFlowViewSet |
| 审计日志 | audit_log | OperationAuditLogViewSet |
| 文件管理 | file | CompanyFileViewSet |
| 设备报修 | repair | RepairRequestViewSet |
| 客户管理 | customer | ClientViewSet（已正确） |
| 供应商管理 | supplier | SupplierViewSet（已正确） |
| 合同管理 | contract | ContractViewSet（已正确） |
| 商机管理 | opportunity | OpportunityViewSet（已正确） |
| 采购申请 | purchase_request | PurchaseRequestViewSet（已正确） |
| 采购订单 | purchase_order | PurchaseOrderViewSet（已正确） |
| 采购入库 | purchase_receive | PurchaseReceiveViewSet（已正确） |
| 项目管理 | project | ProjectViewSet（已正确） |
| 任务管理 | task | TaskViewSet（已正确） |
