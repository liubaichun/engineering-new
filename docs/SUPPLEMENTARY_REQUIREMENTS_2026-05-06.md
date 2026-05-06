# GREEN 企业信息化管理系统 — 补充需求分析
**版本**：v2.0（基于 2026-05-06 系统现状审计）
**编制**：Hermes Agent
**审阅**：刘柏春

---

## 一、现状总览

### 1.1 已有模块（15个App）

| App | 模块 | 成熟度 | 数据量 |
|-----|------|--------|--------|
| `core` | 用户/认证/权限/通知/审计 | ✅ 完整 | 971登录/10通知/13员工 |
| `finance` | 收入/支出/发票/工资/员工/公司 | ✅ 完整 | 5收入/3支出 |
| `crm` | 客户/联系人/合同/商机/供应商 | ✅ 完整 | 7客户 |
| `tasks` | 项目/任务看板 | ✅ 完整 | 2项目 |
| `approvals` | 审批流/节点/模板 | ✅ 完整（多租户） | 有数据 |
| `equipment` | 设备台账 | ✅ 完整 | 7设备 |
| `material` | 物料台账 + BOM | ✅ 完整 | 9物料 |
| `purchasing` | 采购申请/订单/收货 | ✅ 完整（多租户） | 有数据 |
| `repair` | 维修请求/配件 | ✅ 完整（多租户） | 空 |
| `files` | 文件管理 | ✅ 可用 | 有数据 |
| `notifications` | 通知渠道（框架） | 🟡 框架有，渠道配置缺失 | — |
| — | 驾驶舱/统计 | 🟡 页面完整，无真实数据 | — |
| — | 站内通知（core通知） | ✅ 完整（多租户） | 10条 |

### 1.2 多租户隔离完成度

**59个业务表**中有 company_id 字段，迁移已 applied。core 日志3表（LoginLog/PermissionAuditLog/Notification）本轮修复后 company_id 列已存在。

### 1.3 当前数据

```
收入：5条    支出：3条    发票：0条    工资：0条
客户：7个    合同：0个    商机：0个
项目：2个    任务：0条
设备：7台    物料：9种
采购申请/订单/收货：有数据
维修请求：0条（repair模块新建中）
```

---

## 二、P0级缺失功能（影响核心业务流程）

### 2.1 库存管理（Inventory）— 最高优先级

**现状**：系统有物料台账（`material_material`）、有采购收货（`purchasing_purchase_receive`），但**没有独立的库存管理模块**。采购收货后物料直接确认，没有实际入库动作。

**缺失功能**：

| 功能 | 说明 | 影响 |
|------|------|------|
| 仓库（Warehouse） | 多仓库支持，warehouse_id关联 | 采购入库/销售出库无目标仓库 |
| 库位（StorageLocation） | 仓库内部分区/货架 | 无法定位物料具体位置 |
| 库存台账（InventoryLedger） | 每个物料+仓库的实时库存 | 无法查询当前库存量 |
| 采购入库单 | 采购收货后生成入库单，审核后入库存 | 采购收货后无法正式入库 |
| 销售出库单 | 销售订单确认后出库，扣减库存 | 无法完成销售流程 |
| 生产领料单 | BOM展开后按需领料 | 生产模块无法领料 |
| 库存盘点 | 定期盘点，调整账面库存 | 库存无法盘点 |
| 库存预警 | 低于安全库存自动提醒 | 无法设置最低库存 |
| 批次/序列号 | 物料支持批次或序列号管理 | 质量追溯无法实现 |

**建议方案**：新建 `apps/inventory` App，模型：Warehouse → StorageLocation → InventoryLedger（按物料+仓库记账）→ InventoryTransaction（出入库流水）。采购入库和销售出库是主要入口。

**API 端点规划**：
```
GET/POST   /api/inventory/warehouses/          — 仓库管理
GET/POST   /api/inventory/locations/           — 库位管理
GET/POST   /api/inventory/ledgers/             — 库存台账（查询库存）
GET/POST   /api/inventory/transactions/        — 库存流水
GET/POST   /api/inventory/purchase-in/         — 采购入库单
GET/POST   /api/inventory/sales-out/           — 销售出库单
GET/POST   /api/inventory/adjust/              — 库存盘点调整
```

---

### 2.2 BOM设备关联完善

**现状**：`material_bom` + `material_bom_node`（BOM树）+ `equipment_bom_relation`（设备配件关联）已建好，但设备详情页的"配件管理"Tab还没有前端页面和API。

**缺失功能**：

| 功能 | 说明 |
|------|------|
| 设备详情页配件Tab | 设备详情页显示关联的物料配件列表 |
| EquipmentBOMRelation API | 增删改查设备-物料关联关系 |
| BOM树前端展示 | 设备详情页展示物料BOM树状结构 |

