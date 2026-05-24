# 项目路线图 / 需求规划

> 记录已完成的架构决策和待实现的需求分析。按优先级和模块分类。

---

## 一、已完成的架构决策（ADR）

### ✅ ADR-007：权限体系改造（2026-05-21）— ⚠️ 已废弃

**决策**：新建 `apps/permission_registry` 独立模块，实现多公司×五档权限体系。

**核心内容**：
- 超管（is_superuser=True）= 老板本人，全局通行
- 普通用户 = 身份标签取自 Employee.role_title
- 权限体系：用户×公司×模块，五档独立（view/create/edit/delete/approve）
- 每个用户在每个公司有且仅有一个主体企业（is_primary=True）
- 模块自注册：`@register_module` + post_migrate 信号

**状态**：❌ **2026-05-22 废弃** — Phase3 permission_registry 与 Phase2 UCP 冲突，v2.2.1 当天决定彻底删除。详见 `PERMISSION_REGISTRY_REQUIREMENTS.md` 第五节「废弃原因与替代方案」。

> 替代方案：Phase2 UCP（RoleRequired + UserCompanyPermission）已完全覆盖需求，修复后正常运行于 43/124/129 三台服务器。

---

### ✅ ADR-006：通知系统架构（2026-05-19）
**决策**：多渠道（飞书/企微/钉钉/微信/QQ/短信/邮件/Telegram）× 个人IM+广播双模式，扩展插件化。

**状态**：✅ 已完成

---

## 二、待实现的优先级需求

### P0 — 当前阻塞问题

#### P0-1：Leyan 用户多公司数据可见性
**问题**：124 服务器上 Leyan 只关联了 company=1，但按权限设计应该能看到 company=2。

**原因**：UserCompanyRole 表只有 company=1 的记录。

**解决方案**：
- 方案A（业务层）：让系统支持用户主动申请关联新公司，由管理员审批
- 方案B（管理后台）：管理员在后台手动为用户添加关联公司
- 方案C（数据修复）：确认 Leyan 是否真的需要管两家公司，如需要则补充 UserCompanyRole 记录

**责任人**：待确认业务需求

---

#### P0-2：前端多公司切换器
**问题**：用户当前无法在前端切换当前操作的公司上下文。

**现状**：所有下拉框只显示公司列表，但"当前公司"上下文由后端 `_get_user_company_id()` 决定，用户无感知。

**解决方案**：
- 在页头/侧边栏添加"当前公司"切换器
- 切换后通过 cookie 或 localStorage 记住选择
- 后端 `get_active_company_id()` 优先读 cookie，未设置则读 `is_primary=True`

---

### P1 — 核心功能补全

#### P1-1：权限检查真正落地
**状态**：❌ **已废弃（2026-05-22）** — Phase3 permission_registry 已删除，Phase2 UCP 已完全覆盖需求。

> 原计划用 ModulePermission 替换 RoleRequired，但 ModulePermission 从未被实际调用。v2.2.1 修复当日确认 Phase2 UCP（RoleRequired + UserCompanyPermission）已能正确处理所有权限场景，P1-1 无需执行。

---

#### P1-2：员工管理模块权限
**问题**：`EmployeeViewSet` 的 `get_queryset` 是否已经用了 `get_user_companies`？

**待确认**：需要检查 `EmployeeViewSet` 的 `get_queryset` 是否也已改为 `company_id__in` 多公司过滤。

---

#### P1-3：UserCompanyRole 表废弃计划
**状态**：✅ **已完成（2026-05-22）** — `UserCompanyRole` 表已废弃，数据已迁移到 `UserCompanyPermission`。

> 原计划分三阶段执行，实际在 v2.2.1 权限系统修复当日一次性完成：底层查询从 `UserCompanyRole` 改为 `UserCompanyPermission`，`UserCompanyRole` 表保留但已无业务代码调用。

---

### P2 — 体验优化

#### P2-1：个人工作台 / Dashboard
**需求**：登录后显示个人工作台，展示：
- 待处理审批数量（按权限过滤）
- 本月收入/支出汇总
- 即将到期的事项
- 公司切换快捷入口

**实现思路**：新建 `dashboard` app 或在 `core` 中添加 DashboardViewSet

---

#### P2-2：审批流程自定义
**现状**：当前审批是固定流程（提交→审批人审批）。

**需求**：
- 支持多级审批（一级审批、二级审批）
- 支持会签（多人同时审批，全部通过才过）
- 支持或签（任一人审批即可）
- 审批节点可配置（哪些模块需要审批？哪些操作需要审批？）

---

#### P2-3：银行流水自动归类
**现状**：银行流水导入后，需要手动匹配收支记录。

**需求**：
- 根据金额+日期自动推荐匹配的 Income/Expense 记录
- 未匹配记录进入"待归类"队列
- 支持批量确认归类

---

#### P2-4：财务报表增强
**需求**：
- 利润率分析（按项目/按客户/按时间段）
- 现金流预测
- 预算执行追踪（实际 vs 预算）
- 发票汇总报表（按税号/按日期/按发票状态）

---

### P3 — 长期规划

#### P3-1：多租户隔离（不紧急）
**背景**：有客户问"这套系统能不能部署成多套，互不干扰"。

**现状**：当前是"一套代码+一套数据库"架构，通过 `company_id` 隔离数据。

**需求**：
- 方案A：继续保持单库多公司架构（当前方案），加强 `company_id` 过滤
- 方案B：支持 Schema 隔离（PostgreSQL schema per tenant）
- 方案C：支持完全独立部署（每客户一套代码库）

**决策**：当前阶段不需要多租户，先做好多公司支持再说。

---

#### P3-2：移动端支持
**需求**：手机端查看审批、处理日报、查看报表。

**现状**：当前系统无移动端页面，只有响应式基础支持。

**实现思路**：
- 方案A：PWA 改造（Progressive Web App）
- 方案B：单独开发小程序（飞书小程序/微信小程序）
- 方案C：React Native / Flutter 独立 APP

---

#### P3-3：开放 API（对外集成）
**需求**：为第三方系统提供标准 REST API（webhook / OAuth2）。

**现状**：当前 API 仅内部使用（session 认证）。

**实现思路**：
- Token 认证（OAuth2 client_credentials）
- API 版本管理（/api/v1/ / /api/v2/）
- 限流（rate limiting）
- API 使用统计和计费

---

## 三、模块自注册扩展计划

**现状**：`finance` 模块已实现 `@register_module` 自注册。

**待完成**：
- `apps.tasks` 注册 tasks 模块
- `apps.crm` 注册 crm 模块
- `apps.approvals` 注册 approval_flow 模块
- `apps.notifications` 注册 notification 模块

**规范**：每个 app 的 `modules.py` 声明该 app 包含哪些模块，`post_migrate` 信号自动同步到 DB。

---

## 四、技术债务

| 编号 | 描述 | 优先级 | 预计工时 |
|------|------|--------|---------|
| TD-1 | `settings.py` / `settings_pg.py` / `settings_sqlite.py` 三配置同步规范 | P1 | 1h |
| TD-2 | `preload_app=True` 移除（gunicorn 配置） | P1 | 0.5h |
| TD-3 | `UserCompanyRole` 表废弃并迁移数据 | P2 | 2h |
| TD-4 | 所有 ViewSet 权限类统一为 `ModulePermission` | P2 | 3h |
| TD-5 | 旧 `core/permissions.py`（RoleRequired）清理 | P3 | 1h |
| TD-6 | 旧 `module_registry.py`（遗留代码）清理 | P3 | 0.5h |
