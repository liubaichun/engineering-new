# GREEN ERP 全系统深度摸底报告
**日期：** 2026-06-02
**摸底范围：** 43台 `/root/engineering-new/apps/` 下13个app，全部models/views/urls，交叉引用报告文档

---

## 一、已发现但被B001分析低估/漏掉的问题

### ⚠️ P0 — Expense模型有两个日期字段（数据不一致）
**位置：** `apps/finance/models_expense.py`
**问题：** `expense_date` 和 `date` 两个字段共存，`save()` 里互相同步。技术债。
- Income只有 `date`
- Expense多一个 `expense_date`，还留了一个兼容 `date`
- 序列化器/模板可能混用，数据同步不可靠

### ⚠️ P0 — Income有"已到账"，Expense无"已付款"
**问题：** Income状态有 `received`（已到账），Expense状态只到 `confirmed`（已确认支出），没有 `paid`。**不对称。** 做应收应付闭环的话两边状态机必须对齐。

### 🔴 P1 — equipment.bak 和 permission_registry 死代码残留
**位置：**
- `apps/equipment.bak.20260601065724/` — 整个目录备份，还带着 `modules.py`
- `apps/permission_registry/templates/` — 旧权限系统的模板残留
B001之前被用户批评过"系统只需要一套"，但仍然有死代码。`permission_registry` 在 `INSTALLED_APPS` 移除了但文件夹还在。

### 🔴 P1 — Notification app是空壳
**位置：** `apps/notifications/`
**问题：** `models/` 目录下只有 `__init__.py`，没有模型。`core/models.py` 里的 `Notification` 模型是消息通知，但 `notifications` 这个app里实际是通知渠道（企微/飞书/钉钉）。通知渠道的配置模型在 `channels/` 里。**命名混乱：** `notifications` ≠ `channels`。

### 🟡 P2 — 发票与合同/CRM无关联
**位置：** `apps/finance/models_invoice.py`
**问题：** Invoice的 `counterparty` 是纯文本，没有关联到CRM的 Client/Supplier。`project` 有外键但 `contract` 没有。

### 🟡 P2 — 物料入库有PurchaseReceive，但没有通用入库日志
**位置：** `apps/material/models.py`
**问题：** `MaterialUsageLog` 只记录出库。入库只在采购模块里有 `PurchaseReceive`，但没有通用的 `MaterialInboundLog`。

### 🟡 P2 — 所有编码规则硬编码在模型的 `save()` 里
**位置：** Material/Equipment/Client/Supplier 等所有模型的 `save()` 方法
**问题：** 每家公司的编码规则（前缀、年份格式、自增位数）全是代码写死的。

---

## 二、B001分析中正确的点（验证后确认）

| 项目 | 状态 | 补充说明 |
|------|------|---------|
| 应收/应付闭环 | ⚠️ 半成品 | ARAPViewSet已有但只查Invoice |
| 库存流水化 | ⚠️ 半成品 | MaterialUsageLog只出库不入库 |
| 认证证书管理 | ❌ 完全缺失 | 模型/视图/模板全无 |
| 编码规则可配置 | ❌ 完全缺失 | 所有编码硬编码 |
| 行级数据权限 | ⚠️ 公司级有 | 公司级权限隔离已做(v6) |
| 商机管理 | ⚠️ 有但薄弱 | 缺少销售漏斗视图和预测 |

---

## 三、新发现的技术债务

### P0级
1. **Expense模型双日期字段** — `expense_date` 和 `date` 共存
2. **Income/Expense状态机不对称** — Income有`received`，Expense只有`confirmed`没`paid`
3. **Expense save()潜在崩溃bug** — `hasattr(self.expense_date, 'date')` 当expense_date为字符串时会崩溃

### P1级
4. **equipment.bak死代码** — 整个目录备份
5. **permission_registry死代码** — templates目录残留
6. **notifications vs channels 命名混乱** — 两个app功能边界不清

### P2级
7. **Invoice无contract关联** — 应收应付闭环的硬伤
8. **Material无通用入库日志** — 出库有log，入库没有
9. **编码规则重复代码** — 5个模型的save()都在写同样的自动编号逻辑

---

## 四、执行路线

### 第0周（3天）：清理死代码 + 修状态机不对称
1. 删除 equipment.bak
2. 删除 permission_registry 残留
3. 统一 Income/Expense 状态机
4. 修复 Expense 双日期字段
5. 明确 notifications vs channels 边界

### 第1-2周：应收应付闭环
- 打通 Invoice → Contract → PaymentPlan 关联
- 对接 BankStatement 到 Invoice/Contract 核销
- 账龄分析（30/60/90+天分组）
- 到期提醒通知

### 第3周：库存流水化 + 编码规则
- 建 MaterialInboundLog 模型
- stock 改为计算字段
- 编码规则抽成可配置

### 第4周：认证证书管理（全新）
