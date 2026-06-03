
---

## 2026-06-02: 全系统第0周修复（死代码清理 + Expense修复 + 状态机对齐）

### 背景
基于 `docs/FULL_SYSTEM_AUDIT_2026-06-02.md` 摸底报告，执行第0周清理计划。

### 一、P1 — 死代码清理

#### 删除 equipment.bak
- **位置：** `apps/equipment.bak.20260601065724/`
- **操作：** 43和124两台服务器均已删除

#### 删除 permission_registry 残留
- **位置：** `apps/permission_registry/`
- **操作：** 43和124两台服务器均已删除（整个目录）

### 二、P0 — Expense模型双日期字段 + save()崩溃bug修复

#### 问题
1. `expense_date` 和 `date` 两字段共存，save()互相同步（技术债）
2. save()中 `hasattr(self.expense_date, 'date')` 在expense_date为字符串时崩溃

#### 修改
- **models_expense.py**：删除 `expense_date` 字段，简化save()为 `if not self.date: self.date = date.today()`
- **serializers.py**：删除 `expense_date` 序列化字段和同步逻辑
- **views_expense.py**：ordering/filter改用 `date`
- **filters.py**：字段名 `expense_date` → `date`
- **reports_common.py / reports_budget.py / reports_tax.py**：报表日期字段统一
- **classification_rules.py**：试算平衡表日期字段统一
- **bank_import_views.py / tax_invoice_import.py / import_views.py**：导入创建参数统一
- **templates/finance/expense_list.html**：前端字段引用统一
- **共修改15个文件**

#### 迁移
- 新建 `0043_remove_expense_expense_date_alter_expense_date_and_more.py`

#### 验证
- ✅ 43 migrate OK
- ✅ 124 migrate OK
- ✅ Django check 0 issues
- ✅ 两台gunicorn重启

### 三、P0 — Income/Expense状态机对齐

#### 问题
Income有 `received`（已到账），Expense只有 `confirmed`（已确认支出）无 `paid`（已付款）

#### 修改
- **models_expense.py**：EXPENSE_STATUS_CHOICES 新增 `('paid', '已付款')`
- **admin.py**：新增 `paid` 状态颜色（绿色）
- **templates/finance/expense_list.html**：前端统计纳入 `paid` 状态
- **新迁移文件**：自动生成（包含在0043中）

#### 验证
- ✅ 已有confirmed记录不受影响（choices变更不改变已存储值）
- ✅ `get_status_display()` 自动支持新状态
- ✅ 序列化器/过滤器无需修改

### 四、P1 — notifications vs channels 边界分析

#### 结论
**不是死代码，是合理的三层架构，无需修改：**

| 层 | app | 职责 |
|---|-----|------|
| 消息记录 | `core/models.py::Notification` | 谁、什么时间、什么消息 |
| 通知业务 | `apps/notifications/` | 用户偏好、发送规则、模块注册 |
| 渠道插件 | `apps/channels/` | 企微/飞书/钉钉/邮件等渠道实现 |

只需用文档说明即可（已记录在摸底报告和此CHANGELOG中）。

### 第0周完成情况

| 任务 | 状态 | 备注 |
|:---|:----:|:-----|
| 删除 equipment.bak | ✅ | 43+124 |
| 删除 permission_registry | ✅ | 43+124 |
| Expense双日期字段修复 | ✅ | 15个文件 + 迁移0043 |
| Expense save()崩溃bug | ✅ | 同步修复 |
| Income/Expense状态机对齐 | ✅ | Expense新增paid状态 |
|    notifications vs channels | ✅ | 已分析确认合理 |

---

## 2026-06-02: 第1-2周 应收应付闭环（Invoice→Contract关联 + BankStatement核销增强 + 到期提醒）

### 一、P0 — Invoice关联Contract

#### 改动
- **models_invoice.py**：新增 `contract` FK（`ForeignKey 'crm.Contract'`）
- **migrations/0044_add_invoice_contract_fk.py**：迁移文件
- **serializers.py**：InvoiceSerializer 新增 `contract_id` / `contract_name` / `contract_no` 字段
- **views_arap.py**：ARAPViewSet receivables/payables 的 `select_related` 新增 `contract`
- **views_invoice.py**：InvoiceViewSet queryset 新增 `select_related('contract', 'company')`
- **reports_arap.py**：账龄分析 `select_related('contract')` + 响应增加 `contract_no`/`contract_name`
- **templates/finance/ar_ap_list.html**：应收/应付明细表格新增"关联合同"列 + 链接到合同详情页 + 导出CSV增加合同列

#### 验证
- ✅ `python3 manage.py check` 0 issues
- ✅ 迁移 0044 已执行
- ✅ 页面正确显示"关联合同"列表头
- ✅ 无合同关联的发票显示"-"

### 二、P1 — BankStatement核销增强

#### 改动
- **views_invoice.py `match_statement`**：
  - 新增方向校验（收入发票→银行收入，支出发票→银行支出）
  - 核销时同步更新 BankStatement 的 `reconcile_status` 和 `reconcile_time`
  - 如果发票关联了合同，同步更新关联 PaymentPlan 状态为 `paid`
- **views_invoice.py `unmatch_statement`**：取消核销时同步恢复 BankStatement 状态
- **views_invoice.py `mark_paid`**：标记支付时同步更新关联 PaymentPlan

### 三、P2 — 应收应付到期提醒通知

#### 改动
- **check_alerts.py**：新增第8种预警类型「应收应付到期提醒」
  - 到期前7天的发票 → 每日通知（level=warning）
  - 已逾期的发票 → 每72小时通知（逾期≤30天 error，>30天 critical）
  - 通知内容包含：发票号、对方公司、金额、到期日、关联合同信息

