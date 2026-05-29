# 项目更新日志

> 记录每日 Bug 修复、功能迭代、架构调整。格式：日期 / 模块 / 问题 / 根因 / 解决方案

---

## 2026-05-21

> **⚠️ 注意**：以下 2026-05-21 当日记录的两条关于 permission_registry 的条目，已被 v2.2.1（2026-05-22）彻底废弃。Phase3 permission_registry 因与 Phase2 UCP 冲突，在 v2.2.1 当天被完全删除。详见 `PERMISSION_REGISTRY_REQUIREMENTS.md` 第五节「废弃原因与替代方案」。
>
> - 「权限模块未注册导致全局数据异常」→ 废弃（permission_registry 已删除）
> - 「RoleRequired 权限检查形同虚设」→ 废弃（Phase3 已废弃，Phase2 UCP 已完全覆盖）
> - 「阶段1-3：多公司权限体系改造」→ 废弃（Phase3 已废弃）

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

### 🔴 严重：RoleRequired 权限检查形同虚设（P1-1）

**涉及模块**：`apps.finance`

**问题描述**：
- `core.permissions.RoleRequired` 检查 `core_permission` 表，该表从创建至今一直为空
- 所有 ViewSet 的 `permission_classes = [IsAuthenticated, RoleRequired]` 从未真正执行权限过滤
- 任何登录用户都能访问任何模块（只要知道 URL）

**根因**：`RoleRequired` 的 `action_perms` 字段引用的是 `core_permission` 表的 `codename` 字段（如 `finance_invoice_read`），但该表从未写入过数据，导致 `RoleRequired.has_permission` 直接 raise 403。等等——之前的分析说它会 raise 403，但实际用户仍能访问数据，说明另一个逻辑覆盖了？实际上是因为 view 层 `get_queryset` 的公司过滤 + DRF 默认权限已经部分实现了过滤。

**解决方案**：
1. 全部11个 ViewSet 替换 `RoleRequired` → `ModulePermission`
2. 每个 ViewSet 声明 `module_name`（company/employee/income/expense/invoice/wage/report/bank）
3. `ModulePermission` 查 `UserCompanyPermission` 表，真正实现五档权限检查（超管 bypass）
4. `EmployeeViewSet.get_queryset` 从 `company_id` 单值过滤改为 `EmployeeCompany` 中间表多公司过滤

**涉及文件**：
- `apps/finance/views.py`（+34行，-17行）

**教训**：`RoleRequired` 和 `core_permission` 表从未生效，说明光有设计不够，必须有验证机制。建议后续在 admin 后台加"权限健康检查"功能。

---

## 2026-05-25（安全审计收官——三轮权限修复）

### 第三轮：导入视图+用户管理权限修复（P1×6）

**涉及模块**：`apps.crm`, `apps.finance`, `apps.equipment`, `apps.core`

| # | 问题 | 文件 | 方案 |
|---|------|------|------|
| 1 | CRM导入（客户/供应商/合同）创建记录未设company | `crm/import_views.py` | 3处加 `company=getattr(request, 'auth_company', ...)` |
| 2 | 财务导入（收入/支出）硬编码 `Company.objects.first()` | `finance/import_views.py` | 改为 `auth_company` |
| 3 | 发票导入公司来源只用 `user.company_id`，忽略选中公司 | `finance/views.py` | 优先 `auth_company` |
| 4 | 银行导入preview/confirm无公司权限校验 | `apps/equipment/bank_import_views.py` | 2处加 `UserCompanyRole` 校验 |
| 5 | 用户管理（UserViewSet）无action-level权限 | `core/views.py` | 加 `action_perms` + `RoleRequired` |
| 6 | 员工导入缺公司fallback（Excel无"所属公司"列） | `finance/import_views.py` | 加 `auth_company` 兜底 |

**涉及文件**：5个文件
**同步状态**：43服务器 ✅ 124服务器 ✅

---

## 2026-05-24（第二轮：权限越权+缺失修复）

