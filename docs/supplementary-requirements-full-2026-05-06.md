# 企业信息化管理系统 GREEN — 通用企业应用补充需求分析
**编制日期**：2026-05-06
**系统版本**：`bf375d6`（P0+P1+P2全部已修复）
**分析维度**：通用企业应用功能全景 × 当前系统现状 × 补充需求优先级

---

## 一、报告概述

本报告以通用制造/贸易企业信息化系统为基准，对比 GREEN 系统当前功能覆盖情况，识别尚未满足的通用企业应用需求。

**分析结论**：GREEN 系统核心业务模块（CRM、采购、财务、审批）已具备较好基础，经过前两轮修复（P0×5 + P1×7 + P2×5），阻断性问题已全部清零。但**多租户隔离存在系统性漏洞**——大量业务表缺少 `company_id` 字段，导致数据跨公司可见、数据串门等问题。这是商业化交付前**必须解决的结构性问题**。

---

## 二、通用企业应用功能全景图

以下矩阵对比了通用 ERP 系统应有的功能域与 GREEN 当前状态。

### 2.1 功能域覆盖矩阵

| 功能域 | 子模块 | 通用企业应有功能 | GREEN当前状态 | 差距等级 |
|--------|--------|-----------------|--------------|----------|
| **组织管理** | 公司主体 | 多公司注册、子公司管理 | ✅ Company模型有name/industry/address | 无差距 |
| | 员工管理 | 员工档案、入职/离职、合同 | ✅ Employee含档案+合同+社保字段 | 无差距 |
| | 组织架构 | 部门、岗位、汇报线 | ⚠️ 无独立部门/岗位模型 | 中 |
| | 用户权限 | RBAC角色、细粒度权限 | ⚠️ Role/Permission存在但无company_id | 低 |
| **客户管理CRM** | 客户档案 | 客户信息、来源、标签 | ✅ Client+ClientSource | 无差距 |
| | 联系人 | 多人、多联系方式 | ✅ Contact | 无差距 |
| | 销售机会 | 商机阶段、概率、加权金额 | ✅ Opportunity+Pipeline漏斗 | 无差距 |
| | 合同管理 | 合同起草、变更、终止 | ✅ Contract+ContractChangeLog | 无差距 |
| | 跟进记录 | 每次跟进历史 | ✅ FollowUpRecord | 无差距 |
| | 回款计划 | 分期回款跟踪 | ✅ PaymentPlan | 无差距 |
| **采购管理** | 供应商档案 | 供应商信息、评级 | ✅ Supplier | 无差距 |
| | 采购申请 | 需求提出、审批 | ✅ PurchaseRequest | 无差距 |
| | 采购订单 | 订单下达、状态跟踪 | ✅ PurchaseOrder | 无差距 |
| | 到货入库 | 收货、入库登记 | ✅ PurchaseReceive | 无差距 |
| | 采购统计 | 汇总、周期性统计 | ✅ summary API已接入 | 无差距 |
| **财务管理** | 收入记账 | 多种收入类型 | ✅ Income | 无差距 |
| | 支出记账 | 多种支出类型 | ✅ Expense | 无差距 |
| | 发票管理 | 发票开具、匹配 | ✅ Invoice | 无差距 |
| | 工资管理 | 月度工资单、个税 | ✅ WageRecord（42字段完整） | 无差距 |
| | 银行流水 | 对账单导入、自动匹配 | ✅ BankStatement+BankAccount | 无差距 |
| | 社保公积金 | 增员减员、月度申报 | ✅ CompanySocialConfig | 无差距 |
| **仓储物料** | 物料档案 | 物料主数据、分类 | ⚠️ 物料有分类和BOM，但无company_id | **高** |
| | BOM配方 | 多层物料清单 | ✅ MaterialBOM+MaterialBOMNode | 无差距 |
| | 设备档案 | 设备台账、保养计划 | ⚠️ 设备有档案，但无company_id | **高** |
| | 设备BOM | 设备配件关联 | ✅ EquipmentBOMRelation | 无差距 |
| | 库存台账 | 实时库存数量 | ❌ **缺失库存台账模型** | **高** |
| **项目管理** | 项目立项 | 项目信息、类型 | ✅ Project | 无差距 |
| | 任务分解 | WBS任务、甘特图 | ✅ Task+甘特图 | 无差距 |
| | 阶段管理 | 里程碑、阶段进度 | ✅ StageActivity | 无差距 |
| | 项目审批 | 项目相关审批流 | ⚠️ ApprovalFlow无company_id | **中** |
| **设备维修** | 报修登记 | 故障描述、优先级 | ✅ RepairRequest | 无差距 |
| | 维修记录 | 维修过程、备件 | ✅ RepairSparePart | 无差距 |
| | 设备运行日志 | 使用记录 | ✅ EquipmentUsageLog | 无差距 |
| **审批流引擎** | 审批模板 | 可视化/配置化模板 | ✅ ApprovalTemplate | 无差距 |
| | 审批节点 | 多级、会签、或签 | ✅ ApprovalNode | 无差距 |
| | 审批实例 | 运行时审批流 | ✅ ApprovalFlow | 无差距 |
| | 抄送通知 | 审批结果知会 | ✅ 站内通知+signal | 无差距 |
| **驾驶舱** | 经营仪表盘 | 多模块汇总看板 | ⚠️ 页面完整但数据全空 | **高** |
| | 统计图表 | 可视化趋势图 | ⚠️ 图表框架完整但无数据 | **高** |
| **系统管理** | 通知渠道 | 邮件/飞书/企微/钉钉 | ✅ NotificationChannel+插件架构 | 无差距 |
| | 审计日志 | 操作轨迹可追溯 | ✅ OperationAuditLog（已有多租户） | 无差距 |
| | 登录日志 | 登录历史、IP | ⚠️ LoginLog无company_id | 低 |
| | 系统配置 | 全局参数配置 | ✅ SystemSetting | 无差距 |
| **文件管理** | 文件上传 | 多类型附件 | ✅ CompanyFile+FileCategory | ⚠️ FileCategory无company_id |
| **消息通知** | 站内通知 | 系统消息 | ✅ Notification+Signal | 无差距 |
| | 通知日志 | 推送记录 | ⚠️ NotificationLog无company_id | 低 |

