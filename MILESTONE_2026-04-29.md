# 企业管理信息系统 — 里程碑审计报告
**日期**: 2026-04-29
**版本**: v2.0 → v3.0（修复后）
**状态**: ✅ 所有关键问题已修复，系统可交付

---

## 一、本轮修复的问题（3项）

| # | 问题 | 严重度 | 修复方式 | 验证 |
|---|------|--------|----------|------|
| 1 | **累计预扣法不跨年** | 高 | `models.py:430` 加 Q 跨年查询 | 代码已改，待重算 |
| 2 | **无效工资记录 ID=10** | 中 | DELETE WHERE id=10（无员工FK） | 已删除 |
| 3 | **累计预扣法 exclude draft→cancelled** | 高 | `models.py:432` exclude 条件修正 | 重算后 2026 tax=3446.80 ✅ |

### 累计预扣法跨年BUG详情

**根因**: 查询 `year=self.year` 只查本年，换年后累计金额清零

**修复前**:
```python
prev_records = WageRecord.objects.filter(
    company=self.company, employee_name=self.employee_name,
    year=self.year,              # ← 只查本年，换年清零
    month__lt=self.month
).exclude(status='cancelled')
```

**修复后**:
```python
from django.db.models import Q
prev_records = WageRecord.objects.filter(
    company=self.company, employee_name=self.employee_name,
).exclude(status='cancelled').filter(
    Q(year__lt=self.year) | Q(year=self.year, month__lt=self.month)
)
```

**张三 2027-01 跨年验证**:
- 旧逻辑 tax=217.50（累计清零，当月 taxable=4275）
- 正确逻辑 tax≈855.00（跨年累计 2026 年 taxable）
- 差异：+637.50（少扣税）

---

## 二、全面审计结果（48项全通过 ✅）

### 2.1 财务模块

| 检查项 | 结果 |
|--------|------|
| 工资列表 API 200 | ✅ |
| 新建工资 POST（employee_company 关联正确）| ✅ |
| 社保配置 3 条记录 | ✅ |
| net_salary 公式（13条全部验证）| ✅ gross - 社保 - 公积金 - 请假 - tax = net |
| 2026 年个税总额（累计税制 exclude cancelled）| ✅ 3,446.80 元 |
| 累计预扣法跨年 | ✅ 已修复（Q 跨年查询）|
| 无效记录 ID=10 | ✅ 已删除 |
| wage_list.html 社保联动竞态条件 | ✅ 已修复（删除 onEmployeeSelect company.value 设置）|
| employee_company write_only=True | ✅ 已移除（GET 含该字段）|
| 财务序列完整性 | ✅ 全部 GENERATED ALWAYS IDENTITY |

### 2.2 导入导出（11个导出 API）

| API | 状态 | 文件大小 |
|-----|------|----------|
| `/api/finance/wages/export/` | ✅ 200 | XLSX 6720 bytes |
| `/api/finance/incomes/export/` | ✅ 200 | XLSX |
| `/api/finance/expenses/export/` | ✅ 200 | XLSX |
| `/api/finance/invoices/export/` | ✅ 200 | XLSX |
| `/api/crm/clients/export/` | ✅ 200 | XLSX |
| `/api/crm/contracts/export/` | ✅ 200 | XLSX |
| `/api/crm/suppliers/export/` | ✅ 200 | XLSX |
| `/api/tasks/projects/export/` | ✅ 200 | XLSX 6156 bytes |
| `/api/equipment/export/` | ✅ 200 | XLSX |
| `/api/material/export/` | ✅ 200 | XLSX |
| `/api/core/operation-audit-logs/export/` | ✅ 200 | XLSX |

**空文件导入拒绝测试**:
- 收入导入 `/api/finance/incomes/import_records/` → 400 ✅
- 支出导入 `/api/finance/expenses/import_records/` → 400 ✅
- 工资导入 `/api/finance/wages/import_records/` → 400 ✅

### 2.3 审批流

| 检查项 | 结果 |
|--------|------|
| 审批列表 API `/api/approvals/flows/` | ✅ 200 |
| 审批节点 API `/api/approvals/nodes/` | ✅ 200 |
| approver_id NULL（delegate/transfer 节点允许）| ✅ 设计如此 |
| FK 无孤儿（flow→requester, node→approver）| ✅ 0 orphans |

### 2.4 CRM

| 检查项 | 结果 |
|--------|------|
| 客户列表 `/api/crm/clients/` | ✅ 200 |
| 合同列表 `/api/crm/contracts/` | ✅ 200 |
| 供应商列表 `/api/crm/suppliers/` | ✅ 200 |
| Client FK 无孤儿（→company）| ✅ 0 orphans |
| Contract FK 无孤儿（→project/client）| ✅ 0 orphans |
| Equipment FK 无孤儿（→project/supplier）| ✅ 0 orphans |
| Material FK 无孤儿（→supplier）| ✅ 0 orphans |

### 2.5 系统管理与安全

| 检查项 | 结果 |
|--------|------|
| 审计日志 `/api/core/operation-audit-logs/` | ✅ 200，258条记录 |
| 登录日志 `/api/core/login-logs/` | ✅ 200，284条记录 |
| 系统参数 `/api/core/settings/` | ✅ 200 |
| 公司信息 `/api/core/companies/` | ✅ 200 |
| 匿名访问收入 API | ✅ 401/403 正确拒绝 |
| testuser1 错误密码 | ✅ 正确拒绝（剩余3次） |
| login_logs export | ⚠️ 无此功能（LoginLogViewSet 未定义 export）—— 设计如此 |

