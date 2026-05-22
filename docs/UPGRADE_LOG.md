# 升级日志
**更新时间：** 2026-05-22

---

## 2026-05-22 权限系统大修（v2.2.0）

### 问题概述

全系统两套权限系统并存：旧系统（RoleRequired，真正在校验）vs 新系统（ModulePermission，写了但从未调用）。加上 inference 引擎三缺陷，导致权限判断混乱。

### 修复内容

| 类别 | 操作 |
|------|------|
| 删除废弃 app | `permission_registry` 从 INSTALLED_APPS + 代码库彻底移除 |
| Inference 引擎重写 | 新增 VIEW_CATEGORY_MAP，解决特殊命名映射（core→system、bankaccount→bank等） |
| init_rbac 补全 | 权限矩阵从 60 条扩充到 172 条，覆盖所有声明的 action_perms |
| 语法错误修复 | `finance/views.py` EmployeeViewSet + BankAccountViewSet 补回 `action_perms =` 关键字 |
| 特殊命名修复 | `purchasing:purchase_receive` → `receive`（代码与 DB 命名一致） |
| liubc 角色清理 | 删除错误的 admin UserRole，分配正确的 staff UserRole |
| channels 视图修复 | `request.company_id` → `request.auth_company.id`（4个 view） |
| 字段迁移 | `UserCompanyRole.is_primary` 新增（core.0016 migration） |

### 验证结果（liubc/staff 角色）

| 页面 | 结果 |
|------|------|
| 收支管理（无权限） | 显示"网络错误"友好提示 ✅ |
| CRM客户（有权限） | 页面正常 ✅ |
| 审批管理（有权限） | 列表+操作按钮正常 ✅ |
| 通知渠道配置（有权限） | 全部4个tab正常 ✅ |
| 点"批准"（无权限） | 后端返回 403 ✅ |
| 审批对话框 | 弹出但后端正确拦截 ✅ |

### 相关提交

| Commit | 内容 |
|--------|------|
| 32a5537 | fix(permissions): inference engine + init_rbac full coverage |
| 4955b11 | docs: 补充两套系统关系图+后续三次修复记录 |

### 详细报告
**关联文档：**
- `docs/PERMISSION_SYSTEM_FIX_RECORD_2026-05-22.md` — 根因分析 + 修复过程详细记录
- `docs/PERMISSION_SYSTEM_SPEC.md` — v2.0 含公司级矩阵权限完整设计方案（待实施）

---

## 一、本次升级内容（2026-05-05）

### 1. 依赖版本升级

| 组件 | 升级前 | 升级后 | 说明 |
|------|--------|--------|------|
| gunicorn | 25.3.0 | 26.0.0 | 性能和稳定性改进 |
| Django | 生产环境 5.2.13（约束仅 <5.0） | 约束升级为 <6.0 | 解除版本约束不一致 |
| DRF | 3.17.1 | 3.17.1（已是最新） | requirements.txt 约束 >=3.14 兼容 |

### 2. Git 里程碑创建

| 标签 | 分支 | Commit | 说明 |
|------|------|--------|------|
| v2.1.0-commercial-ready | master | 72a41d4 | 商业化就绪版 |
| v2.0.0-standalone | standalone | 46c1392 | 独立用户版 |

### 3. 策略文档创建

- 新增 `docs/strategy/2026-05-05-knowledge-base-analysis.md` — 知识库分析与发展规划

---

## 二、43服务器验证结果

**验证时间：** 2026-05-05
**服务状态：** gunicorn 26.0.0 ✅ 正常运行
**验证方式：** 浏览器逐页验证（已登录 admin 账号）

### 页面验证清单

| # | 页面 | URL | 状态 | 备注 |
|---|------|-----|------|------|
| 1 | 控制台/Dashboard | /dashboard/ | ✅ 正常 | 显示项目/任务/审批/工资统计 |
| 2 | 设备管理 | /equipment/ | ✅ 正常 | 7台设备，分类筛选正常 |
| 3 | 设备BOM | /equipment/bom/ | ✅ 正常 | 设备配件管理页面加载 |
| 4 | 物料管理 | /materials/ | ✅ 正常 | 9种物料，库存/预警正常 |
| 5 | 审批管理 | /approvals/ | ✅ 正常 | 5条审批记录，显示待我审批4条 |
| 6 | 工资管理 | /finance/wages/ | ✅ 正常 | 显示刘柏春工资记录，筛选正常 |
| 7 | 合同管理 | /crm/contracts/ | ✅ 正常 | 12条合同，客户/供应商列表正常 |
| 8 | 用户管理 | /system/users/ | ✅ 正常 | 15个用户，含待审批5人 |
| 9 | 系统参数 | /system/settings/ | ✅ 正常 | Tab切换（系统参数/公司信息） |
| 10 | 预警中心 | /warnings/ | ✅ 正常 | 显示8条未读预警 |
| 11 | 通知消息 | /notifications/ | ✅ 正常 | 全部已读状态 |
| 12 | API文档 | /api/docs/ | ⚠️ 加载慢 | 页面可访问，完整度待查 |
| 13 | 合同管理（旧路径） | /finance/contracts/ | ❌ 404 | 正确路径为 /crm/contracts/ |
| 14 | 用户管理（旧路径） | /core/users/ | ❌ 404 | 正确路径为 /system/users/ |
| 15 | 用户管理（旧路径） | /users/ | ❌ 404 | 正确路径为 /system/users/ |
| 16 | 设备BOM（错误路径） | /equipment/boms/ | ❌ 404 | 正确路径为 /equipment/bom/ |
| 17 | 设备BOM（错误路径） | /projects/equipment-boms/ | ❌ 404 | 正确路径为 /equipment/bom/ |
| 18 | 通知渠道（旧路径） | /notifications/channels/ | ❌ 404 | 正确路径为 /system/notification-channels/ |
| 19 | 通知渠道（旧路径） | /channels/ | ❌ 404 | 正确路径为 /system/notification-channels/ |