---

## 三、补充需求详细清单

### 3.1 P0 — 阻断性问题（商业化必须修复）

#### P0-A：大量业务表缺失 company_id（多租户隔离系统性漏洞）

**影响范围**：61个模型中，至少 **27个业务表** 缺失 `company_id`，占业务表总量约44%。

**根因**：历史开发中部分模型遗漏了 `company_id` FK，导致多租户隔离体系不完整。用户在 UI 上虽然被限制在公司范围内，但通过 API 可以直接跨公司访问数据。

**缺失 company_id 的模型清单**（按影响程度排序）：

| 优先级 | 模型 | 说明 | 当前是否有company |
|--------|------|------|-----------------|
| **P0-A1** | `finance.company` | 公司主体表是公司数据之锚 | ❌ 无（company_id在别处引用它） |
| **P0-A2** | `equipment.equipment` | 设备台账 | ❌ 无 |
| **P0-A3** | `equipment.equipmentrepairlog` | 设备维修记录 | ❌ 无 |
| **P0-A4** | `equipment.equipmentusagelog` | 设备使用日志 | ❌ 无 |
| **P0-A5** | `equipment.equipmentbomrelation` | 设备BOM关系表 | ❌ 无 |
| **P0-A6** | `material.material` | 物料主数据 | ❌ 无 |
| **P0-A7** | `material.materialbom` | 物料BOM | ❌ 无 |
| **P0-A8** | `material.materialbomnode` | BOM树节点 | ❌ 无 |
| **P0-A9** | `material.materialcategory` | 物料分类 | ❌ 无 |
| **P0-A10** | `material.materialusagelog` | 物料使用日志 | ❌ 无 |
| **P0-A11** | `approvals.approvalflow` | 审批流实例 | ❌ 无 |
| **P0-A12** | `approvals.approvalnode` | 审批节点 | ❌ 无 |
| **P0-A13** | `approvals.approvaltemplate` | 审批模板 | ❌ 无 |
| **P0-A14** | `tasks.task` | 任务 | ❌ 无 |
| **P0-A15** | `tasks.stageactivity` | 阶段活动 | ❌ 无 |
| **P0-A16** | `tasks.taskflowinstance` | 任务流实例 | ❌ 无 |
| **P0-A17** | `tasks.taskstageinstance` | 任务阶段实例 | ❌ 无 |
| **P0-A18** | `tasks.flowtemplate` | 任务流模板 | ❌ 无 |
| **P0-A19** | `tasks.flownodetemplate` | 任务节点模板 | ❌ 无 |
| **P0-A20** | `tasks.flowtransition` | 任务流转 | ❌ 无 |
| **P0-A21** | `tasks.taskattachment` | 任务附件 | ❌ 无 |
| **P0-A22** | `tasks.taskcomment` | 任务评论 | ❌ 无 |
| **P0-A23** | `tasks.taskdependency` | 任务依赖 | ❌ 无 |
| **P0-A24** | `purchasing.purchaseorderitem` | 采购订单明细 | ❌ 无（订单有，明细无） |
| **P0-A25** | `purchasing.purchasereceive` | 采购收货单 | ❌ 无（外层有company，子表无） |
| **P0-A26** | `purchasing.purchasereceiveitem` | 采购收货明细 | ❌ 无 |
| **P0-A27** | `crm.contractchangelog` | 合同变更日志 | ❌ 无（合同有，变更无） |
| **P0-A28** | `crm.paymentplan` | 回款计划 | ❌ 无 |
| **P0-A29** | `core.permissionauditlog` | 权限变更日志 | ❌ 无 |
| **P0-A30** | `core.loginlog` | 登录日志 | ❌ 无 |
| **P0-A31** | `notifications.notificationlog` | 通知日志 | ❌ 无 |
| **P0-A32** | `files.filecategory` | 文件分类 | ❌ 无 |
| **P0-A33** | `approvals.approvalchangelog`（如存在） | 审批变更日志 | ❌ 无 |

