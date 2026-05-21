# 项目更新日志

> 记录每日 Bug 修复、功能迭代、架构调整。格式：日期 / 模块 / 问题 / 根因 / 解决方案

---

## 2026-05-21

### 🔴 严重：权限模块未注册导致全局数据异常

**涉及模块**：系统全局（config/settings.py）

**问题描述**：
- 员工管理"加载失败"
- 收支管理全部公司筛选无下拉框
- 发票管理不显示发票数据
- 这些问题在 124 服务器上集中出现

**根因**：`config/settings.py`（生产环境配置）未注册 `apps.permission_registry`，而 `config/settings_pg.py`（本地开发配置）有。该疏漏导致：
1. `Module` / `ModulePermission` / `UserCompanyPermission` 模型虽已创建，但 Django 未加载该 app
2. 所有 ViewSet 的 `get_queryset` 走的是旧的 `company_id` 单值过滤（`company_id=cid`），多公司用户只能看到第一个公司的数据
3. `finance/views.py` 的 `get_user_companies()` 函数虽然已实现，但从未被调用（因为模块未注册时可能引发 import 错误）
4. 旧的 `core.permissions.RoleRequired` 权限检查从未真正生效（Permission 表一直为空）

**解决方案**：
1. `config/settings.py` 添加 `'apps.permission_registry'` 到 `INSTALLED_APPS`（位于 `'apps.core'` 之后）
2. 同步到 124 服务器执行 `sed` 修复
3. 重启 gunicorn：`pkill -9 gunicorn && gunicorn config.wsgi:application ... --daemon`
4. 执行 `migrate_user_permissions` 同步权限数据

**涉及文件**：
- `config/settings.py`（+1 行）
- 124 服务器：`/home/ubuntu/engineering-new/config/settings.py`

**教训**：所有配置文件（settings.py / settings_pg.py / settings_sqlite.py）必须同步修改，特别是 `INSTALLED_APPS` 这种全局项。后续新增 app 必须在所有配置文件同步添加。

---

## 2026-05-21

### 🔴 阶段1-3：多公司权限体系改造

**涉及模块**：`apps.permission_registry`（新建）、`apps.finance`

**改造内容**：

#### 阶段1：基础设施搭建
- 新建 `apps/permission_registry` 模块（独立可复用）
- 模型：`Module`（模块注册）/ `ModulePermission`（权限定义）/ `UserCompanyPermission`（用户×公司×模块权限）
- `@register_module` 装饰器实现模块自注册（import 时安全）
- `post_migrate` 信号实现数据库幂等同步（表创建后才写 DB，避免"先有鸡先有蛋"）
- 9个财务模块注册：income / expense / invoice / wage / report / bank / company / employee / approval
- 每模块标准五档权限：can_view / can_create / can_edit / can_delete / can_approve

#### 阶段2：历史权限迁移
- `migrate_user_permissions` 命令：admin×4公司→五档全开；staff×1公司→view+create
- 幂等处理：已存在记录跳过，`--force` 覆盖
- 迁移结果：216条（admin 180条 + staff 36条）

#### 阶段3：多公司数据修复
- 重写 `finance/views.py` 的 `_get_user_company_id()` → `get_user_companies()`
- 所有 ViewSet 的 `get_queryset`：`company_id=cid` → `company_id__in=cids`
- `IncomeViewSet` / `ExpenseViewSet` / `InvoiceViewSet` / `WageViewSet` 全部更新
- 报表视图（monthly/quarterly/yearly）：改为 `company_id__in` 遍历多公司
- `channels/services.py`：改用 `get_active_company_id()`

**教训**：
- `preload_app=True` 导致 HUP reload 不生效，修改模板后必须 `pkill -9 gunicorn` 再重新启动
- Django shell 通过 ≠ HTTP 服务生效（shell 不经过 gunicorn preload）

---

## 2026-05-19

### 🟡 任务创建 400 错误

**涉及模块**：`apps.tasks`

**根因**：`TaskCreateSerializer` 的 `assignee` 字段是隐式 `PrimaryKeyRelatedField`（只接受 int pk），前端传的是 `username` 字符串。

**解决方案**：改为 `SlugRelatedField(slug_field='username')`

**教训**：API 返回 201 ≠ 用户能看到成功（对话框还开着就是失败）。必须用视觉浏览器以用户的角度验证。

---

## 2026-05-19

### 🟡 F39/F40 报销单页面年份筛选失效

**涉及模块**：`apps.finance`（expense_list.html）

**根因**：两个独立 Bootstrap-select bug：
1. `filterYear` select 缺少 `class="selectpicker"`，导致 `loadYearOptions` 里的条件 `destroy/reinit` 被跳过
2. `DOMContentLoaded` 没有先调用 `loadYearOptions`，导致第一次导航时年份 API 还没返回 select 就有旧值

**解决方案**：
- HTML 加 `class="selectpicker"`
- `DOMContentLoaded` 加显式 `.selectpicker()` 初始化
- `loadYearOptions` 无条件 `destroy/reinit`

---

## 2026-05-19

### 🟡 通知系统 dispatch_notify 绕过了 channels 框架

**涉及模块**：`apps.notifications`

**根因**：通知派发直接调 `channel.send()` 而不是通过 `dispatch_notify()` 框架

**解决方案**：统一改为 `dispatch_notify()`，由框架决定走哪个渠道

**涉及内容**：通知渠道扩展框架搭建完成（飞书/企微/钉钉/微信/QQ/短信/邮件/Telegram），支持个人IM+广播双模式，扩展插件化。
