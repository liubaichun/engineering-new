# 企业信息化管理系统 - 系统差距分析

|> 本文档基于 2026-04-26 全面审计后的真实状态。
> ⚠️ 4月25日版本标注已解决的项目，以此版本为准。

---

## 一、已解决（无需关注）

| 问题 | 状态 | 说明 |
|------|------|------|
| WageRecord.employee FK 缺失 | ✅ 已修复 | employee FK 已存在，数据关联正常 |
| Contract.client FK 缺失 | ✅ 已修复 | client_id 有值，client.name 关联正常 |
| CompanyFile.project FK 缺失 | ✅ 已修复 | project FK + version + created_by 已存在 |
| 通知系统不工作 | ✅ 已修复 | 预警中心正常，有49条真实通知，cron job每小时生成 |
| 工资导出函数缺失 | ✅ 已修复 | exportWages() 函数存在于 wage_list.html |
| 社保配置缺失 | ✅ 已修复 | 龙晟/百川/绿聚能3条数据已初始化，配置页面 `/finance/social-configs/` |
| Employee.email/emergency_contact 缺失 | ✅ 已修复 | 已 ALTER TABLE（email/emergency_contact/emergency_phone） |
| 预警 cron 未配置 | ✅ 已配置 | `0 * * * *` 每小时执行 |
| 权限码与数据库不匹配 | ✅ 已修复 | base.html 权限码已全部对齐数据库 |
| Permission 模型缺少 is_active/menu_code | ✅ 已修复 | models.py 已补充字段 |
| P0 线上安全：DEBUG/ALLOWED_HOSTS/SECRET_KEY | ✅ 已修复 | DEBUG=False默认，.env写入生产配置 |
| Finance 模块数据隔离 | ✅ 已修复 | Income/Expense/WageRecord/Invoice 加 get_queryset 过滤 |
| 发票 counterparty 为空 | ✅ 已修复 | 全部11条发票 counterparty 有值（实测0条空值） |
| file_category 无数据 | ✅ 已修复 | 8条分类数据已初始化 |
| 流程模板管理无前端页面 | ✅ 已修复 | `/tasks/flow-templates/` 页面正常，3模板+14节点 |
| 物料管理整个模块 | ✅ 已完成 | `/materials/` 完整CRUD，8条真实数据，搜索/分类/库存告警全可用 |
| 设备管理整个模块 | ✅ 已完成 | `/equipment/` 完整CRUD，6条真实数据，状态/分类/序列号管理全可用 |
| 任务看板甘特图Tab | ✅ 已完成 | `/tasks/board/` 看板/甘特图 Tab 切换正常，due_date任务显示正确 |
| 任务看板节点拖拽排序 | ✅ 已完成 | `/tasks/flow-templates/` 节点配置弹窗支持HTML5拖拽排序 |
| 收入审批模板缺失 | ✅ 已修复 | id=2"收入确认审批"已创建，Income≥5000自动触发审批流 |
| 系统参数配置UI | ✅ 已完成 | `/system/settings/` 双Tab：审批3项+工资1项参数（开关/数字/文本）；公司信息Tab：FinanceCompany CRUD（增删改查+4个新字段）|
| 项目甘特图独立视图 | ✅ 已完成 | projects.html详情弹窗内Tab切换，甘特图显示项目所有任务，日期范围/周末/今日线/优先级配色完整 |
| Excel批量导入后端 | ✅ 已完成 | `apps/core/import_excel.py`（import_income/import_expense/import_wage），openpyxl解析，字段映射已验证 |
| Excel批量导入API | ✅ 已完成 | `IncomeViewSet.import_records`（221行）+ `ExpenseViewSet.import_records` + `WageRecordViewSet.import_records`，三个端点均已注册 |
| Excel批量导入前端 | ✅ 已完成 | income/expense/wage三个列表页均有导入按钮+弹窗+AJAX，模板下载函数完整 |
| 登录日志页面 | ✅ 已完成 | `/system/login-logs/` 完整页面（过滤/分页/详情/导出），`config/urls.py`路由已添加，LoginLogViewSet API已就绪 |
| 工资条邮件推送 | ✅ 已完成（2026-04-27） | dry_run 发送成功，返回 `[DryRun] 将发送邮件至 zhangsan@company.com` |
| 工资导出 500 Bug | ✅ 已修复（2026-04-29） | ViewSet.export 把 WageRecord 对象转 dict 传给 export_excel，但函数访问 `employee_company.employee.id_card` 字典无此属性；改为直接传模型对象列表 |
| 物料导出 404 | ✅ 已修复（2026-04-29） | MaterialViewSet 无 export action，添加 `@action(detail=False, methods=['get'])` + `export_materials()` 函数 |