> **注**：`core.operationauditlog` 已在 P2.5 中修复，已有 `company_id`。

**修复策略**：
1. **company 主体先行**：先为 `finance.company` 加 `company_id`（引用自己，实现子公司树形结构）或确认其作为租户锚定表不需要 self-company_id
2. **按业务域分批迁移**：设备物料域 → 审批流域 → 项目任务域 → 财务明细/CRM明细/系统日志
3. **关联表优先**：父子表同时加 company_id，防止数据孤岛
4. **ViewSet 过滤**：每个受影响 ViewSet 的 `get_queryset()` 都要加 `company_id` 过滤

---

#### P0-B：驾驶舱仪表盘数据空洞

**现状**：驾驶舱页面和图表框架完整，但所有模块统计卡片均为0，因为 `Finance/Project/Task/Customer/Supplier/Contract` 等 ViewSet 的 `get_queryset()` 历史上注释掉了 `company_id` 过滤（已修复），但当时可能修复不完整。

**根因**：根据历史 commit `97fb19b`，Finance/Employee/Tasks 的多租户隔离被移除了，当前修复状态需要验证是否回恢复了正确的过滤逻辑。

**影响**：用户登录后看到驾驶舱全是空的，无法建立使用信心。

**修复方案**：全面审查所有驾驶舱依赖的 API 端点，确认 `get_queryset()` 中 `company_id` 过滤已正确恢复。

---

### 3.2 P1 — 重要功能缺失（影响业务完整性）

#### P1-A：库存台账模型缺失

**现状**：GREEN 有物料（BOM）、有采购（PurchaseReceive入库），但**没有库存台账**。

**影响**：
- 无法实时查询物料库存数量
- 采购入库后无法追踪当前库存
- 生产/维修领料后无法扣减库存
- 库存预警、最低库存提醒无法实现

**通用 ERP 应有**：库存台账（Inventory/StockLedger），记录每个物料在每个仓库的实时数量，以及每次入库/出库流水。

**建议**：评估是否需要独立的库存模块。若业务简单（来料直接使用），当前采购收货单可部分替代；若需要精细管理，需新增 `InventoryLedger` + `InventoryTransaction`（入库/出库/调拨/盘点）模型。

---

#### P1-B：审批流无 company_id（公司可互用审批模板）

