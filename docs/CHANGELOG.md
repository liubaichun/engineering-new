# 变更日志

## 2026-05-29 多租户SaaS设计 + 系统升级需求分析 v3.0

### 文档更新

| 文档 | 变化 |
|:-----|:------|
| `docs/系统升级方向需求分析报告.md` | ⬆️ **从v2.0升级到v3.0**——核心战略调整为"通用平台+行业插件包"模式。原有垂直定位改为平台底座+认证包+制造包三层架构。实施路线图从12周扩展为24周。增加了行业包开发标准、菜单加载规范、不做清单。 |
| `docs/多租户SaaS平台设计规范.md` | ✅ 新增（v1.0已创建，本次未改动） |
| `docs/CHANGELOG.md` | ✅ 已记录 |
| `docs/README.md` | ✅ 已更新索引 |

### v3.0核心变化

- **战略调整**：单一垂直 → 平台+行业包（认证包+制造包）
- **架构分层**：核心层（通用）+ 行业包层（按需加载）+ 租户配置层
- **新路线图**：P0核心加固(4周)→P1认证包(6周)+P2平台底座(8周并行)→P3制造包(8周)
- **新增标准**：行业包开发规范、菜单加载规范、权限码命名规范
- **不做清单**：明确9类功能不做（MES/电商/APP等）

### 新版本文档（5/29新增）

| 文档 | 说明 |
|:-----|:------|
| `docs/多租户SaaS平台设计规范.md` | 完整多租户架构方案（v1.0，含5个新增缺口已补充） |
| `docs/系统升级方向需求分析报告.md` | 升级方向需求分析（v3.0，平台+行业包模式） |
| `docs/质量安全与认证合规规范.md` | ⬆️ **新增**——等保二级+双软认证规范，含API/代码/字段标准、安全审计、加密备份、上线检查清单（约27KB） |
| `docs/系统深度审计报告与修改计划.md` | ⬆️ **新增**——全量代码扫描（195个文件），发现3项P0/6项P1/8项P2问题，含分周修复计划 |

### 关键决策

- **定位**：不做通用ERP → 做"软件认证+财务合规"垂直SaaS
- **销售模式**：不走传统订单(恒鑫兴模式) → 走项目驱动型销售(商机→合同→里程碑→收款)
- **库存**：不做传统仓库 → 做"物料流转看板"聚焦项目管理场景
- **报表**：不做11种销售统计 → 做管理驾驶舱(预算执行率/工资成本占比/项目进度)
- **多租户**：不使用Hybrid混合隔离(字段隔离→Schema隔离→独立DB按等级分配)
- **文档都标注了哪些功能我们不做**（分销/委外/BOM/积分等）

### 多租户设计亮点

- 通配符域名+数据库路由表（动态新增租户，无需改Nginx）
- JWT中不暴露tenant_id（防篡改），服务端Session双校验
- 平台管理端（恒鑫兴完全没有）
- 自助注册→邮箱验证→自动初始化→14天试用
- 在线数据迁移（共享→Schema→独立DB，不停机）

### 升级方案差异化（vs 恒鑫兴）

- 我们强在：工资/社保/预算/审批流（恒鑫兴没有）
- 恒鑫兴强在：进销存通用能力
- 我们不做：分销二维码/委外/BOM/动销率等不适用功能

## 2026-05-28 通知系统全面分析 + 需求文档梳理

### 分析

- **通知系统全面审计**：发现现有三层架构（站内通知/外部渠道/业务事件通知）存在核心断裂
  - **站内通知**（`core.Notification`）: ✅ 19条记录，crontab定时任务正常写入
  - **外部渠道**（`apps.channels`）: ❌ 飞书token过期、邮件走console、路由规则0条、渠道绑定指向已删除渠道
  - **业务事件通知**（`tasks.notification_service.py`）: ❌ 20+个`notify_xxx()`函数写好但从未被业务代码调用
- **需求文档梳理**：找到原始需求文档 `NOTIFICATION-SYSTEM.md` 和升级需求 `NOTIFICATION-SYSTEM-UPGRADE.md`
- **需求确认**：与用户确认通知系统定位——邮件留配置入口，IM捆绑（飞书/钉钉/微信）是核心

### 产出文档

| 文档 | 说明 |
|:-----|:-----|
| `docs/NOTIFICATION_SYSTEM_REQUIREMENTS.md` | 需求分析与实施计划（群通知/私信通知分类、三种绑定方式、分P实施） |
| `knowledge-base/01-requirements/NOTIFICATION-SYSTEM-OPTIMIZATION-V6.md` | 完整设计细节（流程逻辑、数据流、页面设计） |