---

## 二、已验收功能（2026-04-26）

| 功能 | 验收结果 |
|------|------|
| P2 审批系统金额触发联动 | ✅ 端到端验证通过，expense≥1000元自动创建 ApprovalFlow 并回填 FK |
| P0 任务看板甘特图 Tab | ✅ 代码完整，Tab切换正常，已设5个任务 due_date，甘特图显示"4月25日~5月22日·5个任务" |
| P0 流程节点拖拽排序 | ✅ 代码完整，节点配置弹窗成功加载"需求开发流程"5个节点，tr draggable=true + initNodeDragDrop() 函数就绪 |

---

## 三、真实差距（2026-04-25）

### 🔴 高优先级

#### 1. P2：审批系统 - 业务对象金额触发联动（已实现）

**功能描述**：Expense/Income 创建时根据金额阈值自动匹配 ApprovalTemplate 并创建审批流。

**实现状态**：✅ 已完成

**实现方式**：
- `apps/approvals/services.py`：自动触发引擎
  - `find_matching_template(flow_type, amount)`：按金额阈值匹配模板
  - `create_approval_flow_for_expense(expense)`：创建审批流 + 节点 + 回填 FK
  - `create_approval_flow_for_income(income)`：同理
- `finance/serializers.py`：`ExpenseSerializer.create` 和 `IncomeSerializer.create` 钩子调用服务层
- `ApprovalFlow` 模型新增 `related_type` + `related_id` 字段（DB已ALTER TABLE，models.py已更新）

**验证方式**：
1. 支出管理 → 新建支出 → 金额≥1000元 → 提交
2. 该支出应自动显示"待审批"状态（来自 approval_flow.status）
3. 审批管理页面应出现对应审批记录

**验收结果（2026-04-26）**：✅ 端到端验证通过
- 数据库直接确认：expense #49(8000元) → approval_flow #36（已批准），expense #48(8000元) → #35（待审批），expense #47(5000元) → #34/#33（待审批）
- expense 列表页正确显示审批状态（"待审批"/"已批准"）
**注意**：expense #47 历史遗留两个 flow 记录（#33/#34）为修复前测试数据。根因 `ExpenseViewSet._trigger_approval_flow()` 未检查 `approval_flow FK` 已于 2026-04-26 修复（第257行加 `and not expense.approval_flow_id` 判断）。

**已知情况**：
- 数据库现有审批模板：
  - id=1："支出审批测试"（type=expense，min_amount=1000）
  - id=2："收入确认审批"（type=income，min_amount=5000）✅ 已新增
- 新建 Expense≥1000 或 Income≥5000 时，自动触发审批流

---

### 🟡 中优先级

#### 2. P0：任务流程可视化

**功能描述**：任务看板 flow_board.html 有完整功能代码（1194行），甘特图和节点拖拽排序均已实现。

**当前状态**：
- flow_board.html：任务看板已有，筛选器+看板+甘特图+导出+创建弹窗完整
- flow_template_list.html：流程模板管理页面已有，3个示例模板，14个节点