### 遗留问题

| 问题 | 路径 | 说明 |
|------|------|------|
| ~~通知渠道404~~ | ~~/notifications/channels/~~ | ✅ 已修复（301→/system/notification-channels/）|
| ~~旧路径残留~~ | ~~/finance/contracts/~~ | ✅ 已修复（301→/crm/contracts/）|
| ~~旧路径残留~~ | ~~/core/users/~~ | ✅ 已修复（301→/system/users/）|
| ~~旧路径残留~~ | ~~/users/~~ | ✅ 已修复（301→/system/users/）|
| ~~错误路径~~ | ~~/equipment/boms/~~ | ✅ 已修复（301→/equipment/bom/）|
| ~~错误路径~~ | ~~/projects/equipment-boms/~~ | ✅ 已修复（301→/equipment/bom/）|

## 三、124服务器（standalone）同步完成

**同步时间：** 2026-05-05
**服务状态：** gunicorn 26.0.0 ✅ systemd service正常运行 ✅
**部署分支：** standalone → origin/standalone

### 合并内容

| 类型 | 说明 |
|------|------|
| master→standalone合并 | 40个文件合入，standalone rebased后push |
| 迁移链重建 | notifications/material/equipment三个app迁移链历史冲突解决 |
| BOM表手动创建 | material_bom、material_bom_node、equipment_bom_relation表手动重建 |
| gunicorn升级 | 25.3.0 → 26.0.0 |
| 旧路径重定向 | 6条301规则随master合并同步到standalone |
| core_system_setting sequence修复 | setval到max(id)解决0012种子数据PK冲突 |

### 124服务器页面验证

| # | 页面 | URL | 状态 |
|---|------|-----|------|
| 1 | 控制台 | / | ✅ 200 |
| 2 | 用户管理 | /system/users/ | ✅ 200 |
| 3 | 合同管理 | /crm/contracts/ | ✅ 200 |
| 4 | 设备管理 | /equipment/ | ✅ 200 |
| 5 | 物料BOM | /material/bom/ | ✅ 200 |
| 6 | 设备BOM | /equipment/bom/ | ✅ 200 |
| 7 | 项目管理 | /projects/ | ✅ 200 |
| 8 | 通知消息 | /notifications/ | ✅ 200 |
| 9 | 审批管理 | /approvals/ | ✅ 200 |
| 10 | 合同管理（旧路径） | /finance/contracts/ | ✅ 301→200 |
| 11 | 用户管理（旧路径） | /users/ | ✅ 301→200 |
| 12 | 设备BOM（旧路径） | /equipment/boms/ | ✅ 301→200 |

### 124服务器systemd服务

- 服务名：`engineering-gunicorn.service`
- 状态：`active (running)`，开机自启 `enabled`
- 进程：4 workers，port 8001，gunicorn 26.0.0

---

## 四、Git里程碑

| 标签 | 分支 | Commit | 说明 |
|------|------|--------|------|
| v2.0.0-standalone | standalone | 46c1392 | 独立用户版 |
| v2.1.0-commercial-ready | master | 72a41d4 | 商业化就绪版 |
| v2.1.1-commercial-ready-hotfix | master | e56f5cd | gunicorn 26升级+6条旧路径重定向 |
| v2.1.1-commercial-ready-hotfix | standalone | 4ffdef1 | 迁移链重建+BOM表+gunicorn升级+重定向 |

---

## 五、升级注意事项

1. **Django 版本约束**：生产环境已运行 Django 5.2.13，requirements.txt 约束已更新为 <6.0
2. **gunicorn 26.0.0** 需要 systemd restart 才生效（已在43服务器执行）
3. **通知渠道页面**导航链接指向404，需要在代码中找到正确的路由并修复
4. **历史URL残留**不影响功能，但建议在后续清理中做重定向
5. **standalone迁移链**：material/equipment两个app的BOM相关迁移曾被删除并手动重建，确保数据库表结构与model定义一致
6. **NotifyBinding.notify_app**：standalone分支该字段已改为nullable，master分支如有合入需求需同步该改动

---

*本文件记录每次升级的完整信息，便于追溯和问题回滚。*