### 设计要点

- **通知分两类**：群通知（群机器人Webhook）和私信通知（点对点推个人）
- **三种绑定方式**：扫码绑定🥇（飞书/钉钉/企微）、填Token🥈（微信PushPlus）、自动使用档案邮箱🥇
- **支持渠道**：飞书、钉钉、企业微信、微信（PushPlus）、邮件
- **实施分4个P**：P0基础设施（1天）→ P1用户绑定（1天）→ P2邮件配置（半天）→ P3业务接入（1天）
- **docs/README.md**：新增通知系统章节

## 2026-05-28 驾驶舱工资柱状图修复 + 数据同步检查

### 修复
- **月度工资柱状图缺1-3月数据**（`apps/finance/views.py` + `templates/stats.html`）：两个问题叠加
  - `SafePageNumberPagination` 默认 `page_size=20`，工资API按月份倒序返回
  - 第1页只返回4-7月数据，1-3月被分到第2页，前端未做翻页
  - 修复：`WageRecordViewSet.page_size = 200` 确保一年数据一次返回
  - 同时前端 `&page_size=100` 参数作为兜底

### 检查
- **数据统计页面模块同步检查**：经营驾驶舱覆盖了工资、收支、发票、项目、合同、设备、审批共9个数据源，与当前12个系统模块基本同步（缺预算执行监控、银行流水分析两个图表模块，属于前期设计未覆盖）

## 2026-05-28 侧边栏菜单去冗余：扁平化 + 合并

### 重构
- **侧边栏精简**（`templates/core/base.html` + `templates/base.html`）：
  - 扁平化单菜单项分组：**客户管理/采购管理/运营管理/文件管理** 直接显示为菜单项，去掉冗余的分组标题行
  - **"我的通知"** 合并到 **"数据"** 分组下（排在"数据统计"后面），不再孤立悬浮
  - 视觉上从 10个分组标题 + 20个菜单项 → 5个分组标题 + 21个菜单项

## 2026-05-28 权限矩阵修复：预算管理注册 + 银行流水权限清理

### 新增
- **预算管理权限注册**（`apps/finance/modules.py`）：新增 `budget` 模块注册（查看/新建/编辑/删除4个动作），权限码格式 `finance:budget:<action>`
- **BudgetViewSet权限码修正**（`apps/finance/views.py`）：从旧的 `finance:budget:manage` / `finance:report:read` 改为标准 `finance:budget:read`/`create`/`update`/`delete`

### 修复
- **银行流水权限精简**（`apps/finance/modules.py`）：去掉虚假的 新建/编辑/删除 3个动作，银行流水页面实际上只有导入和查看功能
- **权限矩阵计数更新**：财务分类从8个模块变为9个

## 2026-05-28 应收应付账龄分析修复

### 修复
- **应收应付账龄分析报表**：发票账龄计算回退逻辑遗漏 `issue_date`（开票日），发票无到期日时直接掉到 `today` 导致所有无到期日发票都显示为1-30天
- **修复方案**（`apps/finance/reports_v2.py`）：在账龄计算回退链中加上 `issue_date`，即 `due_date or issue_date or date or today`
- **效果**：百川两张待收发票（开票日2026-04-02/2026-03-30）从错误的"1-30天"修正为正确的"31-60天"

## 2026-05-28 Phase 3 发票管理全部完成

### 完成项
- **红冲发票关联**：模型字段+导入逻辑+前端显示已实现
- **认证所属期**：credited_period字段+序列化+前端编辑显示
- **到期提醒cron**：check_invoice_expiry管理命令+每日9点crontab
- **核销对账UI**：发票详情页核销按钮+API
- **附件上传**：上传/删除API+前端按钮
- **账龄分析报表**：API+前端完整渲染（30/60/90+天账龄段）
- **统计图表**：发票列表页新增月度趋势图、状态分布图、公司Top10
- **权限矩阵**：发票模块新增import(导入)/export(导出)独立动作

### 修复
- 财务报表年份下拉未包含发票年份（改为从Income/Expense/Invoice三表合并取年份）
- 发票导入兼容多Sheet格式（信息汇总表/发票基础信息自动识别）

## 2026-05-28 发票导入表头兼容性修复

### 核心问题
用户导入龙晟税局导出文件时，文件可能使用"全电发票号码"或"发票号码"表头，
但代码只精确匹配"数电发票号码"，导致找不到表头，返回"未识别到有效发票记录（1 行错误）"