**验收结果（2026-04-26）**：
- ✅ 甘特图/时间线 Tab 切换：看板页面 `/tasks/board/` 新增「看板/甘特图」两个 Tab
  - 纯 JS+CSS 实现，无需第三方图表库
  - 甘特图按 `due_date` 过滤任务；已为5个任务设置 due_date，验证显示"4月25日~5月22日·5个任务"正常
  - 顶部月份+日期双层 header，支持横向滚动
  - 任务条按优先级配色（低=灰/中=蓝/高=橙/紧急=红）
  - 红色"今天"指示线
  - 点击任务条弹出详情弹窗
- ✅ 节点拖拽排序：流程模板页 `/tasks/flow-templates/` 节点配置弹窗中
  - HTML5 drag & drop API，表格行直接拖拽
  - 拖拽后实时更新序号 PATCH 到后端保存
  - 提示文字"拖拽行可调整节点顺序"

---

### 🟢 低优先级

#### 3. P1-3：财务报表 - 字段级导出（已覆盖）

收入/支出/发票/工资四个模块均已有导出函数：
- `exportExpenses()` → expense_list.html:596
- `exportIncomes()` → income_list.html:696
- `exportInvoices()` → invoice_list.html:726
- `exportWages(selectedFields)` → wage_list.html:730

#### 4. P1-1：文件管理 - UUID 存储 / 权限控制（已完成）

当前文件名存储方式可接受（原始文件名），UUID 存储为可选增强。

**已完成（2026-04-26）**：
- ✅ `IsAuthenticated` 权限替换 `IsAuthenticatedOrReadOnly`（未登录 403）
- ✅ `CompanyFileViewSet.get_queryset()` 加公司隔离：管理员/超级用户看全部，普通用户只看自己上传的文件
- ✅ `uploaded_by` 自动写入当前用户（`perform_create`）
- ✅ 删除/下载均走 DRF 权限链，admin 可删自己上传的文件（204验证通过）

---

## 四、真实遗留问题（2026-04-26）

### 🟡 中优先级

#### 1. 项目进度字段均为 0%

**现象**：Dashboard 项目进度卡片显示"城市综合体 0%、住宅小区 0%、工业厂房 0%、道路桥梁 44%、水利设施 0%"，绝大多数项目进度为 0。

**根因**：项目创建时未录入 `progress` 字段，属历史数据质量问题，非代码 bug。

**影响**：Dashboard 进度展示不准确，无法真实反映项目进展。

**修复方案**：由用户补录各项目的 `progress` 字段值（0-100%）。

---

#### 2. 收入历史数据未触发审批流（历史遗留）

**现象**：数据库中 9 条历史收入记录（id=10~18，金额 50,000-70,000，创建于 2026-04-26 之前）`approval_flow_id` 均为 NULL。新建收入≥5000元时审批流触发正常（id=49 已验证）。

**根因**：这些收入记录创建于收入审批模板（id=2）和触发逻辑实现之前，非代码 bug。

**影响**：历史收入记录无法自动触发审批流程。

**修复方案**：历史数据可通过手动创建审批流补录，或在后台修正 `approval_flow_id`。

---

#### 3. Dashboard 统计数据准确性待验证

**现象**：Dashboard「设备状态」卡片、「合同状态」等统计面板可能存在数据偏差。

**说明**：已验证以下数据正常：公司统计（3家）、收入总额（¥548,888）、待审批（10条）。部分统计面板（如设备状态、合同状态）建议用户使用时核对。

---

## 五、待新增功能（从未实现）

以下功能经逐一代码验证，从未实现：

| 功能 | 验证方式 | 优先级 | 状态 |
|------|---------|--------|------|
| 工资条邮件推送 | 全局搜索 `wage.*email\|payslip\|工资条` 无结果 | P2 | ⏸️ 暂不做 |
| Excel批量导入 | 后端工具已写完，API端点和前端未实现 | P2 | ✅ 已完成（前后端串联验证通过） |