### 修复项：P0×1 + P1×7

**涉及模块**：`apps.crm`, `apps.approvals`, `apps.finance`, `apps.equipment`, `apps.core`

| # | 类型 | 问题 | 文件 | 修复 |
|---|------|------|------|------|
| 1 | P1 | CRM合同5个动作权限越权（approve/reject/activate/complete/terminate）用了错误的权限码 | `crm/views.py:124-128` | `crm:client_source:*` → `crm:contract:*` |
| 2 | P1 | 审批流create权限 = read（`approval:flow:read`） | `approvals/views.py:97` | `read` → `create` |
| 3 | P1 | finance 5个ViewSet权限前缀都是`company:xxx` | `finance/views.py` | 逐项修正：employee/bank/social_security/employee/social_security |
| 4 | P1 | Equipment record_repair/export无权限注册 | `equipment/views.py:43-50` | 补写操作用 `equipment:device:create/read` |
| 5 | P0 | user_list.html前端权限码用旧格式 `user.add` | `templates/system/user_list.html` | 改为 `system:user:create` |
| 6 | P1 | 6个ViewSet `action_perms=` 缺失（Company/Income/Expense/WageRecord/Invoice/ARAP ViewSet） | `finance/views.py` | `{dict}`裸赋值改为 `action_perms = {...}`，这些权限定义**从未生效过** |

**涉及文件**：5个
**同步状态**：43服务器 ✅ 124服务器 ✅

---

## 2026-05-22（第一轮：敏感数据脱敏+权限加固）

### 修复项：P0敏感数据脱敏 + P1加固×3

**涉及模块**：`apps.finance`

| # | 类型 | 问题 | 方案 |
|---|------|------|------|
| 1 | P0 | 身份证号/银行卡号/手机号明文返回 | `MaskedCharField`自定义字段：写入存完整值，读取返回脱敏值（`110101****1234`） |
| 2 | P1 | 模板菜单权限码指向错误 | `base.html`: 员工管理/社保管理/银行流水3个权限码修正 |
| 3 | P1 | Serializer新建/修改时无公司归属校验 | `CompanyAccessValidatorMixin`：非超管创建/修改时校验company归属 |
| 4 | P1 | ExpenseSerializer `id`/`operator`/`created_at`可写 | 补全 `read_only_fields` |

**涉及文件**：3个
**部署状态**：43服务器 ✅ 124服务器 ✅

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

---

## 2026-05-27（财务系统分类改造）

### 一、支出分类体系重构（二次清洗）

**背景**：首次分类（other 从 640 降至 21 条）后，发现仍有 161 条"服务费/技术服务费"被误归入财务费用。

**执行动作**：

| 操作 | 涉及条数 | 结果 |
|------|:-------:|:----:|
| 服务费/技术服务费→从 finance_expense 改回 main_cost | 161条 | main_cost: 81→253条 |
| 空描述但有公司供应商→从 other 改回 main_cost | 11条 | |
| 财务费用二次清理 | -214→53条 | 仅剩银行手续费¥1,403 |
| other 二次清理 | 21→10条 | 降幅97%（640→10） |

**涉及文件**：
- `apps/finance/management/commands/reclassify_expenses.py` — 二次分类命令
- `apps/finance/management/commands/classify_expenses.py` — 支出分类命令

### 二、会计科目体系搭建

| 组件 | 说明 |
|------|------|
| `Account` 模型 | 5大类（资产/负债/权益/收入/费用），支持多级科目 |
| `FinanceAccount` 表 | 34个科目（19个一级+15个二级），参照小企业会计准则 |
| `classification_rules.py` | 收入/支出/工资/社保→科目映射函数（查询时映射，不修改原始数据） |
| `seed_accounts.py` | 科目初始化命令 |
| `check_accounting.py` | 会计校验命令（借贷平衡、跨期一致性） |

### 三、报表系统升级

