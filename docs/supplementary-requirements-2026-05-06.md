# 企业信息化管理系统 GREEN — 补充需求分析
**编制日期**：2026-05-06
**基于版本**：`6702be2`（master分支最新）
**分析深度**：5个子模块全面审计（银行流水/采购/CRM商机/设备管理/项目管理）+ 系统级审计（多租户/驾驶舱/审批流/审计日志）

---

## 一、系统现状总览

### 1.1 已完成开发的功能模块

| 模块 | 状态 | 说明 |
|------|------|------|
| 驾驶舱（Dashboard） | ⚠️ 空数据 | 页面+图表完整，API返回空数据（company_id过滤问题） |
| CRM客户管理 | ✅ 完整 | Client/Supplier/Contract/Contact/FollowUpRecord 含company_id |
| CRM商机管理 | ✅ 基础完整 | Opportunity + Pipeline漏斗，weighted_amount前端未用 |
| 财务模块 | ✅ 较完整 | Income/Expense/WageRecord/Invoice/BankAccount/BankStatement |
| 银行流水导入 | ✅ 刚修复 | 刚修复 source_display 和反向追溯字段（commit 6702be2） |
| 采购管理 | ⚠️ 有Bug | 状态机前端过滤缺失 + 级联删除风险 |
| 设备管理 | ⚠️ 有Bug | record_repair缺装饰器 + BOM关联正常 |
| 设备报修工单 | ✅ 基础完整 | RepairRequest 状态机完整 |
| 物料BOM | ✅ 基础完整 | MaterialBOM + BOMNode树形结构正常 |
| 项目管理 | ⚠️ 有Bug | 甘特图正常，审批流状态不同步 |
| 审批流引擎 | ⚠️ 有Bug | project类型审批通过后状态不同步 |
| 通知系统 | ✅ 完整 | Signal信号自动记录，API已修复 |
| 系统配置 | ✅ 基础完整 | SystemSetting 全局配置（无多租户） |
| 审计日志 | ⚠️ 缺失隔离 | OperationAuditLog 存在但无company_id |

---

## 二、按模块问题清单（按优先级排序）

### P0 — 阻断性问题（影响商业化交付）

#### P0.1：多租户隔离不完整 — Finance Reports API
**影响**：用户可通过URL参数查任意公司的财务报表
**位置**：`apps/finance/reports_v2.py`
**现状**：所有Report API（cash_flow/expense_analysis/income_statement等）只从 `request.query_params.get('company')` 获取company，无自动用户公司过滤
**修复方向**：在 `reports_v2.py` 入口统一加入 `request.user.company_id` 强制过滤

#### P0.2：多租户隔离不完整 — Employee 模块
**影响**：所有登录用户可查看/操作所有公司的员工数据
**位置**：`apps/finance/views.py:1538, 1721`（注释明确标注"多租户隔离已移除"）
**现状**：Employee/EmployeeCompany ViewSet 的 `get_queryset()` 无 `company_id` 过滤
**修复方向**：恢复 `company_id=user.company_id` 过滤

#### P0.3：多租户隔离不完整 — Tasks 模块
**影响**：Task/TaskStageInstance/StageActivity 等无company隔离，多用户数据混淆
**位置**：`apps/tasks/views.py:491, 673`（注释标注"公司隔离已移除"）
**修复方向**：Task关联Project（已有company_id），通过 `project__company_id` 过滤

#### P0.4：审批流状态不同步 — Project 类型
**影响**：项目立项审批通过后，`Project.approval_status` 不会自动更新为"approved"，页面停留在"pending"
**位置**：`apps/approvals/views.py` 的 `_sync_business_status` 函数（第19-67行）只处理 expense/income/wage_record，不处理 'project'
**修复方向**：在 `_sync_business_status` 中加入 `elif obj_type == 'project': project.approval_status = 'approved'; project.save()`

#### P0.5：采购管理 — 级联删除导致数据孤儿
**影响**：删除采购申请单（PurchaseRequest）时，关联的采购订单（PurchaseOrder）不删除，变成孤儿记录
**位置**：`apps/purchasing/models.py` — `PurchaseOrder.purchase_request = SET_NULL`
**修复方向**：改为 `PROTECT`（阻止删除有订单的采购申请）或 `CASCADE`（删申请时级联删订单），按业务逻辑选择

---

### P1 — 重要功能缺失（影响业务完整性）