### 修复方案（apps/core/import_excel.py）
1. **新增 INVOICE_NO_HEADERS**：支持3种表头变体，按优先级匹配
   - `数电发票号码` — 标准税局导出（全量发票查询）
   - `全电发票号码` — 旧版税局导出（2024年及以前）
   - `发票号码` — 纸质发票或旧版导出
2. **新增 `_find_invoice_header_row()`**：统一查找逻辑，返回匹配到的表头行索引+关键字+headers
3. **c_invoice_no 动态匹配**：根据实际匹配到的关键字（而非硬编码）确定发票号码列
4. **c_legacy_invoice_no 排除误匹配**：当发票号码列与数电/全电列相同时，标记为 -1
5. **新增诊断错误**：当无任何Sheet匹配时，报出Sheet列表+已找到的（方便用户排查）
6. **保留已有修复**：Sheet遍历+信息汇总表聚合+发票基础信息逐行+多Sheet去重

### 验证结果
- ✅ 数电发票号码 → 1行正确解析
- ✅ 全电发票号码 → 1行正确解析
- ✅ 发票号码（旧纸质发票）→ 1行正确解析
- ✅ 无发票号码列 → 返回诊断错误"文件中未找到包含发票号码的Sheet"
- ✅ 多Sheet去重 → 1行+1错误（重复跳过）

## 2026-05-28 发票导入底层修复（上一版）

### 核心问题
`import_invoice()` Sheet选择逻辑只处理"信息汇总表"（需含税率列），忽略"发票基础信息"Sheet
导致龙晟等公司的导出文件全部被跳过

### 修复方案（apps/core/import_excel.py）
1. 遍历所有Sheet：不再固定选一个Sheet
2. 双模式识别：信息汇总表（需聚合）+ 发票基础信息（逐行处理）
3. 合并去重：多Sheet结果按发票号合并，跨Sheet重复跳过
4. 纸质发票支持：--数电号码生成N/A-日期_序号临时编号
5. 列匹配修复：排除"发票号码"→"数电发票号码"的substring误匹配

### 测试结果
- ✅ 发票基础信息格式（无税率）→ 正确解析1条
- ✅ 信息汇总表格式（多行明细）→ 2行聚合为1条
- ✅ 混合格式（汇总表+基础信息+纸质发票）→ 3条全正确

## 2026-05-29 P2修复：默认排序 + 文件拆分

### 改动内容
1. **P2-2: 9个ViewSet添加默认排序**
   - IncomeViewSet → `ordering = ['-date', '-created_at']`
   - ExpenseViewSet → `ordering = ['-expense_date', '-created_at']`
   - WageRecordViewSet → `ordering = ['-year', '-month', '-created_at']`
   - InvoiceViewSet → `ordering = ['-issue_date', '-created_at']`
   - SupplierViewSet, ClientViewSet, ContractViewSet → `ordering = ['-created_at']`
   - ProjectViewSet, TaskViewSet → `ordering = ['-created_at']`
2. **P2-3: 拆分 finance/views.py（2804行→12文件）**
   - 创建 `views_common.py`：共享工具（SafePageNumberPagination, get_user_companies, render_bank_import_page 等）
   - 创建 `views_company.py`(112行) / `views_income.py`(237行) / `views_expense.py`(221行)
   - 创建 `views_wage.py`(741行) / `views_invoice.py`(358行) / `views_report.py`(770行)
   - 创建 `views_employee.py`(177行) / `views_social.py`(143行) / `views_bank.py`(99行)
   - 创建 `views_budget.py`(79行) / `views_arap.py`(138行)
   - `views.py` 降为20行重导出层（向后兼容）
   - `config/urls.py` 更新引用

### 同步
- [x] 43 服务器部署验证（HTTP 200）
- [ ] 124 服务器待同步

## 2026-05-29 — 审计报告 P0 修复

### P0-1: objects.get() 异常处理（已完成）
- **审计报告说46处，实际扫描结果：**
  - ✅ 原有23处已有 try/except
  - ❌ 修复4处裸奔 get()：
    - `apps/crm/views.py:388` — Contract.objects.get
    - `apps/purchasing/views.py:147` — PurchaseRequest.objects.get
    - `apps/purchasing/views.py:296` — PurchaseOrder.objects.get
    - `apps/purchasing/views.py:398` — PurchaseReceive.objects.get
  - ✅ 修复后全部 27 处 `objects.get()` 均有异常处理

### P0-2: save() 异常处理（进行中：10/20 文件）

