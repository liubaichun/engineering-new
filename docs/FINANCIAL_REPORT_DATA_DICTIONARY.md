# 财务报表数据口径文档

> 本文档定义每个报表的数据来源、计算逻辑和业务含义。
> 最后更新：2026-05-27

---

## 1. 月度报表 / 年度报表

**API 端点**: `reports/monthly/`, `reports/yearly/`

**数据来源**: `Income` 表（收入）、`Expense` 表（支出）

**计算逻辑**:
| 指标 | 来源 | 计算方式 |
|------|------|----------|
| `total_income` | Income.amount | SUM(amount)，按公司/月份筛选 |
| `total_expense` | Expense.amount | SUM(amount)，按公司/月份筛选 |
| `balance` | 差值 | total_income - total_expense |
| `income_count` | Income 记录数 | COUNT(id) |
| `expense_count` | Expense 记录数 | COUNT(id) |
| `income_by_category` | Income.income_category | 按收入科目分组 SUM |
| `wage_expense` | WageRecord.gross_salary | SUM(gross_salary) |
| `other_expense` | Expense | total_expense - wage_expense - social - tax |

**内部转账排除**: 收入端排除 `customer IN (所有注册公司名)` 的记录（P1-2）

**业务含义**: 展示各公司月度/年度收支情况和结余。用于日常经营管理，非会计准则报表。

---

## 2. 收支汇总表

**API 端点**: `reports/revenue-expense-summary/`

**数据来源**: Income、Expense、WageRecord、SocialRecord

**计算逻辑**:
| 指标 | 来源 |
|------|------|
| `total_income` | Income（排除内部转账） |
| `total_expense` | Expense（排除内部转账） |
| `wage_expense` | WageRecord.gross_salary |
| `social_expense` | SocialRecord.total_company |
| `other_expense` | total_expense - wage_expense - social_expense - tax |
| `balance` | total_income - total_expense |

**业务含义**: 精简版收支总览，每公司一行，快速了解经营状况。

---

## 3. 银行余额变动表

**API 端点**: `reports/cash-flow/`

**数据来源**: BankStatement（银行流水表）

**计算逻辑**:
| 指标 | 来源 |
|------|------|
| `beginning_balance` | 当期初 BankStatement 前一条记录的余额 |
| `total_income` | BankStatement(direction='incoming').amount SUM |
| `total_expense` | BankStatement(direction='outgoing')/wage/payment.amount SUM |
| `ending_balance` | 当期末 BankStatement 最后一条记录的余额 |

**业务含义**: 展示各银行账户的资金流入/流出/余额变动情况。原名"现金流量表"。
**⚠️ 注意**: 此表基于银行流水数据，非会计意义上的现金流量表。

---

## 4. 应收应付账龄

**API 端点**: `reports/ar-ap-aging/`

**数据来源**: ARAP（应收应付表）

**计算逻辑**: 按账龄区间分组（0-30天/31-60天/61-90天/91-180天/180天+）

**业务含义**: 展示客户未收款和供应商未付款的账龄分布，帮助管理资金回笼和付款计划。

---

## 5. 工资汇总

**API 端点**: `reports/wage_summary/`

**数据来源**: WageRecord（工资单记录）

**计算逻辑**:
| 指标 | 计算方式 |
|------|----------|
| `total_gross` | SUM(gross_salary) |
| `total_social_insurance` | SUM(employee_social) |
| `total_housing_fund` | SUM(employee_housing_fund) |
| `total_tax` | SUM(tax) |
| `total_net` | SUM(net_salary) |

**业务含义**: 各公司月度应发工资、社保公积金扣款、个税和实发金额汇总。

---

## 6. 发票汇总

**API 端点**: `reports/invoice_summary/`

**数据来源**: Invoice（发票表）

**计算逻辑**: 按公司统计各状态发票数量和金额

| 指标 | 含义 |
|------|------|
| `issued_count` | 已开票/已收票 |
| `pending_count` | 待收/待付 |
| `paid_count` | 已完成 |
| `cancelled_count` | 已作废 |
| `valid_amount` | 有效发票金额合计（排除作废） |

**业务含义**: 各公司的发票开具和收取概览。

---

## 7. 发票多维度汇总（P2-2）

**API 端点**: `reports/invoice-dimension/`

**数据来源**: Invoice（发票表），排除 status='cancelled'

