# ViewSet 公司隔离修复 — 实施步骤清单

## 概述
本清单按照「先核心后边缘、先验证后推广」的原则，分 4 个 Phase 共 25 步完成。

---

## Phase 1：ViewSet 过滤修复（最核心）

### Step 1.1：Finance 模块 — Company（1个文件）

**文件：** `apps/finance/views_company.py`

**当前代码（第27-35行）：**
```python
def get_queryset(self):
    if not self.request.user.is_authenticated:
        return Company.objects.none()
    user = self.request.user
    if user.is_authenticated and not user.is_superuser:
        if hasattr(user, 'company') and user.company_id:
            return Company.objects.filter(id=user.company_id)
    return Company.objects.all()
```

**替换为：**
```python
def get_queryset(self):
    if not self.request.user.is_authenticated:
        return Company.objects.none()
    companies = get_module_companies(self.request.user, 'company', 'read')
    if companies is None:
        return Company.objects.all()
    return Company.objects.filter(id__in=companies)
```

### Step 1.2：Finance 模块 — Employee（1个文件）

**文件：** `apps/finance/views_employee.py`

两个 ViewSet 需要修改：
1. `EmployeeViewSet.get_queryset()`（第50-58行）
2. `EmployeeCompanyViewSet.get_queryset()`（第145-151行）

EmployeeViewSet 当前代码：
```python
def get_queryset(self):
    if not self.request.user.is_authenticated:
        return Employee.objects.none()
    queryset = Employee.objects.prefetch_related(...)
    user = self.request.user
    if user.is_authenticated and not user.is_superuser:
        if hasattr(user, 'company') and user.company_id:
            queryset = queryset.filter(company_id=user.company_id)
    return queryset
```

替换为同样的 `get_module_companies` 模式。

### Step 1.3：Finance 模块 — Bank（1个文件）

**文件：** `apps/finance/views_bank.py`

### Step 1.4：Finance 模块 — Social（1个文件）

**文件：** `apps/finance/views_social.py`

两个 ViewSet：`CompanySocialConfigViewSet`, `SocialRecordViewSet`

### Step 1.5：Finance 模块 — Income/Expense/Invoice/Wage（4个文件）

- `apps/finance/views_income.py` — IncomeViewSet
- `apps/finance/views_expense.py` — ExpenseViewSet
- `apps/finance/views_invoice.py` — InvoiceViewSet
- `apps/finance/views_wage.py` — WageRecordViewSet

当前使用 `get_user_companies(user)`，替换为 `get_module_companies(user, '<模块名>', 'read')`

### Step 1.6：Finance 模块 — Budget/ARAP（2个文件）

- `apps/finance/views_budget.py` — BudgetViewSet
- `apps/finance/views_arap.py` — ARAPViewSet

### Step 1.7：Finance 模块 — Report（1个文件）

- `apps/finance/views_report.py` — ReportViewSet

注意 ReportViewSet 是 `views.ViewSet`（非 ModelViewSet），需要特殊处理。

### Step 1.8：其他模块 — Equipment/Material/Repair（3个文件）

- `apps/equipment/views.py` — EquipmentViewSet（注意 company_id 或 project__company_id）
- `apps/material/views.py` — MaterialViewSet（同上）
- `apps/repair/views.py` — RepairRequestViewSet

### Step 1.9：其他模块 — Files/Approvals（2个文件）

- `apps/files/views.py` — CompanyFileViewSet
- `apps/approvals/views.py` — ApprovalFlowViewSet（注意关联字段可能是 company_id）

### Step 1.10：Core 模块 — AuditLog/Settings（2个文件）

- `apps/core/views_log.py` — OperationAuditLogViewSet
- `apps/core/views_settings.py` — FinanceCompanyViewSet

---

## Phase 2：系统管理闪退修复

### Step 2.1：修改 app.js

**文件：** `static/js/app.js`

在第128行 `function checkAuth() {` 后添加：
```javascript
function checkAuth() {
    if (window.self !== window.top) return; // iframe内不执行认证检查
    // ... 原有代码
}
```

### Step 2.2：修改系统管理模板

**文件：** `templates/system/index.html`

iframes 子页面加载轻量级模板（不需要完整 base.html）。

---

## Phase 3：权限矩阵UI增强

### Step 3.1：修改模板

**文件：** `templates/core/permission_matrix.html`

加载权限矩阵时，只显示目标用户有 UCR 角色的公司。

---

## Phase 4：清理+验证

### Step 4.1：清理liubc的多余公司权限
运行脚本删除 liubc 在 2/4/6 公司的 UCR 和 UMP。

### Step 4.2：重启 gunicorn

### Step 4.3：运行测试脚本
```bash
cd /root/engineering-new && python3 scripts/test_permission_security.py
```

### Step 4.4：HTTP API 验证
运行 `/tmp/verify_http.py` 确认返回数据符合预期。

### Step 4.5：浏览器验证
登录 liubc，逐模块检查数据隔离。

### Step 4.6：同步到 124

---

## 检查清单（实施完成打勾）

### Phase 1
- [ ] Step 1.1 CompanyViewSet (views_company.py)
- [ ] Step 1.2 EmployeeViewSet + EmployeeCompanyViewSet (views_employee.py)  
- [ ] Step 1.3 BankAccountViewSet (views_bank.py)
- [ ] Step 1.4 CompanySocialConfigViewSet + SocialRecordViewSet (views_social.py)
- [ ] Step 1.5 IncomeViewSet (views_income.py)
- [ ] Step 1.5 ExpenseViewSet (views_expense.py)
- [ ] Step 1.5 InvoiceViewSet (views_invoice.py)
- [ ] Step 1.5 WageRecordViewSet (views_wage.py)
- [ ] Step 1.6 BudgetViewSet (views_budget.py)
- [ ] Step 1.6 ARAPViewSet (views_arap.py)
- [ ] Step 1.7 ReportViewSet (views_report.py)
- [ ] Step 1.8 EquipmentViewSet (equipment/views.py)
- [ ] Step 1.8 MaterialViewSet (material/views.py)
- [ ] Step 1.8 RepairRequestViewSet (repair/views.py)
- [ ] Step 1.9 CompanyFileViewSet (files/views.py)
- [ ] Step 1.9 ApprovalFlowViewSet (approvals/views.py)
- [ ] Step 1.10 OperationAuditLogViewSet (core/views_log.py)
- [ ] Step 1.10 FinanceCompanyViewSet (core/views_settings.py)

### Phase 2
- [ ] Step 2.1 app.js 加 iframe 检测
- [ ] Step 2.2 系统管理模板轻量化

### Phase 3
- [ ] Step 3.1 权限矩阵公司过滤

### Phase 4
- [ ] Step 4.1 清理liubc多余权限
- [ ] Step 4.2 重启gunicorn
- [ ] Step 4.3 运行测试脚本
- [ ] Step 4.4 HTTP API验证
- [ ] Step 4.5 浏览器验证
- [ ] Step 4.6 同步124