| 报表 | 变更 | 状态 |
|:----|:----|:----:|
| 利润表（新增） | `income_statement_report` API，基于科目余额表层级计算 | ✅ 新增 |
| 收支汇总表 | `revenue_expense_summary`（原balance_sheet改名+逻辑修复） | ✅ 改名 |
| 内部转账排除 | 月度/年度/汇总表均加入 `exclude(internal_transfer, equity)` | ✅ 修复 |

### 四、收入分类补充

| 操作 | 金额 | 说明 |
|------|:----:|:-----|
| 生育津贴→内部往来 | ¥27,095 | 百川公司 |
| 稳岗补贴→其他收益 | ¥594 | 百川公司 |
| 金易豪李斌投资款→实收资本 | ¥20,000 | |
| 新增 `other_income` 分类 | - | 收入分类4→7个 |

### 五、关联方往来台账

| 组件 | 说明 |
|------|------|
| `RelatedPartyLedger` 模型 | 完整生命周期：借出/借入/还款，已结清/未结清 |
| `build_ledger` 命令 | 从已有 `internal_transfer` 标记反向构建台账，118条记录 |
| 台账API | 余额+明细 |
| 仪表盘 | 关联方往来卡片 |

### 当前待办

| # | 任务 | 优先级 |
|:-:|:-----|:------:|
| 1 | **10条other残留发票核实**（设备定金、百川两笔、报价单等） | 🟡 |
| 2 | **报销款拆分规则细化**（"报销款"→管理费，"差旅费报销"→差旅） | 🟡 |
| 3 | 发票关联接口 | 🟡 |
| 4 | 社保数据补全（仅1月4条，缺2-7月） | 🟢 |
| 5 | 自动分类引擎升级（多维规则） | 🟢 |

---

## 2026-05-27 社保模块改造：员工可空 + 脏数据过滤（v2.3.2）

### 一、问题

| # | 问题 | 严重程度 |
|:-:|:-----|:--------:|
| 1 | **社保导入丢失17条**：Employee表缺6人，`SocialRecord.employee` NOT NULL 报错被 try/except 吞掉 | 🔴 |
| 2 | **杨钊斌脏数据**：仅工伤¥14.09，此人从未入职，不应导入 | 🟡 |
| 3 | **分页不生效**：前端传 `offset/limit`，后端只认 `page/page_size` | 🔴 |
| 4 | **年份筛选硬编码**：写死最近12个月，选不到2024年数据 | 🔴 |

### 二、修改内容

#### 社保模块（models.py）

- `SocialRecord.employee` → 加 `null=True, blank=True`，支持无员工关联的记录
- `unique_together` → 从 `['employee', 'year_month']` 改为 `['company', 'id_card', 'year_month']`
- `__str__` → 员工为空时显示 `未知(证件尾号4位)`
- `ordering` → 从 `employee__name` 改为 `id_card`

#### 前端（social_record_list.html）

- 分页参数从 `offset/limit` 改为 `page/page_size`，匹配后端 `SafePageNumberPagination`
- 年份筛选从硬编码最近12个月改为从数据库 `DISTINCT year_month` 动态生成

#### 导入逻辑（import_social_records.py）

- 新增脏数据检测：**仅工伤>0且其他险种全部为0** → 自动跳过并计入 `skipped_dirty`
- 导入结果返回增加 `skipped_dirty` 列表，明确告知用户跳过的记录
- `employee=None` 路径不再报错

### 三、迁移（0034）

```
finance.0034_adjust_social_record_nullable_and_unique
  ~ Alter field employee on socialrecord (nullable)
  ~ Alter unique_together for socialrecord → (company, id_card, year_month)
  ~ Alter model options (ordering, verbose_name)
```

### 四、验证结果

- 60条记录全部入库（44有员工 + 16无员工）
- 杨钊斌（仅工伤¥14.09）→ 正确跳过
- 1条脏数据被过滤，0错误
- 年份筛选范围：2024-07 ~ 2026-05（数据库实际数据）
- 分页翻页正常，第2页显示24年数据
- 43 + 124 两端同步部署完成

### 五、待办更新