**维度**:
| 维度 | 分组字段 | 说明 |
|------|----------|------|
| 按发票类型 | invoice_type | 增值税专用发票 vs 普通发票 |
| 按税率 | tax_rate | 按税率汇总（1%, 3%, 6%, 13% 等） |
| 按对方公司 | counterparty | Top 20 对方公司排名 |

**汇总指标**: count, total_amount(不含税), total_tax(税额), net_amount(价税合计)

**业务含义**: 从多维度分析发票构成，了解主要合作伙伴和发票类型分布。

---

## 8. 客户收入排行（P2-1 增强）

**API 端点**: `reports/customer-revenue/`

**数据来源**: Income（收入表）

**计算逻辑**:
1. 排除内部公司转账（customer 为注册公司名的记录）
2. 按公司/客户分组汇总收入
3. 若记录已关联 CRM Client(`client_ref`)，优先使用 CRM 名称

**业务含义**: 各客户收入贡献排行，了解核心客户群体。

**CRM 标准化（P2-1）**: 当 Income.client_ref 不为空时，显示 CRM 标准化名称而非原始文本。

---

## 9. 供应商支出（P2-2 增强）

**API 端点**: `reports/supplier-expense/`

**数据来源**: Expense（支出表）

**分类逻辑**:
| 类别 | 判断规则 |
|------|----------|
| 企业供应商 | 不在员工名单 + 不在 CRM individual 名单 + 非纯中文姓名(2-4字) |
| 个人供应商 | 员工姓名匹配 / CRM individual / 纯中文姓名(2-4字) |
| 内部转账 | 无供应商名 |

**企业排名**: 按支出金额降序，取 Top N

**CRM 标准化（P2-1）**: 当 Expense.supplier_ref 不为空时，优先使用 CRM 名称。

---

## 10. 税费汇总（P1-1 修复）

**API 端点**: `reports/tax-summary/`

**数据来源**: Income（增值税）、Expense（企业所得税/附加税）、WageRecord（个税）、SocialRecord（社保）

**计算逻辑**:
| 税费 | 来源 | 计算 |
|------|------|------|
| `output_vat` | Income × 6% | SUM(amount) × 6%（6%为默认简易税率） |
| `input_vat` | Expense(税费类别) | expense_category='税款' 的合计 |
| `net_vat` | 差值 | output_vat - input_vat（逐公司计算后汇总） |
| `corporate_tax` | Expense | expense_category__icontains='所得税' |
| `surtax` | Expense | expense_category__icontains='附加' |
| `personal_tax` | WageRecord | SUM(tax) |
| `social_total` | SocialRecord | SUM(total_company) |

**⚠️ 注意**: output_vat 使用默认 6% 计算，非实际销项税率。
如需精确增值税，请集成税务系统。

---

## 11. 预算执行表（P2-3 增强）

**API 端点**: `reports/budget-execution/`

**数据来源**: Expense（实际支出）、WageRecord（工资）、SocialRecord（社保）、Budget（预算）

**计算逻辑**:
| 费用类型 | 实际支出来源 | 预算来源 |
|----------|-------------|----------|
| 工资薪酬 | WageRecord.gross_salary | Budget(expense_type='salary') |
| 社保公积金 | SocialRecord.total_company | Budget(expense_type='social') |
| 办公/差旅/通信/招待/营销/研发/税费 | Expense.expense_category icontains 关键词 | Budget(expense_type 匹配) |
| 其他 | 不计入 | Budget(expense_type='other') |

**执行率**: `actual / budget × 100%`（预算为 0 时显示 "-"）

**业务含义**: 各公司费用执行情况对比预算，帮助控制成本。

---

## 数据同步说明

| 数据来源 | 同步方式 | 更新频率 |
|----------|----------|----------|
| Income/Expense | 银行流水导入 / 手工录入 | 实时 |
| WageRecord | 工资单导入/计算 | 月 |
| SocialRecord | 社保申报导入 | 月 |
| Invoice | 税控导入 / 手工录入 | 实时 |
| Budget | 手工录入（预算管理页面） | 按需 |
| BankStatement | 银行流水导入 | 实时 |
| CRM Client/Supplier | 手工录入 | 按需 |

---

## 核心假设与限制

1. 本系统为 **多公司经营管理台账**，非专业会计软件
2. 所有报表未经会计准则审计，不保证与财务报表完全一致
3. 增值税计算使用默认 6% 简易税率（不区分服务/货物类型）
4. 内部转账排除基于公司名精确匹配
5. 预算执行率仅反映全年预算对比，不支持月度预算对比