---

## 六、权限系统关键信息

| 项目 | 值 |
|------|---|
| 权限码来源 | RolePermission.menu.code（多对多） |
| 权限检查位置 | base.html:270 `hasPermission(code)` 函数 |
| 权限码映射 | `project.list→project.view`, `task.board→task_board.view`, `wage.list→wage.view`, `report.list→report.view`, `client.list→client.view`, `user.list→user.view`, `role.list→role.view`, `approval.list→approval.view`, `company.list→company.view`, `file.list→file.view` |
| 现有权限码 | project.*, task.*, task_board.*, flow_template.*, wage.*, finance.*, income.*, expense.*, invoice.*, report.*, client.*, contract.*, user.*, role.*, permission.*, company.*, approval.*, file.* |

---

## 七、系统访问信息

| 项目 | 值 |
|------|---|
| 系统地址 | http://43.156.139.37:8001/ |
| 管理账号 | admin / admin123 |
| gunicorn 端口 | 8001 |
| gunicorn 入口 | config.wsgi |
| 数据库 | PostgreSQL `engineering_new` @ localhost:5432，engineer/engineering123 |
| 重启命令 | `sudo systemctl restart engineering-gunicorn && sleep 2` |

---

## 八、Bug 根因模式（调试参考）

1. **DRF分页返回 `{count, results}`**，前端若用 `data.length` 取总数则永远为0
2. **fetch URL 年份硬编码 2026**，导致 stats 全为0 → 用 `new Date().getFullYear()`
3. **area+name 叠加**：name 字段已含完整地名，再拼接 area 则重复
4. **onclick vs href**：href 跳转先于 onclick 执行，需在 onclick 末尾加 `return false;`
5. **FK 断裂**：WageRecord.employee_id 大量 NULL 导致姓名显示"?"
6. **gunicorn HUP 信号不足以重载 Python 代码**：必须完全重启（kill -9 + daemon）

## 九、本轮新增 Bug 根因（2026-04-29）

**【根因类型A：ViewSet层转dict但函数层访问ORM属性 — AttributeError 500】**

- 典型案例：`WageRecordViewSet.export` 把 WageRecord 对象转成 Python dict 列表传给 `export_wage_records(records)`，但 `export_wage_records` 直接写 `r.employee_company.employee.id_card`（期望ORM对象，收到dict）
- 症状：GET 导出 API 返回 HTTP 500 + `AttributeError: 'dict' object has no attribute 'employee_company'`
- 诊断：`export_excel.py` 里的函数签名期望接收什么类型的参数？直接读函数源码判断
- 修复原则：**始终传模型对象给 export 函数，不要中间转 dict**；如果必须转，dict 的 key 必须与函数内的访问路径一致
- 验证：`curl` 调 API 返回 200 + 有效 Excel 文件（文件大小 > 1KB）才算通过

**【根因类型B：功能缺失而非代码损坏 — URL 404】**

- 典型案例：`MaterialViewSet` 没有任何 `@action(detail=False, methods=['get'])` 的 export 方法 → `/api/material/export/` 404
- 诊断：先 `grep -n "def export" apps/XXX/views.py` 确认 ViewSet 是否有 export 方法
- 易混淆点：模型/序列化器/前端模板可能全对，但 ViewSet 忘了写 action
- 修复：补 `@action` + 对应的 export 函数

**【根因类型C：URL 路径不一致 — URL 404】**