#### P1.1：采购管理 — 状态机前端过滤不完整
**影响**：PurchaseRequest 的 `partially_ordered`/`ordered` 状态和 PurchaseOrder 的 `partial_shipped`/`partial_received`/`invoiced` 状态无法通过前端下拉过滤
**位置**：
- `templates/purchasing/purchase_request_list.html` — 状态下拉缺少选项
- `templates/purchasing/purchase_order_list.html` — 状态下拉缺少选项
- `purchase_order_list.html` — 发货按钮条件遗漏 `partial_shipped`/`partial_received`
**修复方向**：补全状态下拉选项，更新JS状态过滤逻辑

#### P1.2：采购管理 — 统计卡片未填充
**影响**：`stat-amount`（本月预估总额）和 `stat-monthly`（本月新增订单）数据卡片创建后从未被 `updateStats()/refreshStats()` 填充
**位置**：
- `templates/purchasing/purchase_request_list.html`
- `templates/purchasing/purchase_order_list.html`
**修复方向**：新增统计API端点（已有API返回数据，需前端接入）

#### P1.3：CRM商机 — `weighted_amount` 前端未展示
**影响**：Serializer计算了加权金额（expected_amount × probability / 100），但前端列表和详情弹窗都没有展示
**位置**：`templates/crm/opportunity_list.html`
**修复方向**：在商机列表表格增加"加权金额"列，详情弹窗增加该字段

#### P1.4：CRM商机 — `validate_stage` 空实现
**影响**：商机标记为 lost 时未强制要求填写 lost_reason，数据不完整
**位置**：`apps/crm/serializers.py:249-251`
**修复方向**：实现 `validate_stage` 方法，stage='lost' 时要求 lost_reason 非空

#### P1.5：设备管理 — `record_repair` API未注册
**影响**：`record_repair` 方法缺少 `@action` 装饰器，无法通过API调用维修记录
**位置**：`apps/equipment/views.py:124`
**修复方向**：添加 `@action(detail=True, methods=['post'])` 装饰器

#### P1.6：采购管理 — `receive_date` 无默认值
**影响**：创建 PurchaseReceive 时未自动填充 `receive_date`，可能导致入库记录日期为空
**位置**：`apps/purchasing/views.py` 的 `perform_create`
**修复方向**：`receive_date = timezone.now().date()` 自动填充

#### P1.7：甘特图 — `gantt_data` 与 `gantt_all` 处理不一致
**影响**：两个API对 Task.start_date 的处理逻辑不同，`gantt_data` 忽略 start_date 始终用 due_date-7
**位置**：`apps/tasks/views.py:396-470`
**修复方向**：统一使用 `t.start_date or (t.due_date - timedelta(days=7))`

---

### P2 — 体验优化问题（不影响核心流程）

#### P2.1：采购管理 — 详情弹窗表头"规格"字段不存在
**影响**：PurchaseRequestItem 没有 `specification` 字段，详情弹窗表头显示"规格"但数据列空白
**位置**：`templates/purchasing/purchase_request_list.html` 详情弹窗明细表头
**修复方向**：将表头"规格"改为"描述"或保留后端字段映射修正

#### P2.2：采购管理 — ListSerializer 字段缺失
**影响**：Detail 视图可看到 `reason`/`remark`/`actual_delivery_date`，但列表视图没有暴露这些字段
**位置**：各 ListSerializer 缺少部分 Detail 字段
**修复方向**：按需补全（低优先级，不影响主流程）

#### P2.3：CRM — Pipeline 漏斗 `probability` 字段未用
**影响**：`pipeline/` API 返回 `probability` 和 `total_weighted`，前端漏斗展示区未使用
**位置**：`templates/crm/opportunity_list.html` 漏斗渲染区
**修复方向**：在漏斗统计卡片中展示加权总额

#### P2.4：系统配置 — SystemSetting 无多租户
**影响**：所有公司共享同一套系统配置（可能是预期行为，但需确认）
**位置**：`apps/core/models.py:SystemSetting`
**说明**：通知渠道、飞书WebHook等若是按公司配置，则需要加 company_id；若是系统全局（如Logo/名称），则当前正确

#### P2.5：审计日志 — OperationAuditLog 无 company_id
**影响**：审计日志不区分公司，全局可见；无法按公司查询操作日志
**位置**：`apps/core/models.py:337`
**修复方向**：新增 `company_id` 字段，通过信号自动填充（需要迁移）

---

### P3 — 架构设计建议（非阻断）