**参考**：当前 `equipment/equipment/` API 正常（7台设备），只需新增 equipment_bom_relation 的 ViewSet 并在设备详情页接入。

---

### 2.3 文件管理增强（别名+分类）

**现状**：`files` App 有文件上传下载，但没有文件别名、分类管理。

**缺失功能**：

| 功能 | 说明 |
|------|------|
| 文件别名（alias） | 同一文件多个语义别名，方便检索 |
| 文件分类（category） | 支持自定义分类目录树 |
| FileCategory模型 | 分类目录，支持树形结构 parent_id |
| 文件批量上传/移动/复制 | 批量管理 |
| 文件标签（tag） | 多维度标签检索 |

---

## 三、P1级重要功能（提升系统完整性）

### 3.1 站内通知 + 外部渠道集成

**现状**：`core_notification` 有站内通知，SystemSetting 有邮箱配置字段（email_smtp_host等），但：
- 邮件实际发送未验证（EMAIL_BACKEND=console，仅打印到stdout）
- 飞书/企微/钉钉 Webhook 未集成
- 通知渠道配置Tab无前端页面

**缺失功能**：

| 功能 | 说明 |
|------|------|
| 邮箱域名配置Tab | SystemSetting 中配置企业邮箱域（如 `@company.com`）后自动限定注册用户 |
| 外部渠道Webhook配置 | 飞书/企微/钉钉机器人Webhook地址配置 |
| 通知渠道绑定 | 给用户绑定通知渠道（邮件/飞书/企微） |
| 真实邮件发送 | 将 EMAIL_BACKEND 改为 smtp，配置真实SMTP |
| 通知发送记录 | channels_notification_log 表已有但无API |

### 3.2 驾驶舱/统计 — 真实数据接入

**现状**：驾驶舱页面和图表完整，但所有统计数据返回0（`/api/stats/` 无 company_id 过滤，返回空）。

**根因**：驾驶舱 stats API 走的是硬编码假数据或无数据。需要把所有 stats 改为调用真实 API。

**修复清单**：

| 统计项 | 当前状态 | 修复方案 |
|--------|---------|---------|
| 总用户数 | 0 | User.objects.filter(company=auth_company).count() |
| 本月收入 | 0 | Income.objects.filter(company=auth_company, date__month=this_month).aggregate(Sum('amount')) |
| 本月支出 | 0 | Expense.objects.filter(...).aggregate(Sum('amount')) |
| 待审批数 | 0 | ApprovalFlow.objects.filter(company=auth_company, status='pending').count() |
| 项目进展 | 0 | Project.objects.filter(company=auth_company) |
| 逾期任务 | 0 | Task.objects.filter(project__company=auth_company, due_date<today, status!='done') |

---

### 3.3 采购管理完善 — 采购入库→库存联动

**现状**：采购模块已有 Request/Order/Receive，但 Receive（收货）只是收货记录，没有生成入库单。

**缺失**：PurchaseReceive 审核后应生成 InventoryTransaction（入库事务），自动增加库存台账。

---

### 3.4 审批流完善 — 统一两套审批

**现状**：系统同时存在：
1. **DRF ApprovalFlow**（`apps.approvals`）：正规审批流，可配置多级、会签/或签、超时升级
2. **Django Admin 审批**：finance/wage 等模型直接在 admin 点击"批准"按钮

**缺失**：统一使用 ApprovalFlow 审批，所有财务单据（收入/支出/发票/工资）通过 ApprovalFlow 流转。

---

### 3.5 客户关系完善 — 商机→合同→回款闭环

**现状**：CRM 有商机管理（`crm_opportunity`），但：
- 商机没有关联合同
- 合同没有关联回款计划（PaymentPlan 有，但没有 API/前端）
- 合同到期没有自动提醒

**缺失功能**：

| 功能 | 说明 |
|------|------|
| 商机状态推进 | 商机赢单→创建合同 |
| 合同→PaymentPlan | 创建合同时自动生成回款计划 |
| 回款计划API | PaymentPlan 的 ViewSet + 前端页面 |
| 合同到期提醒 | Notification 定时检查合同到期日 |

---

## 四、P2级功能（通用企业应用标配）

### 4.1 质量管理（QC）

| 功能 | 说明 |
|------|------|
| 来料质检（IQC） | 采购入库前进行质量检验 |
| 质检标准定义 | 按物料定义质检项目/允收标准 |
| 不良品处理 | 质检NG→退供应商/特采/报废 |

### 4.2 设备维护计划

| 功能 | 说明 |
|------|------|
| 设备保养计划 | 按时间/运行小时自动生成保养工单 |
| 设备点检表 | 日常点检记录 |
| 故障统计 | 设备故障率/MTBF分析 |

### 4.3 人力资源（HR）增强

**现状**：`finance_employee` 只有员工档案，没有招聘入职转正流程。

