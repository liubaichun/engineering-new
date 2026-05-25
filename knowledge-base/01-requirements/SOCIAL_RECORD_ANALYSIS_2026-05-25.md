# 社保管理模块 — 需求分析文档

**日期：** 2026-05-25
**操作人：** Hermes Agent
**状态：** 待开发

---

## 一、问题背景

深圳市百川软件科技发展有限公司每月从社保局下载「社保费申报明细」Excel，包含9张分险种明细表（企业养老/地补养老/基本医疗/失业/生育/工伤，各有个人缴和单位缴）。目前 GREEN 系统中没有对应的数据表，社保数据只能通过 WageRecord 反推，导致：

1. **数据不准确**：用固定费率（10.3%/23.0%）反推，单位部分算不准，地补养老等附加项目完全缺失
2. **与社保局数据脱节**：无法和社保局实际扣款金额做核销
3. **报表数据断裂**：税费汇总表、预算执行表、资产负债表的社保数据都依赖反推，而非实际值

---

## 二、现有数据现状

### 2.1 现有社保相关表

| 表 | 字段 | 状态 | 用途 |
|----|------|------|------|
| `Employee` | `has_social_insurance` / `social_insurance_deduction` | 存在但从未被后端读取 | 前端工资单填充时参考 |
| `Employee` | `has_housing_fund` / `housing_fund_deduction` | 同上 | 前端工资单填充时参考 |
| `CompanySocialConfig` | 养老/医疗/失业/工伤各险种个人费率+单位费率 | 配置了但未被后端调用 | 前端 JS 按公式算扣款金额 |
| `WageRecord` | `social_insurance` / `housing_fund`（本月汇总值） | 正常使用 | 个税计算、累计预扣法 |

**结论：三张表的社保数据各自为政，没有任何联动。**

### 2.2 现有 Bug

| # | 严重度 | 问题 |
|----|--------|------|
| B-S1 | **P0** | `tax_summary_report` 查询 `expense_type='social'` 但银行导入时写的是 `expense_type='税务'`（映射为'税款'），永远查不到，社保显示为0 |
| B-S2 | **P1** | `tax_summary_report` 用硬编码 `emp_rate=10.3`、`com_rate=23.0` 反推社保，和实际社保局数据不符 |
| B-S3 | **P1** | `budget_execution_report` 同上 |
| B-S4 | **P1** | `WageRecord.social_insurance` 纯手动录入，无自动计算逻辑 |

---

## 三、设计方案

### 3.1 新建表：SocialRecord（社保申报记录）

每行 = 一个员工在某个费款所属期的社保费用明细。

```
字段设计：
- id
- company (FK)          → 公司
- employee (FK)         → 员工
- id_card               → 身份证号（用于匹配）
- year_month            → 费款所属期（YYYY-MM）
- pension_employee      → 企业养老个人
- pension_company      → 企业养老单位
- pension_bup_employee → 地补养老个人
- pension_bup_company   → 地补养老单位
- medical_employee      → 基本医疗个人
- medical_company       → 基本医疗单位
- unemployment_employee → 失业个人
- unemployment_company  → 失业单位
- injury_company       → 工伤单位
- birth_company        → 生育单位
- housing_fund_employee → 公积金个人
- housing_fund_company  → 公积金单位
- total_employee       → 个人缴合计（自动计算）
- total_company        → 单位缴合计（自动计算）
- remark               → 备注
- created_at / updated_at
```

**复合唯一索引**：`{employee, id_card, year_month}`，防止重复导入。

### 3.2 菜单位置

```
财务
├── 工资管理
├── 员工管理
├── 社保管理          ← 新增（和工资管理平级）
├── 收支管理
├── 发票管理
├── 财务报表
└── 银行流水
```

### 3.3 菜单位置

放在「财务」分组下，和工资管理平级，不要嵌套在员工管理里。原因：社保记录是按月申报的独立业务线，嵌套会让菜单层级过深。

---

## 四、需要打通的模块

### 4.1 工资单创建/编辑（P1）

**现状**：选员工+年月后，社保扣款需手动录入，或前端用 CompanySocialConfig 按公式算。

**改动**：
- 员工+年月确定后，自动从 SocialRecord 读取当月 `total_employee` → 填入 `WageRecord.social_insurance`
- 自动从 SocialRecord 读取 `housing_fund_employee` → 填入 `WageRecord.housing_fund`
- 若 SocialRecord 无记录，保留用户手动录入或前端计算逻辑

**触发时机**：工资单表单上员工下拉框选择变化时。

### 4.2 税费汇总表（P1）

**现状**：`tax_summary_report` 查询 `expense_type='social'` 的 Expense 记录，但银行导入时社保写的是 `expense_type='税务'`。