**现状**：`ApprovalTemplate` 和 `ApprovalNode` 无 `company_id`，意味着审批模板是全局共享的——A公司的审批流可以被B公司使用。

**影响**：公司间审批数据串门；无法按公司独立配置审批规则。

**修复**：为 `ApprovalTemplate` + `ApprovalNode` 加 `company_id`，并将 `ApprovalFlow` 的查询限制在本公司内。

---

#### P1-C：Task/Project 任务系统多租户隔离不完整

**现状**：`Project` 有 `company_id` ✅，但 `Task` 无 `company_id`。

**影响**：任务系统是项目管理的核心，无 company_id 意味着跨公司任务数据可见性问题。

**修复**：为 `Task` 及其所有关联表加 `company_id`，并通过 `project.company_id` 继承或直接存储实现。

---

### 3.3 P2 — 体验优化问题

#### P2-A：部门/岗位组织架构缺失

**现状**：无独立 `Department`/`Position` 模型，员工直接挂在 `Company` 下。

**影响**：无法表达部门层级、岗位汇报线；权限体系缺少"部门级"授权维度。

**说明**：若业务流程不依赖细粒度部门权限，当前无此模型不影响核心运作。

---

#### P2-B：驾驶舱统计图表数据断层

**现状**：驾驶舱图表已渲染，但 Y轴数值、ECharts 配置可能存在不匹配，导致数据展示异常。

**影响**：统计数字和图表对不上，用户体验差。

---

#### P2-C：LoginLog 无 company_id

**现状**：`LoginLog` 记录登录历史但无 `company_id`，无法按公司查询登录日志。

**影响**：审计追踪不完整；多公司环境下无法追踪特定公司的登录行为。

---

## 四、多租户隔离完整性审计结果

### 4.1 模型 company_id 覆盖情况（61个业务模型）

```
已有 company_id（17个）：✅
  core.user ✅ | core.usercompanyrole ✅ | core.operationauditlog ✅
  crm.client ✅ | crm.supplier ✅ | crm.contact ✅ | crm.contract ✅
  crm.opportunity ✅ | crm.followuprecord ✅ | crm.clientsource ✅
  finance.employee ✅ | finance.employeecompany ✅
  finance.income ✅ | finance.expense ✅ | finance.invoice ✅
  finance.wagerecord ✅ | finance.companysocialconfig ✅
  purchasing.purchaserequest ✅ | purchasing.purchaseorder ✅
  files.companyfile ✅ | notifications.notificationchannel ✅
  notifications.notifyapp ✅ | repair.repairrequest ✅
  tasks.project ✅

缺失 company_id（33个）：❌
  finance.company ❌ | equipment ❌(4表) | material ❌(5表)
  approvals ❌(3表) | tasks ❌(9表) | purchasing子表 ❌(3表)
  crm子表 ❌(2表) | core日志类 ❌(3表) | files.filecategory ❌
  notifications.notificationlog ❌

无多租户必要（全局资源）：✅
  core.systemsetting | core.role | core.permission | core.rolepermission
  core.permissionauditlog | tasks.flowtemplate | tasks.flownodetemplate
  tasks.flowtransition | channels相关插件配置

多租户隔离正确（局部）：✅
  notifications.notifybinding ✅ | core.loginlog ✅（可争议）
```

### 4.2 多租户隔离风险等级

| 风险等级 | 说明 | 涉及模型数 |
|---------|------|-----------|
| 🔴 极高 | 核心业务数据无隔离，直接串门 | 12个（设备×4 + 物料×5 + 审批×3） |
| 🟠 高 | 业务主数据无隔离，统计会跨公司 | 6个（Project + Task + Purchase子表×3 + CRM子表×2） |
| 🟡 中 | 审计/日志类，影响审计追踪 | 5个 |
| 🟢 低 | 非核心业务或低频使用 | 10个 |

---

## 五、综合成熟度评估