#### P3.1：CRM商机 — `product_lines` 用字符串而非正经M2M
**现状**：商机与产品的关联用逗号分隔字符串存储，非规范化关系
**建议**：若有产品线管理需求，建议新建 `OpportunityProduct` 中间表

#### P3.2：Material/Equipment 模型无独立 company_id
**现状**：物料/设备模型无 company 字段，通过关联的 Project 间接获取公司
**影响**：无法直接按公司查询物料目录（需通过项目间接过滤）
**建议**：评估是否需要独立的物料公司归属

#### P3.3：ApprovalNode/ApprovalTemplate 无 company_id
**现状**：审批模板和审批节点无公司归属，无法实现公司级审批流程定制
**建议**：若有按公司定制审批流程的需求，需补充 company 字段

---

## 三、补充需求优先级矩阵

| 优先级 | 编号 | 模块 | 问题 | 预计工时 | 风险 |
|--------|------|------|------|----------|------|
| P0 | P0.1 | Finance Reports | 多租户隔离缺失 | 2h | 数据泄露 |
| P0 | P0.2 | Employee | 多租户隔离移除 | 1h | 数据泄露 |
| P0 | P0.3 | Tasks | 多租户隔离移除 | 2h | 数据泄露 |
| P0 | P0.4 | Approvals | project审批状态不同步 | 1h | 业务逻辑错误 |
| P0 | P0.5 | Purchasing | 级联删除数据孤儿 | 1h | 数据完整性 |
| P1 | P1.1 | Purchasing | 状态机前端过滤缺失 | 2h | 业务流转不完整 |
| P1 | P1.2 | Purchasing | 统计卡片未填充 | 2h | 统计功能失效 |
| P1 | P1.3 | CRM | weighted_amount前端未展示 | 1h | 功能不完整 |
| P1 | P1.4 | CRM | validate_stage空实现 | 1h | 数据质量 |
| P1 | P1.5 | Equipment | record_repair未注册API | 0.5h | API不可用 |
| P1 | P1.6 | Purchasing | receive_date无默认值 | 0.5h | 数据不完整 |
| P1 | P1.7 | Tasks | gantt_data/gantt_all不一致 | 0.5h | 数据显示错误 |
| P2 | P2.1 | Purchasing | 详情弹窗规格字段不存在 | 0.5h | UI显示错误 |
| P2 | P2.2 | Purchasing | ListSerializer字段缺失 | 1h | API不一致 |
| P2 | P2.3 | CRM | Pipeline漏斗probability未用 | 1h | 功能未利用 |
| P2 | P2.4 | Core | SystemSetting多租户确认 | 1h | 需确认架构 |
| P2 | P2.5 | Core | AuditLog无company_id | 2h | 审计不完整 |

---

## 四、商业化成熟度评估

| 维度 | 当前得分 | 说明 |
|------|----------|------|
| 多租户隔离 | 5/10 | CRM/Finance/Purchasing 已实现，Tasks/Employee/Reports 未完成 |
| 数据完整性 | 6/10 | 级联删除风险、默认值缺失、审批状态不同步 |
| 功能完整度 | 7/10 | 核心模块齐全，但采购/审批等状态机不完整 |
| 驾驶舱可用性 | 3/10 | 页面完整但数据全空（company_id过滤问题） |
| API一致性 | 7/10 | Serializer与模板字段整体对齐，少量不一致 |
| 审计追踪 | 6/10 | 审计日志存在但无多租户隔离 |

**综合成熟度**：约 **5.5/10**（刚过及格线，P0问题需优先修复）

---

## 五、推荐处理顺序

```
第一轮（P0 阻断性Bug，1-2天）
  ① P0.4 审批流 project 状态不同步（1h）
  ② P0.5 采购管理级联删除（1h）
  ③ P0.1 Finance Reports 多租户（2h）
  ④ P0.2+P0.3 Employee+Tasks 多租户（3h）

第二轮（P1 重要功能，2-3天）
  ⑤ P1.1-P1.7 采购管理状态机+统计+Bug（8h）
  ⑥ P1.3-P1.4 CRM商机（2h）
  ⑦ P1.5-P1.7 设备+甘特图（2h）

第三轮（P2 体验优化，1-2天）
  ⑧ P2.x 各项体验问题（5h）
  ⑨ P2.5 审计日志 company_id（2h）
```

---

*文档版本：2026-05-06-v1，基于 commit 6702be2*