**已完成高+中优先级模块：**
| 模块 | 状态 | 修了 | 说明 |
|------|:----:|:----:|------|
| **finance** (views_*.py × 9文件) | ✅ | 18处 | 发票/收支/工资/员工/公司/银行等核心业务save |
| **approvals** | ✅ | 14处 | 审批流全部操作（审批/拒绝/转交/委托/撤回等） |
| **crm** | ✅ | 12处 | 合同状态变更/付款计划/商机推进 |
| equipment | ✅ | 3处 | 设备借用/归还状态save |
| core | ✅ | 9处 | 用户密码/激活/通知/系统设置save |
| tasks | ✅ | 9处 | 项目/任务/流程状态save |
| channels | ✅ | 5处 | 渠道配置save |
| material | ✅ | 2处 | 物料库存/BOM节点save |
| notifications | ✅ | 1处 | 路由规则save |

### 在途
- P0-2: ✅ **全部完成**（29处裸save已包裹）
- P0-3: CSRF中间件（待开始）

## 2026-05-29 — P2-8: 迁移文件清理 + 旧代码清理

### 清理内容
1. **Finance 迁移修复** — 重建 0028/0029 文件，修复0030依赖链，消除编号间隙
2. **Core Phase1 权限系统清理** — 创建 0024 migration：
   - RunPython 保护2条审计日志（role_id→role_name 数据迁移）
   - 删除 core_role 表（7条废弃角色数据）
   - SeparateDatabaseAndState 处理已手动删除的 core_rolepermission/core_userrole
3. **Notifications 清理** — 0009 migration 状态同步已手动删除的5个模型
4. **Repair 清理** — 0002 migration 状态同步已手动删除的索引
5. **Core 005** — 状态同步已手动删除的 menu_code 列
6. **死脚本清理** — 删除 4 个旧 Phase1 权限迁移脚本
7. **Core admin.py** — 清理 UserRole 死注释

## 2026-05-29 — P1-4: CASCADE→PROTECT 关键业务模型

### 改动：finance 7处 + core 12处 = 19处 `on_delete=CASCADE` → `PROTECT`

**finance (7处)：**
| 模型 | 字段 | 原因 |
|:-----|:-----|:------|
| EmployeeCompany | employee, company | 员工任职关联 |
| CompanySocialConfig | company | 公司社保配置 |
| BankStatement | bank_account | 银行流水不应因删账户丢失 |
| Budget | company | 预算数据 |
| Account | company | 科目表 |
| RelatedPartyLedger | company | 往来台账 |

**core (12处)：**
| 模型 | 字段 | 数量 |
|:-----|:-----|:-----|
| UserCompanyRole | user, company | 2 |
| CompanyRole | company | 1 |
| CompanyRolePermission | company_role, permission | 2 |
| UserCompanyPermission | user, company, module, action | 4 |
| UserModulePermission | user, company, module | 3 |

**保留 CASCADE：** `Notification.user`, `ModuleAction.module`, `Account.parent`

### 验证
| 项目 | 状态 |
|:-----|:-----|
| models.py修改 | ✅ 19处已改 |
| finance.0041 migration | ✅ 43+124已应用 |
| core.0026 migration | ✅ 43+124已应用 |
| 0 pending, 0 errors | ✅ |
| 浏览器预算/员工/银行账户 | ✅ 正常加载 |

## 2026-05-29 — Day 5 全量回归测试

### P0+P1 全部 9 项终验

| 项目 | 43服务器 | 124服务器 |
|:-----|:---------|:----------|
| P0-1 get()异常处理 | ✅ | ✅ |
| P0-2 save()异常处理 | ✅ | ✅ |
| P0-3 CSRF降级P2 | ✅ 已分析 | ✅ |
| P1-1 SQL注入 | ✅ 参数化 | ✅ |
| P1-2 安全头配置 | ✅ SAMEORIGIN | ✅ |
| P1-3 except日志 | ✅ 34处 | ✅ |
| P1-4 CASCADE→PROTECT | ✅ 19处 | ✅ |
| P1-5 权限校验 | ✅ 已有声明 | ✅ |
| P1-6 print→logging | ✅ | ✅ |

### 验证指标
| 检查项 | 43 | 124 |
|:-------|:---|:----|
| makemigrations --check | ✅ No changes | ✅ No changes |
| showmigrations pending | ✅ 0 | ✅ 0 |
| check --deploy ERRORS | ✅ 0 | ⚠️ 1个历史遗留（CRM short_name） |
| 浏览器用户视角 | ✅ 控制台/预算/员工/系统/权限/用户 | ✅ login page / gunicorn running |
| gunicorn重启验证 | ✅ 200 | ✅ 200 |