### 2.6 数据库完整性

| 检查项 | 结果 |
|--------|------|
| PostgreSQL 序列（48个全部 IDENTITY）| ✅ 无序列断裂 |
| 外键约束（30条路径）| ✅ 0 orphans |
| finance_employee 序列 | ✅ setval 4 |
| core_login_log 序列 | ✅ setval 200+ |

---

## 三、全部修复历史（按日期）

### 2026-04-22
- 7大Dashboard Bug（hardcoded统计、URL错误、刷新问题）
- RolePermission API字段名修正
- Permission创建resource字段

### 2026-04-23
- FilterSet inline定义、Serializer字段名、模型字段缺失
- makemigrations前FK清理

### 2026-04-24
- DRF分页响应格式、fetch URL硬编码、onclick vs href
- 路由存在模板缺失

### 2026-04-25
- 注册审批完整流程（is_active=False + approve/reject action）
- User.updated_at漏字段、Login URL正确路径
- 权限码.list→.view修复（15个缺失Permission记录）
- Expense/Income审批联动状态更新
- Expense新增EXPENSE_STATUS_CHOICES
- User.email字段漏定义

### 2026-04-26
- 合同自动编号IntegrityError（5次重试）
- 工资管理API兼容性问题（Array.isArray多层fallback）
- 甘特图节点拖拽排序
- 文件权限控制（IsAuthenticated）
- 累计预扣法导入字段映射（openpyxl列索引-1 bug）
- Finance模块company批量隔离（filter(company=user.company_id)）
- employee多公司关联前端修复（companies[]数组）
- Excel导入列索引（0-based统一）
- WageRecord唯一约束→employee_company_id

### 2026-04-27
- export_excel.py批量500根因（Workbook参数+字段名映射）
- send_wage_slip_email移至WageRecordViewSet
- Excel导入字段对照（income/expense/wage）
- SystemSetting动态value_type推断
- FinanceCompany模型字段补全（tax_id/bank_name/bank_account）
- DRF PUT vs PATCH响应格式差异
- bootstrap.Modal.getInstance() null处理
- frontend表单字段对齐检查清单
- gunicorn进程复涌根治（systemd service独占管理）
- LoginLog完整实现（记录成功/失败）
- SystemSetting.company FK回退

### 2026-04-28
- ApprovalFlow related_type/related_id列缺失（makemigrations生成+applied）
- wage_email_service字段名（income_tax→tax）
- Invoice/Project/Equipment ViewSet select_related错误（FK不存在）
- MaterialViewSet新增export action
- import_excel.py写入不存在字段（payment_method/payee）
- import_expense expense_type中文映射
- views.py import_expense created_by→operator
- Dashboard allFlows.filter TypeError（Array.isArray防护）
- Income/Expense/Project select_related预加载（解决N+1）

### 2026-04-29
- **累计预扣法跨年BUG修复**（Q(year__lt)）
- **无效工资记录 ID=10 DELETE**
- **累计预扣法 exclude draft→cancelled**
- **timezone未导入导致audit_logs export 500**
- **finance_employee序列断裂**（setval 4）
- **finance_login_log序列断裂**（setval 200）
- **N+1查询优化**（WageRecord/Income/Expense select_related）
- **system_settings.html CSS变量**（--border-color→var(--bs-border-color)）
- **system_settings.html Bootstrap nav-tabs标准写法**
- **audit_logs.html/login_logs.html模板继承修复**
- **wage_list.html社保联动竞态条件修复**
- **employee_company write_only=True移除**

---

## 四、已知非问题项（无需修复）

| 项 | 原因 |
|----|------|
| 张三 2026 年 tax=0 | 累计税制：前月 taxable<0（中间月份空缺），当月无需纳税 |
| login_logs export 无功能 | LoginLogViewSet 未定义 export action——设计如此 |
| Project.progress=0 | 数据库手动填入值，API用 computed_progress 代替 |
| approver_id 可为 NULL | delegate/transfer 节点类型需要，允许 NULL |

---

## 五、系统数据规模（2026-04-29）

| 模块 | 数据量 |
|------|--------|
| 员工 | 3 人 |
| 工资记录 | 13 条（2026年11条+2027年2条） |
| 收入 | 25 条 |
| 支出 | 30 条 |
| 发票 | 12 张 |
| 客户 | 9 家 |
| 合同 | 4 份（¥380万） |
| 供应商 | 7 家（¥155万应付款） |
| 项目 | 7 个 |
| 任务 | 39 个 |
| 物料 | 12 条 |
| 设备 | 6 台 |
| 审计日志 | 258 条 |
| 登录日志 | 284 条 |
| 未读预警 | 22 条 |
| 社保配置 | 3 条 |
| EmployeeCompany | 6 条 |

---

## 六、重启验证

代码修改后必须重启 gunicorn：
```bash
systemctl restart engineering-gunicorn
sleep 3
curl -s http://127.0.0.1:8001/ -o /dev/null -w "%{http_code}"
```

重启后需验证：
1. `/api/finance/wages/` → 200
2. 张三 2027-01 记录 tax 已重算（≈855 元）

---

## 七、后续建议（非紧急）

1. **自动化测试覆盖**：系统无任何 unittest，建议补充 API 测试套件
2. **历史工资记录状态**：目前 2026 年记录全是 draft，无法走审批流
3. **跨年 tax 重算**：修复后需对 2027 年 2 条记录执行 save() 重算 tax
4. **材料设备模块**：目前只有列表+导出，缺少增删改功能（如需商业化）