| 功能 | 说明 |
|------|------|
| 招聘岗位 | 发布招聘需求 |
| 入职流程 | 入职清单/资料提交 |
| 考勤管理 | 上下班打卡（GPS/外勤） |
| 假期管理 | 年假/病假/调休 |

### 4.4 行政管理

| 功能 | 说明 |
|------|------|
| 印章管理 | 印章使用申请/登记 |
| 证照管理 | 公司资质证照到期提醒 |
| 办公用品 | 办公用品申请/发放 |
| 会议室管理 | 会议室预约 |

### 4.5 系统运维

| 功能 | 说明 |
|------|------|
| API访问统计 | 记录每个 API 的调用量/响应时间 |
| 访问日志增强 | 详细的请求日志（当前 OperationAuditLog 已有框架） |
| 数据库定时备份 | 每日自动备份 |
| 操作日志导出 | 审计日志批量导出 |

---

## 五、技术债务（影响稳定性）

### 5.1 迁移历史漂移

部分迁移标记为 applied 但实际列不存在（如 `finance_wagerecord` 的 approval_flow FK），或列存在但迁移未标记：

```bash
# 检查 finance_wagerecord 实际列
core_login_log: company_id ✅（本轮修复后已存在）
但某些迁移文件描述了不存在的变更
```

**建议**：迁移清理不是紧急事项，当前能跑即可。

### 5.2 Finance 模块权限控制

Finance 模块当前有些 ViewSet 的 `get_queryset` 有 `auth_company` 过滤，但 finance 模块下的 `Employee`/`EmployeeCompany` 关联表未见完整的 company 过滤逻辑。

**建议**：对 Finance 模块做一次完整的 company_id 覆盖审计。

### 5.3 密码策略

当前密码无强度要求，无定期强制修改，无登录失败锁定。

---

## 六、补充需求优先级汇总

### 优先级矩阵

| 优先级 | 功能 | 工作量 | 价值 |
|--------|------|--------|------|
| P0-1 | 库存模块（Inventory App） | 高 | 🔴 核心 |
| P0-2 | BOM设备关联（API+前端） | 低 | 🔴 核心 |
| P0-3 | 驾驶舱真实数据接入 | 中 | 🔴 核心 |
| P0-4 | 文件别名+分类管理 | 低 | 🔴 核心 |
| P1-1 | 采购入库→库存联动 | 中 | 🟠 高 |
| P1-2 | 外部通知渠道（邮件/飞书Webhook） | 中 | 🟠 高 |
| P1-3 | 统一审批流（废弃Admin审批） | 高 | 🟠 高 |
| P1-4 | CRM合同→回款计划闭环 | 中 | 🟠 高 |
| P2-1 | 质量管理（IQC） | 中 | 🟡 中 |
| P2-2 | 设备保养计划 | 中 | 🟡 中 |
| P2-3 | HR增强（招聘/考勤） | 高 | 🟡 中 |
| P2-4 | 系统运维（备份/API统计） | 低 | 🟡 中 |

### 立即可行动项（不需产品设计）

1. **BOM设备关联**（低工作量）：EquipmentBOMRelation ViewSet 新建 + equipment_detail.html 配件Tab
2. **文件别名/分类**（低工作量）：FileCategory 模型 + 扩展 files API
3. **驾驶舱数据**（中工作量）：改造 `/api/stats/` 调用真实 ORM

---

## 七、补充需求 vs 系统现状对照

### 7.1 企业通用功能覆盖度

| 功能领域 | 现状 | 覆盖度 |
|---------|------|--------|
| 用户/权限/认证 | ✅ 完整 | 100% |
| 财务管理（收支票工资） | ✅ 完整 | 100% |
| 客户管理（CRM） | ✅ 基本完整，缺回款计划 | 85% |
| 项目/任务管理 | ✅ 完整 | 100% |
| 采购管理 | ✅ 完整，缺库存联动 | 90% |
| 设备管理 | ✅ 基本完整，缺保养计划 | 80% |
| 物料管理 | ✅ 完整，缺BOM前端展示 | 85% |
| 审批管理 | ✅ 基本完整，缺统一 | 90% |
| 文件管理 | 🟡 基础有，缺别名分类 | 50% |
| 通知系统 | 🟡 站内通知有，缺外部渠道 | 40% |
| 库存管理 | ❌ 完全没有 | 0% |
| 质量管理 | ❌ 无 | 0% |
| 人力资源 | 🟡 员工档案有，缺招聘考勤 | 30% |
| 行政管理 | ❌ 无 | 0% |
| 系统运维 | 🟡 部分有，缺备份监控 | 30% |

**综合成熟度**：约 65%（库存模块为最大缺口，其次是外部通知渠道和系统运维）

---

*文档版本：SUPPLEMENTARY_REQUIREMENTS_2026-05-06.md*
*下次更新：库存模块完成后再评估*