| 维度 | 成熟度 | 说明 |
|------|--------|------|
| 多租户隔离 | 5/10 | 已修复 CRM/Finance/Purchasing/审计，但设备物料/审批/任务仍大片缺失 |
| 功能完整度 | 7/10 | 核心模块齐全，但库存台账缺失是明显空白 |
| 驾驶舱可用性 | 3/10 | 页面完整但数据全空，需系统性验证修复 |
| 数据一致性 | 7/10 | 父子表 company_id 多数未同步 |
| 审批流引擎 | 8/10 | 引擎完整，但无 company_id 隔离 |
| 审计追踪 | 7/10 | OperationAuditLog 已修复，但 LoginLog/PermissionAuditLog 仍缺失 |
| **综合** | **6.0/10** | 比 P2 修复后（8.0）低了2分，因本报告发现了更深层结构问题 |

> ⚠️ **注意**：本报告发现了 P0-A（多租户系统性漏洞）这一之前未被识别的阻断性问题，综合成熟度应回退至 **6.0/10**。这是商业化交付前必须解决的架构级问题。

---

## 六、推荐处理顺序

### 第一批（P0-A 核心堵漏，按业务域）

**优先级最高 — 设备物料域（制造企业核心）**：
1. `equipment.equipment` 加 `company_id` + ViewSet 过滤
2. `material.material` + `material.materialbom` + `material.materialbomnode` + `material.materialcategory` + `material.materialusagelog` 加 `company_id`
3. `equipment.equipmentrepairlog` + `equipment.equipmentusagelog` + `equipment.equipmentbomrelation` 加 `company_id`
4. 设备/物料列表页、详情页 API 验证

**次高 — 审批流域**：
5. `approvals.approvaltemplate` + `approvalnode` + `approvalflow` 加 `company_id`
6. 审批流创建/查询接口按公司过滤

**第三 — 项目任务域**：
7. `tasks.task` + 所有关联表加 `company_id`
8. `tasks.project` 已有时验证 `get_queryset()` 过滤正确

**第四 — 采购/CRM 父子表**：
9. `purchaseorderitem` + `purchasereceive` + `purchasereceiveitem` + `contractchangelog` + `paymentplan` 加 `company_id`

### 第二批（P0-B 驾驶舱数据验证）

10. 系统性审查所有驾驶舱 API 端点的多租户过滤逻辑
11. 验证 Finance/Employee/Tasks 的 company_id 过滤已正确恢复

### 第三批（P1 功能补全）

12. 评估是否需要库存台账模块
13. 审批流 company_id 隔离测试

### 第四批（P2 体验优化）

14. LoginLog 加 `company_id`
15. Department/Position 组织架构（低优先级）
16. 驾驶舱图表数据验证

---

## 七、补充需求汇总表

| 优先级 | 编号 | 模块 | 问题 | 涉及模型数 | 修复方式 |
|--------|------|------|------|-----------|---------|
| P0 | P0-A | 多租户 | 设备物料/审批/任务/采购子表大量缺失company_id | 27个表 | 分域迁移 |
| P0 | P0-B | 驾驶舱 | 数据空洞，需系统性验证所有API多租户过滤 | 全局 | 审查+验证 |
| P1 | P1-A | 仓储 | 库存台账模型缺失 | — | 新建模 |
| P1 | P1-B | 审批 | ApprovalTemplate/Node/Flow无company_id | 3个表 | 迁移+过滤 |
| P1 | P1-C | 任务 | Task及关联表无company_id | 9个表 | 迁移+过滤 |
| P2 | P2-A | 组织 | 部门/岗位模型缺失 | — | 评估后决策 |
| P2 | P2-B | 驾驶舱 | 图表数据与数字不匹配 | — | 图表调优 |
| P2 | P2-C | 审计 | LoginLog无company_id | 1个表 | 迁移 |

---

## 八、变更日志

| 日期 | 版本 | 变更内容 |
|------|------|----------|
| 2026-05-06 | v1 | 初版发布：P0×5 + P1×7 + P2×5（基于 commit 6702be2） |
| 2026-05-06 | v2 | P0全部修复（commit `97fb19b`），P1全部修复（commit `a8b8558`） |
| 2026-05-06 | v3 | P2全部修复（commit `50e58d4`/`67adf0e`），综合成熟度8.0/10 |
| 2026-05-06 | v4 | **本版**：全面功能审计发现P0-A多租户系统性漏洞，综合成熟度6.0/10 |

---

*文档版本：2026-05-06-v4，基于 commit `bf375d6`*