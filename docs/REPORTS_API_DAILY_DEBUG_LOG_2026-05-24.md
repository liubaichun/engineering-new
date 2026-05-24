# 财务报表 API 全面审计与修复日志

**日期：** 2026-05-24（初稿）/ 2026-05-25（补录前端修复）
**操作人：** Hermes Agent
**关联提交：** 9个 commit（见文末第七节）

---

## 一、问题背景

刘柏春指出之前的分析报告过于简略，仅列举了具体 bug，未对整个财务报表模块的**数据来源、逻辑链路、前端展示**做全面分析。

本次作为"用户视角"，用可视化浏览器对所有修复进行了逐项验证。

---

## 二、审计范围

| 模块 | 文件 | 报表接口数 |
|------|------|-----------|
| Finance ViewSet（类视图） | `apps/finance/views.py` | 5个 |
| reports_v2.py（函数式报表） | `apps/finance/reports_v2.py` | 8个 |
| 前端模板 | `templates/finance/income_list.html` | 收入列表 |
| 前端模板 | `templates/finance/expense_list.html` | 支出列表 |

**共审计 13 个后端报表端点 + 2 个前端列表页面。**

---

## 三、审计结论：不存在"多租户漏洞"

之前报告中判断 `reports_v2.py` 存在多租户漏洞是**错误的**。经过完整审查：

- 普通用户：只能看到自己关联公司的数据（通过 `get_user_companies()` 实现）
- 超管：可以指定公司，也可以不指定（查全部）
- 这是合理的设计，不是漏洞

---

## 四、后端 Bug 及修复记录

### P0 级（严重影响功能）

| # | 接口/文件 | 问题描述 | 根因 | 修复方案 | 验证结果 |
|---|-----------|---------|------|---------|---------|
| B1 | `invoice_summary` (`views.py:1859`) | 调用接口 HTTP 500 | 变量名笔误：`user_company_id` 未定义，正确为 `user_company_ids` | 删错误逻辑，改为直接 `filter(company_id__in=user_company_ids)` | HTTP 200, total_count=407 ✅ |
| B2 | `ar_ap_aging_report` (`reports_v2.py:228`) | `year/month` 参数声明了但未使用，返回全量数据 | `due_date__year` 和 `due_date__month` 过滤条件缺失 | 添加 `due_date__year=year` + `due_date__month=month` 到 query | year=2026: AR=311,500 ✅ |

### P1 级（数据错误）

| # | 接口/文件 | 问题描述 | 根因 | 修复方案 | 验证结果 |
|---|-----------|---------|------|---------|---------|
| B3 | `balance_sheet` (`views.py`) | `wage_expense` 永远为 0 | `expense_type='wage'` 在银行流水中不存在，工资通过 WageRecord 发薪记录 | 改为从 WageRecord 汇总：`filter(period__startswith=year).aggregate(Sum('gross_salary'))` | BC=376,000 / LJN=280,000 / JYH=88,000 ✅ |
| B4 | `cash_flow_report` (`reports_v2.py`) | `month` 参数声明了但未使用，总是返回全年12个月数据 | `for month in range(1, 13)` 硬编码循环，未用 `month` 参数 | 添加 `month` 参数逻辑：指定则只处理该月，否则处理全年 | month=4只返回1个月数据 ✅ |
| B5 | `tax_summary` / `wage_summary` (`reports_v2.py`) | 社保费率硬编码深圳（个人10.3%、公司23%），各公司实际配置不同 | `_EMP_SI_RATE=10.3`、`_COM_SI_RATE=23.0` 写死 | 改为从 `CompanySocialConfig` 读取各公司的 `emp_rate`/`com_rate` | BC社保公司=42,588 / LJN=32,532 ✅ |

### P2 级（逻辑缺陷，已修复）

| # | 接口/文件 | 问题描述 | 修复方案 |
|---|-----------|---------|---------|
| B6 | `customer_revenue_report` (`reports_v2.py`) | `INTERNAL_COMPANY_NAMES` 硬编码3个公司名，新增公司需手动维护 | 改为从 `Company.objects.values_list('name')` 动态读取 |
| B7 | `supplier_expense_report` (`reports_v2.py`) | `len(supplier) <= 4` 判断个人不可靠，误判"有限公司"为个人 | 改用正则：`re.match(r'^[\u4e00-\u9fa5]{2,4}$', supplier)` 精确匹配2-4个汉字 |
| B8 | `budget_execution_report` (`reports_v2.py`) | 社保计算同样硬编码公司费率 `_COM_SI_RATE=23.0` | 与 B5 同步修复，从 `CompanySocialConfig` 读取 |
| B9 | 前端 `report_dashboard.html` | 现金流量表 URL 未传 `month` 参数 | 添加 `${month ? '&month=' + month : ''}` 到 API URL |

---

## 五、前端页面 Bug 及修复记录

### F1：收入列表年份下拉框框中框（income_list.html）

**根因**：`filterYear` `<select>` 同时有 `selectpicker` class（bootstrap-select 插件）和 Bootstrap 原生 `form-select` class，两套样式冲突导致嵌套。

**修复**：
1. 移除 `selectpicker` class
2. 移除 `loadYearOptions()` 里的 `$(select).selectpicker(...)` 初始化代码
3. 保留 API 请求和选项填充逻辑，改用原生 `<select>` + CSS

**修复后**：年份下拉框显示为普通原生下拉框，无嵌套。

---

### F2：支出列表年份下拉框框中框（expense_list.html）