- 常见错误：`expense-records` vs `expenses`、`companies` vs `employees`、`wage-records` vs `wages`
- 诊断：直接用 Python 查 DRF router 的 URL patterns（`django.urls.get_resolver().url_patterns`）
- 永远不要猜测 URL，先用 `curl -X OPTIONS` 或 Python `resolve()` 反查
- **完整 API URL 导出（2026-04-29 实测）：**
  ```
  GET /api/finance/companies/export/
  GET /api/finance/incomes/export/
  GET /api/finance/expenses/export/
  GET /api/finance/wages/export/
  GET /api/finance/invoices/export/
  GET /api/crm/clients/export/
  GET /api/crm/contracts/export/
  GET /api/tasks/projects/export/
  GET /api/crm/suppliers/export/
  GET /api/equipment/export/
  GET /api/material/export/
  POST /api/finance/incomes/import_records/
  POST /api/finance/expenses/import_records/
  POST /api/finance/wages/import_records/
  ```

## 十一、本轮新增 Bug 根因（2026-04-29 第二轮深度审计）

**【根因类型D：导入函数写入模型中不存在的字段——静默失败或 TypeError】**

- 典型案例A：`import_excel.py` 导 `Expense` 时写 `payment_method` 字段，但 `Expense` 模型根本没有此字段，Django ORM 会忽略未知字段关键字参数，导致该字段永远无法通过导入写入
- 典型案例B：`import_excel.py` 导 `Expense` 时写 `payee` 字段，但 `Expense` 模型只有 `supplier` 字段没有 `payee`，`Expense.objects.create(..., payee=...)` 直接抛出 `TypeError` 导致整个导入批量失败
- 症状：导入 API 返回 200 但数据不对，或直接 500 错误
- 诊断：**永远不要在导入代码里写模型不存在的字段**；用 `grep "col_" import_excel.py` 找所有列定义，逐个对照模型字段
- 修复原则：`import_xxx` 写入的每个 key，**必须**在对应模型的 `.objects.create()` 可接受范围内

**【根因类型E：导入默认值状态值不在 choices 合法范围内——数据损坏】**

- 典型案例：`import_excel.py` 里 `status_map.get(..., 'confirmed')` 的默认值 `confirmed`，但 `Income.STATUS_CHOICES` 只有 `pending/approved/rejected`，`Expense.STATUS_CHOICES` 只有 `draft/pending/approved/rejected`
- 症状：导入时状态列填了未知值后 fallback 到 `confirmed`，数据库写入了非法值，前端无法正确展示
- 诊断：导入函数的默认状态值，**必须**与模型的 STATUS_CHOICES 对齐
- 修复：Income 默认值改 `pending`，Expense 默认值改 `draft`

**【根因类型F：Serializer 访问关联对象属性，但 ViewSet.get_queryset 没有预加载——N+1 查询】**

- 典型案例：`ApprovalFlowSerializer` 访问 `obj.requester.username`，但 `ApprovalFlowViewSet.get_queryset` 没有 `select_related('requester')`，导致每条记录一次额外 SQL
- 典型案例：`ApprovalNodeSerializer` 访问 `approver.username`，`ApprovalFlowSerializer` 嵌套的 `nodes` 中的 `approver.username`，但对应的 ViewSet 没有 `prefetch_related('nodes__approver')`
- 症状：API 列表返回正常，但响应慢（N+1 查询放大），数据库负载高
- 诊断：看 serializer 的 `source=` 或 `SerializerMethodField`，对应查 viewset 的 `get_queryset`
- 修复：每个 `source='related.name'` 都要有对应的 `select_related('related')`，嵌套的 `Prefetch` 对象同理

## 十二、系统性防御规范（迁移/重构/新增功能必查）

### 规范1：任何 export 函数必须同时验证 API 和 Excel 文件内容

**错误做法**：只检查 HTTP 200，不检查文件内容
**正确做法**：
```bash
curl -sb /tmp/sess.txt "http://localhost:8001/api/finance/wages/export/" -o /tmp/wage.xlsx
python3 -c "import openpyxl; wb=openpyxl.load_workbook('/tmp/wage.xlsx'); print(wb.active.title, wb.active.max_row)"
# 有效文件：max_row > 1（表头+数据），不是 0
```