| # | 任务 | 状态 |
|:-:|:-----|:----:|
| 1 | ~~社保导入丢失17条~~ | ✅ 已修复 |
| 2 | ~~年份筛选硬编码~~ | ✅ 已修复 |
| 3 | ~~分页不生效~~ | ✅ 已修复 |
| 4 | **重新导入社保数据**（补全2-7月，其他三家公司） | 🟡 |
| 5 | 10条other残留发票核实 | 🟡 |
|| 6 | 报销款拆分规则细化 | 🟡 |
|

## 2026-05-28

### 发票管理模块修复（共10项）

**1. Bootstrap Tab 默认不显示数据**
- 问题：进入页面默认Tab内容空白，要点其他Tab再点回来才显示
- 根因：`list-pane-expense` 缺 `show active` 类；两个重复的DOMContentLoaded监听器
- 修复：加 `show active` 类 + 去掉重复监听器，同时修了年份下拉出两次的bug

**2. 导入弹窗缺少公司选择器**
- 问题：导入时无法选公司 → 后端 company_id=null
- 修复：公司选择器放Tabs外面，两Tab共享；后端优先读 `request.data.company_id`

**3. 筛选条件不生效（年份/状态/日期）**
- 问题：选筛选条件后列表无变化，汇总不变
- 根因：所有筛选器 onchange=`loadInvoices()` 不传参数 → `type=undefined`
- 修复：新增 `onFilterChange()` → 重置分页→刷新当前列表+两边汇总

**4. 汇总不随筛选变化**
- 问题：`loadSummary()` 只传了company_id和年份
- 修复：增加传 `status`/`dateFrom`/`dateTo`；后端summary支持status过滤

**5. 导入重复发票报错**
- 修复：预查已有发票号→跳过重复→字段白名单→错误信息带发票号

**6-7. 权限码缺失 + Filter缺日期范围**
- 修复：action_perms补create/destroy/import_records；InvoiceFilter加issue_date_min/max

|**涉及文件：** `invoice_list.html` / `views.py` / `filters.py`

---

## 2026-05-27 发票导入引擎重构（Bug修复 + 数据修复）

> **背景：** 百川软件2004年（2024年）收到发票导入后，用户发现记录数少了几十条，金额也对不上。经全面分析发现3个设计Bug。

### 发现的3个Bug

**Bug 1: Sheet选择错误（设计问题）**
- 代码优先选择「信息汇总表」（有税率列，但811行明细数据，246张多行发票需聚合）
- 应该使用「发票基础信息」（463行，一行=一张完整发票，无需聚合）
- 修复：Sheet选择逻辑改为优先找「发票基础信息」（无税率列+无明细列），次选「信息汇总表」

**Bug 2: 金额计算错误（abs()严重Bug）**
- `total_amount += abs(float(amt))` 将折扣/调整行的负值翻正，导致金额虚增
- 244/388张发票金额错误，总计多算 ¥112,205.75（35.2%）
- 修复：改为直接求和 `total_amount += float(amt)`，最终取绝对值

**Bug 3: "--"发票处理缺陷（去重逻辑错误）**
- 税局系统用 `--` 表示无电子发票号的交易（中石化加油、打车等），共75笔
- `invoice_no` 字段有 `unique=True`约束，且去重仅按 `invoice_no` 判断→全部被跳
- 2024年的75笔交易与2025年1笔旧`--`错误去重
- 修复：`--` 条目生成唯一ID `--{日期}_{序号}`（如 `--20241219_001`），每个独立导入

### 涉及文件
- `apps/core/import_excel.py` — `import_invoice()`函数完全重写

### 数据修复
- 删除原错误388条记录（金额虚增）+ 重新导入463条
- 验证：数据库金额 ¥358,686.47 = 文件金额 ¥358,686.47 ✅
- 浏览器验证：463条显示正常，含税金额 ¥371,026.75 ✅

### 待同步
- [ ] 同步代码到124服务器
- [ ] 同步数据库（需重新导入）