同上，filterYear 的 `selectpicker` class 已移除，bootstrap-select 初始化代码已删除。

---

### F3：收入列表分页不准确（income_list.html）

**根因**：`renderPagination(data, infoId)` 依赖 `data.page_size`（有时为空）和 `data.total_pages`（来自后端），分页信息显示不准确。

**修复**：照抄工资管理模块（`wage_list.html`）的可靠模式：
```javascript
var incomePageSize = 20;  // 常量，不依赖 API 返回值

function renderPagination(data) {
    var total = data.count || 0;
    var totalPages = Math.ceil(total / incomePageSize);
    // 显示 "显示 N-M 条，共 X 条"
}

async function fetchIncomesPage(page = 1) {
    let url = '/api/finance/incomes/?page=' + page + '&page_size=' + incomePageSize;
    return await response.json();  // 返回完整分页响应（含 count）
}
```

---

### F4：支出列表分页根本性错误（expense_list.html）

**根因**：`fetchAllExpenses` 递归调用 API 直到 `data.next` 为空，把全量数据拉到前端，`renderPagination` 只传 count 数字，前端真正渲染的是 `data.results`（全量数据），分页信息显示"1-20条"但实际渲染了全部记录。

**修复**：删除 `fetchAllExpenses`，替换为 `fetchExpensesPage`，只取当前页：
```javascript
async function fetchExpensesPage(page = 1) {
    let url = '/api/finance/expenses/?page=' + page + '&page_size=' + pageSize;
    // ...过滤参数
    return await response.json();  // 只返回当前页
}

async function loadExpenses() {
    const data = await fetchExpensesPage(currentExpensePage);
    renderExpenses(data.results || data);
    renderExpensePagination(data);  // 传完整 data，不只传 count
}
```

`renderExpensePagination(data)` 同样改为从 `data.count` 计算 totalPages，和收入列表一致。

---

## 六、数据链路分析

### balance_sheet 工资数据流

```
WageRecord 表 (company + period + gross_salary)
    ↓ filter(period__startswith=year, company=company)
    ↓ Sum('gross_salary')
    → wage_expense 字段
```

> **注意：** WageRecord 表目前只有2026年数据（59条），2025年无工资记录是正常现象。

### cash_flow_report 数据流

```
BankStatement 表 (company + date + amount + type)
    ↓ filter(date__year=year, ...)
    ↓ 按 type='income'/'expense' 分组
    ↓ 按月循环 (1-12 或指定 month)
    → monthly[].{income, expense, net, end_balance}
```

### 收入/支出列表分页数据流

```
修复前（错误）：
API: GET /incomes/?page=1 → 全量递归拉取 → 前端分页（数据已全拉回来，分页形同虚设）

修复后（正确）：
API: GET /incomes/?page=1&page_size=20 → 只返回第1页20条
     GET /incomes/?page=2&page_size=20 → 只返回第2页20条
前端只渲染 data.results，不做本地分页
```

---

## 七、经验总结

### 1. 调试原则

- **先分析数据链路，再动手**：确认变量从哪来、函数干什么、为什么出错
- **改完后必须实际验证**：用浏览器/API curl 确认，不能靠猜
- **破坏后立即回滚**：出问题第一时间回滚，不要越挖越深

### 2. 常见陷阱

- **参数声明了但未使用**：`year=2026` 传进来，但 query 里没有 `date__year=2026`，数据永远是全量
- **硬编码配置值**：社保费率等应该在 `CompanySocialConfig` 表里读取，不应该写死在代码里
- **单值 vs 列表混淆**：`user.company_id` 是单值，`get_user_companies()` 返回列表，多公司查询必须用后者
- **前端递归拉全量替代真分页**：`fetchAllExpenses` 把所有数据拉到前端再分页，违背了分页初衷，对大数据量是性能灾难

### 3. 修复后必查项

- [ ] 参数 year/month/company 是否真的在 query 里使用
- [ ] 硬编码的配置值是否应改为从 DB 读取
- [ ] 多公司查询是否用 `__in` 而非 `=`
- [ ] 前端分页是否真的每次只请求当前页（而不是 fetchAll 拉到前端再分）

---

## 八、相关提交记录

| Commit | 时间 | 内容 |
|--------|------|------|
| `038a656` | 05-25 | fix: income/expense list - real server-side pagination, remove client-side fetchAll pattern |
| `03f7f51` | 05-25 | fix: expense_list - remove bootstrap-select from filterYear (box-in-box) |
| `a27ff1e` | 05-24 | fix P2: invoice_summary 500 + stats.html confirmedIncome |
| `9518d52` | 05-24 | fix: P0 ar_ap_aging year/month + P1 balance_sheet WageRecord |
| `210d176` | 05-24 | fix: cash_flow_report respect month param |
| `ba7b7b9` | 05-24 | fix: P1 tax_summary/wage_summary read social config |
| `4ae315e` | 05-24 | fix: P2 customer_revenue + supplier + budget_execution |
| `43c0b0e` | 05-24 | fix: cash_flow frontend URL include month param |

---

## 九、已知遗留限制

| 项目 | 说明 |
|------|------|
| balance_sheet 前端无工资列 | 年度报表表格目前只显示：收入/支出/结余/笔数，无工资列。如需增加需改前端模板 |
| budget_execution_report 无执行率 | 只有 actual 实际支出，没有 budget 预算基数，需要新建 Budget 模型 |
| 龙旭科技(LS)数据全0 | 该公司无银行流水和工资记录，属于正常状态 |