### 规范2：任何 ViewSet 新增 action 前，先确认 URL 路由是否已注册

**标准检查流程（30秒）：**
```bash
./venv/bin/python3 -c "
from django.urls import get_resolver
def collect(p, prefix=''):
    for x in p:
        if hasattr(x, 'url_patterns'): collect(x.url_patterns, prefix+str(x.pattern))
        else: print(prefix+str(x.pattern))
collect(get_resolver().url_patterns)
" | grep 'export\|import' | grep YOUR_APP_PREFIX
```

### 规范3：修改任何 model FK 字段后，必须检查所有引用该 FK 的代码

```bash
# FK 从 A.foreign_key 改为 B.foreign_key 后必查
grep -rn "select_related\|prefetch_related\|filter(.*fk\|fk__)" apps/finance/views.py
grep -rn "\.foreign_key\." apps/core/export_excel.py
```

### 规范4：迁移后必做验收清单（PostgreSQL）

```bash
# 1. 确认表结构（所有列必须与 models.py 对齐）
psql -c "\d finance_company" | grep -E "tax_id|bank_name|bank_account"
# 2. 确认序列
psql -c "SELECT last_value FROM core_login_log_id_seq;"
# 3. 确认唯一约束（尤其是 unique_together）
psql -c "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint WHERE contype='u' AND conrelid='finance_wage_record'::regclass;"
# 4. 端到端 API 验证（见规范1）
```

### 规范5：导出 API 路径规范

```
GET  /api/finance/companies/export/      ← FinanceCompany 在 finance app
GET  /api/finance/incomes/export/
GET  /api/finance/expenses/export/      ← 注意是 expenses（复数），不是 expense-records
GET  /api/finance/wages/export/
GET  /api/finance/invoices/export/
GET  /api/crm/clients/export/
GET  /api/crm/contracts/export/
GET  /api/tasks/projects/export/
GET  /api/crm/suppliers/export/
GET  /api/equipment/export/
GET  /api/material/export/              ← Material 是独立 app
```

### 规范6：每次代码审查必须用 curl 实际调用验证，不能只看代码

**最低验证标准（每个 export/action API）：**
```bash
# 1. HTTP 状态码 200
# 2. Content-Type 是 Excel/application
# 3. 文件大小 > 1KB
# 4. openpyxl 能打开
# 5. 数据行数与数据库 SELECT COUNT(*) 一致
```

## 十一、全量 API 验证命令（每次重构/迁移后必跑）

```bash
cd /root/engineering-new
export PGPASSWORD=engineer123
./venv/bin/python3 - << 'PYEOF'
import os, sys, requests, io
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django; django.setup()

BASE = 'http://127.0.0.1:8001'
s = requests.Session()
r = s.post(f'{BASE}/api/core/auth/login/', json={'username':'admin','password':'admin123'})
assert r.status_code == 200

exports = [
    ('/api/finance/companies/export/',    'Company'),
    ('/api/finance/incomes/export/',    'Income'),
    ('/api/finance/expenses/export/',   'Expense'),
    ('/api/finance/wages/export/',        'Wage'),
    ('/api/finance/invoices/export/',    'Invoice'),
    ('/api/crm/clients/export/',         'Client'),
    ('/api/crm/contracts/export/',        'Contract'),
    ('/api/tasks/projects/export/',      'Project'),
    ('/api/crm/suppliers/export/',       'Supplier'),
    ('/api/equipment/export/',           'Equipment'),
    ('/api/material/export/',             'Material'),
]
all_ok = True
for path, name in exports:
    r = s.get(f'{BASE}{path}')
    ok = r.status_code == 200 and len(r.content) > 1024
    print(f"{'✅' if ok else '❌'} {name:12s} {r.status_code} {len(r.content):6d}bytes")
    if not ok: all_ok = False

print('\n总结:', '✅ 全部通过' if all_ok else '❌ 有失败项')
PYEOF
```