**改动**：
- 修复：银行流水识别为"社保公积金"后，写入 `expense_type='social'`（而非 `'税务'`）
- 社保单位缴从 SocialRecord 汇总（`total_company`），不再用硬编码反推
- 删除 `reports_v2.py` 中两处硬编码 `emp_rate=10.3`、`com_rate=23.0`

### 4.3 预算执行表（P1）

同上，社保单位部分从 SocialRecord 汇总，删除硬编码。

### 4.4 资产负债表（P1）

目前社保部分为空（只有工资支出有数据）。从 SocialRecord 汇总单位缴合计，作为"社保公积金支出"列示。

### 4.5 银行流水核销（P2）

社保局扣款流水（摘要含"社保费"）进来后：
- 自动和 SocialRecord 的 `total_company` 做匹配
- 标记该条 SocialRecord 为"已核销"（新增 `is_reconciled` 字段）
- 未匹配的社保流水提示"无法核销，请检查社保申报数据"

### 4.6 员工档案同步（P2）

导入 SocialRecord 后，自动用个人缴合计更新对应 Employee 的 `social_insurance_deduction`（作为参考值存档）。

---

## 五、导入功能设计

### 5.1 导入入口

在社保管理页面（`social_record_list.html`）有「导入」按钮，点击弹出上传框，支持上传社保局 Excel。

### 5.2 Excel 格式处理

深圳社保局 Excel 结构：
- Sheet 名含"养老"等关键词
- 列：证件号码 / 费款所属期 / 各险种个人缴 / 各险种单位缴
- 一人一行，每行 = 一个员工某月的分险种明细

**导入逻辑**：
1. 读取所有 Sheet，聚合同一员工同一月份的数据
2. 按证件号匹配 Employee（id_card 字段）
3. 写入 SocialRecord，若重复（employee + year_month 已存在）则覆盖
4. 返回：成功条数 / 失败条数 / 失败原因列表

### 5.3 导入模板

系统提供「社保导入模板.xlsx」，列名和社保局 Excel 一致，包含：
- 证件号码 / 姓名 / 费款所属期 / 企业养老个人 / 企业养老单位 / 地补养老个人 / 地补养老单位 / 基本医疗个人 / 基本医疗单位 / 失业个人 / 失业单位 / 工伤单位 / 生育单位 / 公积金个人 / 公积金单位

---

## 六、API 设计

### 6.1 SocialRecordViewSet

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/finance/social-records/` | 列表（支持 year/month/company 筛选） |
| GET | `/api/finance/social-records/{id}/` | 详情 |
| POST | `/api/finance/social-records/import/` | Excel 导入（multipart/form-data） |
| DELETE | `/api/finance/social-records/{id}/` | 删除单条 |
| GET | `/api/finance/social-records/export/` | 导出 Excel |

### 6.2 工资单联动 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/finance/wage-records/autofill-social/?employee_id=&year_month=` | 查询 SocialRecord，返回 social_insurance + housing_fund 用于工资单填充 |

---

## 七、实现顺序

| 优先级 | 内容 | 预计工作量 |
|--------|------|-----------|
| **P0** | 新建 `SocialRecord` 模型 + 迁移 | 中 |
| **P0** | `SocialRecordSerializer` + `SocialRecordViewSet` | 中 |
| **P0** | `social_record_list.html`（列表页 + 导入按钮） | 中 |
| **P0** | Excel 导入功能（`import_social_records`） | 大 |
| **P1** | 工资单创建/编辑时自动从 SocialRecord 带出社保数据 | 中 |
| **P1** | 修复 `tax_summary_report`（expense_type 错 + 硬编码） | 小 |
| **P1** | 修复 `budget_execution_report`（同上） | 小 |
| **P1** | 修复 `balance_sheet` 社保部分（从 SocialRecord 汇总） | 小 |
| **P2** | 银行流水社保核销 | 大 |
| **P2** | 员工档案同步 | 小 |

---

## 八、文件清单

| 文件 | 动作 |
|------|------|
| `apps/finance/models.py` | 新增 `SocialRecord` 模型 |
| `apps/finance/serializers.py` | 新增 `SocialRecordSerializer` |
| `apps/finance/views.py` | 新增 `SocialRecordViewSet` + 工资单联动 action |
| `apps/finance/urls.py` | 新增路由 |
| `apps/finance/bank_import_views.py` | 修复社保流水 `expense_type='social'` |
| `apps/finance/reports_v2.py` | 删除硬编码，改为从 SocialRecord 汇总 |
| `templates/finance/social_record_list.html` | 新建列表页（含导入功能） |
| `templates/finance/wage_list.html` | 增加"自动带出社保"按钮 |
| `templates/base.html` | 侧边栏增加"社保管理"菜单 |
| `docs/SOCIAL_RECORD_ANALYSIS_2026-05-25.md` | 本文档 |

---

*文档创建后请更新 CHANGELOG 和相关待办清单。*