### 完成情况

| 任务 | 状态 | 备注 |
|:---|:----:|:-----|
| Invoice→Contract FK | ✅ | 迁移0044，serializer，view，template |
| BankStatement核销增强 | ✅ | 方向校验+状态同步+PaymentPlan联动 |
| 到期提醒通知 | ✅ | 集成到check_alerts预警系统 |
| 43服务器验证 | ✅ | 页面显示正常 |
| 124服务器同步 | ✅ | 已同步并验证 |

---

## 2026-06-02: 第3周 库存流水化 + 编码规则（MaterialInboundLog + stock计算字段 + 编码规则可配置）

### 一、P2 — MaterialInboundLog入库日志模型

#### 改动
- **models.py**：新增 `MaterialInboundLog` 模型（material FK, quantity, unit_price, supplier, project, source_type）
- **migrations/0006_add_material_inbound_log.py**：迁移文件
- **serializers.py**：新增 `MaterialInboundLogSerializer` + MaterialSerializer 增加 `inbound_logs` 字段
- **views.py**：新增 `get_inbound_logs`（GET）和 `record_inbound`（POST）API

#### 验证
- ✅ `python3 manage.py check` 0 issues
- ✅ 迁移 0006 已执行

### 二、P2 — stock改为计算字段

#### 改动
- **Material模型**：`stock` DB字段→`@property`（init_stock + Σ入库 - Σ出库）
- **models.py**：新增 `init_stock`（期初库存），`stock` property，`total_inbound`/`total_outbound` property
- **migrations/0007_stock_to_init_stock.py**：RemoveField stock + AddField init_stock + 数据迁移（复制现有stock→init_stock）
- **serializers.py**：stock改为 `IntegerField(read_only=True)`，新增 init_stock/total_inbound/total_outbound
- **views.py**：`record_usage`/`record_inbound`不再手动修改stock字段；`stock_alert`过滤器改用annotation计算；移除 `stock` 从filter fields和ordering_fields

#### 验证
- ✅ 数据迁移已将现有库存值复制到 init_stock
- ✅ `stock` property 正确计算 init_stock + 入库 - 出库

### 三、P2 — 编码规则可配置

#### 改动
- **core/models.py**：新增 `CodingRule` 模型 + `generate_code()` 通用函数
- **migrations/0027_add_coding_rule.py**：迁移文件
- **material/models.py**：Material.save() 使用 generate_code('material')
- **crm/models.py**：Client/Supplier.save() 使用 generate_code('client') / generate_code('supplier')
- **finance/models_employee.py**：Employee.save() 使用 generate_code('employee')
- **equipment/models.py**：Equipment.save() 使用 generate_code('equipment')
- **crm/supplier_model.py**：同步更新
- **core/views_settings.py**：新增 `CodingRuleViewSet`（CRUD API → `/api/core/coding-rules/`）
- **core/urls.py**：注册路由

#### 验证
- ✅ 5个模块的统一编码规则已替换硬编码逻辑
- ✅ 默认规则：WL-（物料）、KH-%Y-（客户）、GYS-%Y-（供应商）、YG-%Y-（员工）、SB-（设备）
- ✅ 系统管理员可通过 API 在线修改编码规则（前缀、年份格式、流水号位数等）

### 完成情况

| 任务 | 状态 | 备注 |
|:---|:----:|:-----|
| MaterialInboundLog 模型+API | ✅ | 迁移0006，serializer，view |
| stock计算字段+数据迁移 | ✅ | 迁移0007，property+annotation |
| 编码规则可配置 | ✅ | 5个模型统一使用 generate_code() |
| Django check | ✅ | 0 issues |
| 43服务器验证 | ✅ | 页面+API均正常 |
| 124代码同步 | ✅ | 代码+迁移均已到位 |

---

## 2026-06-02: 第4周 商机管理增强（Pipeline看板 + 项目驱动销售）

### 一、P0 — Pipeline看板视图

#### 改动
- **views.py (crm)**：新增 `kanban` action — 按线索/意向/方案/商务4列返回商机卡片数据（含项目关联）
- **opportunity_kanban.html**：新建看板模板 — 拖拽卡片推进商机阶段（调用 `advance_stage`）
- **config/urls.py**：新增路由 `crm/opportunities/kanban/`
- **opportunity_list.html**：工具栏新增「看板视图」按钮

### 二、P1 — 项目驱动销售

#### 改动
- **models.py (crm)**：Opportunity新增 `project` FK（ForeignKey 'tasks.Project'）
- **migrations/0032_add_opportunity_project_fk.py**：迁移文件
- **serializers.py (crm)**：新增 `project_id`/`project_name`/`project_code` 只读字段
- **views_project.py (tasks)**：ProjectViewSet新增 `create_opportunity` action — 通过项目关联合同找客户，创建商机（stage=qualify, probability=30）
- **views.py (crm)**：OpportunityViewSet get_queryset 新增 `select_related('project')`；kanban action 新增 project 数据

### 完成情况

| 任务 | 状态 | 备注 |
|:---|:----:|:-----|
| Pipeline看板视图（4列/拖拽/卡片） | ✅ | 线索→意向→方案→商务 |
| 列表/看板视图切换导航 | ✅ | 双向导航 |
| 项目→商机自动创建 | ✅ | 需合同关联客户 |
| Opportunity新增project FK | ✅ | 迁移0032 |
| 43服务器验证 | ✅ | 页面+API均正常 |
| 124服务器同步 | ⏳ | 待同步 |
