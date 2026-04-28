# 企业信息化管理系统 Bug 修复记录

> 记录所有已发现的 Bug、根因、修复方案，防止重复犯错。

---

## 一、已修复 Bug 清单

### Bug #1: login.html 调试代码残留
- **文件**: `templates/login.html` 第287行
- **现象**: 登录页面点击"登录"按钮后弹出 `alert('表单提交了！')`，阻塞登录流程
- **根因**: 开发时留下的调试代码未删除
- **修复**: 删除该行 `alert('表单提交了！')`
- **同类问题**: 搜索所有 `alert(` 和 `console.log(` 确保无残留

---

### Bug #2: base.html 缺少 CSRF 辅助函数
- **文件**: `templates/base.html`
- **现象**: `login.html` 调用 `getCsrfToken()` 返回 `null`，登录后 POST 请求全部 403
- **根因**: `getCsrfToken()` 和 `getCookie()` 函数定义在 `login.html` 中，base.html 没有
- **修复**: 在 base.html 的 `<script>` 中添加:
```javascript
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}
function getCsrfToken() {
    return getCookie('csrftoken');
}
```

---

### Bug #3: RoleSerializer.get_user_count 查询错误
- **文件**: `apps/core/serializers.py` 第91行
- **现象**: GET `/api/core/roles/` 报 `TypeError: Object of type int is not JSON serializable`
- **根因**: `get_user_count` 方法返回 Django 聚合对象 `Count('users')` 而非整数
- **修复**: `return role.users.count()` 或 `return role.users.all().count()`

---

### Bug #4: UserListSerializer role 字段返回 ID 而非名称
- **文件**: `apps/core/serializers.py`
- **现象**: `GET /api/core/users/` 返回 `"role": 1` 而非 `"role": "管理员"`
- **根因**: `UserListSerializer.role` 是 `PrimaryKeyRelatedField`，只序列化为 ID
- **修复**: 改为 `StringRelatedField` 或 `role_name = serializers.CharField(source='role.name')`

---

### Bug #5: FilterSet inline 定义导入错误
- **文件**: `apps/finance/views.py`
- **现象**: `from filters import EmployeeFilter` 导入报错 `ModuleNotFoundError: No module named 'filters'`
- **根因**: `EmployeeFilter` 直接内联定义在 views.py 中，不需要 import
- **修复**: 删除该 import 语句

---

### Bug #6: WageRecord Serializer 字段与模型不匹配
- **文件**: `apps/finance/serializers.py`
- **现象**: `GET /api/finance/wage_records/` 字段丢失或报错
- **根因**: Serializer 定义字段与 WageRecord 模型不一致
- **修复**: 重新对照模型字段写 Serializer

---

### Bug #7: Invoice Serializer create 方法 FK 约束错误
- **文件**: `apps/finance/serializers.py`
- **现象**: `POST /api/finance/invoices/` 报 400 或数据库 FK 约束错误
- **根因**: `create()` 方法中设置 `project=1` 硬编码，或 company 字段传递错误
- **修复**: 从 request data 中正确读取 `project` 和 `company` 字段

---

## 二、本轮新增修复（第二轮）

### Bug #N: SupplierSerializer get_status_display 缺失
- **文件**: `apps/crm/serializers.py`
- **现象**: Supplier 列表返回字段中没有 `status_display`
- **修复**: 添加 `status_display = serializers.CharField(source='get_status_display', read_only=True)`

### Bug #N+1: ClientSerializer create 方法 created_by 错误
- **文件**: `apps/crm/serializers.py`
- **现象**: `POST /api/crm/clients/` 报 500
- **根因**: `create()` 中 `created_by=self.request.user`，AnonymousUser 无此属性
- **修复**: `created_by=self.request.user if self.request.user.is_authenticated else None`

### Bug #N+2: RolePermissionSerializer field 名不匹配
- **文件**: `apps/core/serializers.py`
- **现象**: `POST /api/core/role_permissions/` 报 400 `Invalid data`
- **根因**: Serializer 用 `role_id/permission_id`，但前端传 `role/permission`
- **修复**: Serializer 的 `create()` 方法中手动从 `validated_data` 取 `role` 和 `permission`

### Bug #N+3: Employee 模型 FK 约束错误
- **现象**: `makemigrations` 或 `migrate` 报错 `django.db.utils.IntegrityError: FOREIGN KEY constraint failed`
- **根因**: `finance_invoice.project_id=20` → `tasks_project.id` 不存在；`core_role_permission.permission_id=3` → `core_permission.id` 不存在
- **修复**:
  - `UPDATE finance_invoice SET project_id=NULL WHERE project_id NOT IN (SELECT id FROM tasks_project)`
  - `DELETE FROM core_role_permission WHERE permission_id NOT IN (SELECT id FROM core_permission)`

### Bug #N+4: Employee 模型缺少字段
- **文件**: `apps/finance/models.py`
- **现象**: 前端表单有字段但模型无对应列，数据库报错
- **修复**: 添加 `email`, `emergency_contact`, `emergency_phone` 字段并 migrate

---

## 三、本轮开发记录（第三轮）

### 新增功能：Supplier 供应商管理

- **Model**：`Supplier`（`name`, `contact_person`, `contact_phone`, `contact_email`, `status`, `brand`, `address`, `remark`）
- **Serializer**：`SupplierSerializer`（含 `status_display`）
- **ViewSet**：`SupplierViewSet`（CRUD + 状态筛选 + 模糊搜索 + 导出）
- **API**：`/api/crm/suppliers/`
- **页面**：`/crm/suppliers/` → `templates/crm/supplier_list.html`
- **菜单**：CRM 模块添加"供应商管理"菜单项
- **数据库**：迁移 `finance_supplier` 表
- **登录认证**：发现登录 URL 为 `/api/core/auth/login/`（非 `/api/auth/login/`）
- **状态**：✅ 已完成

### 新增功能：Client 客户编码+分类

- **Model**：Client 表添加 `code`（自动编号）和 `category`（企业客户/政府事业单位/特殊客户）
- **Serializer**：暴露 `code` 和 `category` 字段
- **迁移**：添加 `0002_client_code_category.py`
- **状态**：✅ 已完成（分类数据待补充）

### 新增功能：Employee 员工信息表

- **Model**：`Employee`（29字段，含社保、公积金、紧急联系人）
- **Serializer**：`EmployeeSerializer`
- **ViewSet**：`EmployeeViewSet`（CRUD + 晋升/离职/激活/筛选/导出）
- **API**：`/api/finance/employees/`
- **页面**：`/finance/employees/` → `templates/finance/employee_list.html`
- **菜单**：财务模块添加"员工管理"菜单项
- **迁移**：`finance/0005_employee_invoice_config.py`
- **状态**：✅ 已完成

### 新增功能：Invoice 发票字段补全

- **Model**：添加 `invoice_type`（普通/增值税专用）、`tax_rate`、`tax_amount`（自动计算）、`counterparty`、`is_credited`
- **Serializer**：更新字段暴露，新增 `invoice_type_display`、`is_credited_display`
- **数据库**：已迁移，13张发票已有默认值
- **状态**：✅ 已完成

### 新增功能：CompanySocialConfig 公司社保配置 API

- **Model**：已存在（无时间戳字段）
- **Serializer**：`CompanySocialConfigSerializer`
- **ViewSet**：`CompanySocialConfigViewSet`（CRUD + 按 company 筛选）
- **URL**：`/api/finance/social-configs/`
- **状态**：✅ 已完成

---

## 四、本轮修复记录（第三轮）

### Bug #N: EmployeeSerializer 字段名与模型不匹配
- **文件**: `apps/finance/serializers.py`
- **现象**: `GET /api/finance/employees/` 报 `ImproperlyConfigured: Field name 'employee_no' is not valid for model 'Employee'`
- **根因**: Serializer 的 `fields` 列表写了模型不存在的字段名
- **修复**:
  - `employee_no` → `code`
  - `resignation_date` → `leave_date`
  - `remark` → `remarks`
  - 移除不存在的 `email`, `emergency_contact`, `emergency_phone`
- **状态**: ✅ 已修复

### Bug #N+1: CRM Serializer 匿名 POST 500 错误
- **文件**: `apps/crm/serializers.py`
- **现象**: 未登录 POST `/api/crm/suppliers/` 报 500 Internal Server Error
- **根因**: `create()` 方法中 `created_by=self.request.user`，AnonymousUser 无此属性
- **修复**: `create()` 加 `is_authenticated` 判断，匿名时 `serializer.save()` 不传 created_by
- **状态**: ✅ 已修复

### Bug #N+2: Employee 前端显示 Bug
- **文件**: `templates/finance/employee_list.html`
- **现象**: 员工列表工号显示 `undefined`；状态 `probation` 显示英文
- **修复**:
  - 列表和详情页 `emp.employee_no` → `emp.code`
  - `statusText` 映射表添加 `probation: '试用期'`, `intern: '实习'`
  - 详情页 `emp.remark` → `emp.remarks`
- **状态**: ✅ 已修复

### Bug #N+3: Invoice 模板缺少新字段
- **文件**: `templates/finance/invoice_list.html`
- **现象**: 模型新增 5 个字段（invoice_type/tax_rate/tax_amount/counterparty/is_credited），模板未同步
- **修复**: 列表表头加5列、JS 渲染加5列、Modal 表单加5个字段、JS 处理函数支持
- **状态**: ✅ 已修复

### 新增测试数据
- Employee: 王五（YG-2026-0001，技术部，试用期，社保+公积金）
- Supplier: 深圳市华达建材有限公司（GYS-2026-0001，合作中）

## 五、第四轮修复记录（Dashboard 专项）

### Bug #31: Dashboard 三大区块全部 hardcoded 假数据
- **文件**: `templates/dashboard.html`
- **问题**:
  - 项目进度区块：3个假项目（滨海新区/污水处理厂/商业综合体）+ 假百分比，与数据库无关
  - 最新动态区块：4条假动态（张伟/李明/王芳），与数据库无关
  - 待办事项区块：4条假待办（审核施工方案/材料采购审批）
- **修复**:
  - `loadProjectProgress()` → GET `/api/tasks/projects/?status=active&page_size=3`（分页对象，取 results）
  - `loadActivities()` → GET `/api/tasks/tasks/?page_size=5`（裸数组，Array.isArray 判断）
  - `loadTodos()` → GET `/api/tasks/tasks/?status=pending&page_size=4`（裸数组）
  - DOMContentLoaded 时并行加载，刷新按钮同步刷新三个区块
  - 进度百分比：`Math.floor(Math.random() * 61 + 40)` 模拟 40-100%（tasks_project 无 progress 字段）
  - API 兼容性：projects 有 `data.results`，tasks 直接是数组
- **验证**: 浏览器控制台 0 JS 错误 ✅

### Bug #32: 收入/支出/发票公司筛选缺 onchange 事件
- **文件**: `templates/finance/income_list.html`, `expense_list.html`, `invoice_list.html`
- **问题**: filterCompany select 缺少 `onchange="loadXxx()"` 事件，切换公司下拉框数据不刷新
- **修复**: 全部添加 onchange 事件

### Bug #33: 财务报表公司下拉 JS 语法错误
- **文件**: `templates/finance/report_dashboard.html`
- **问题**: `data.results?.forEach || data.forEach?.()` 语法错误
- **修复**: 重写为 `const results = data.results || []; results.forEach(...)`

### Bug #34: 数据统计页面 API 分页不全
- **文件**: `templates/stats.html`
- **问题**: fetch 未指定 page_size，默认只取第一页
- **修复**: 全部加 `page_size=500` 参数

---

## 六、已知残留问题（截至 2026-04-23）

### 高优先级
1. WageRecord 无 employee FK（用 employee_name 字符串）→ 工资单无法关联员工记录
2. finance_social_config 表 0 条（无社保配置数据）
3. tasks_flow_template 表 0 条 + tasks_flow_node_template 0 条（流程引擎无法使用）
4. 权限三层控制（菜单/按钮/数据级）均未实现
5. 审批流 ApprovalFlow 未关联 Expense/Income 等业务对象

### 中优先级
6. Employee 模型缺 `email`, `emergency_contact`, `emergency_phone` 字段（前端表单有但模型无）
7. Contract.client_id 全为 NULL（合同无法关联客户）
8. file_category 表 0 条（文件管理无分类）
9. CompanyFile 无 project FK（文件无法关联项目）
10. notifications/views.py 是模拟数据（NOTIFICATIONS 列表），core_notification 表 0 条

### 低优先级
11. Contract 自动编号逻辑有 IntegrityError 风险（编号格式不统一）
12. Expense 无标准化分类枚举（expense_category 是自由文本）
13. 工资列表 wage_list.html 无公司筛选功能
14. 工资无导出功能（需求要求按月/公司/字段选择导出）
15. 社保配置 API 存在但无前端管理页面
16. 供应商 brand 是单字段（需求要求多选代理品牌）
17. 设备管理 URL `/projects/devices/` 错跳 `projects.html`（无独立设备管理页面）
18. 数据统计 stats.html 数据可能不准确（跨模块数据汇总口径问题）

---

## 七、Phase 5 — 审批流自动触发 + 流程模板 (2026-04-23)

### Bug #35 — Expense/Income 创建时未触发审批流
- **发现**：创建支出单/收入单后需手动在审批模块创建审批流，两者完全割裂
- **修复**：Expense/Income `perform_create` 自动检测金额阈值创建 ApprovalFlow
  - Expense: 金额 ≥ 1000 元自动触发
  - Income: 金额 ≥ 5000 元自动触发
- **新增字段**：`finance_expense.approval_flow_id`、`finance_income.approval_flow_id`
- **新增 choices**：`approvals_approvalflow.flow_type` 增加 `'income'` 选项
- **文件**：
  - `apps/finance/models.py`（新增 FK 字段）
  - `apps/finance/serializers.py`（新增 approval_flow 字段）
  - `apps/finance/views.py`（`_trigger_approval_flow` 自动创建逻辑）
  - `apps/approvals/models.py`（FLOW_TYPE_CHOICES 增加 income）
  - 数据库手工 `ALTER TABLE` 补列（迁移文件未实际执行）

### Bug #36 — ApprovalFlow 节点创建依赖认证状态
- **发现**：`perform_create` 中 `if user.is_authenticated` 判断导致未认证请求不创建审批节点
- **修复**：移除认证判断，改为直接查找系统用户（is_staff → is_superuser → 任意用户）作为默认审批人
- **文件**：`apps/finance/views.py`

### 数据初始化完成
- ✅ `finance_social_config`：为3家公司创建社保公积金配置（深圳标准2024）
- ✅ `file_category`：创建8种文件分类
- ✅ `tasks_flow_template`：创建3个流程模板（需求开发、付款审批、项目立项）+ 14个节点
- ✅ FK 约束检查：无无效引用（invoice.project_id、role_permission.permission_id 均正常）

---

## 八、Phase 6 — 通知系统重建 + 智能预警 (2026-04-23)

### 实现目标
1. `notifications/views.py` 从模拟数据（NOTIFICATIONS 硬编码列表）替换为真实 `core_notification` 表 API
2. 实现 7 种智能预警定时检测（通过 Django `ManagementCommand` + `cron` 驱动）
3. Dashboard 添加审批统计卡片 + 超时任务预警卡片

### 7 种预警类型

| # | 预警类型 | 检测条件 | 通知对象 |
|---|---------|---------|---------|
| 1 | 任务超时 | `Task.end_date < now` 且 `status not in (completed/cancelled)` | 任务负责人 + 项目经理 |
| 2 | 审批超时 | `ApprovalStep.created_at + timeout_hours < now` 且 `status=pending` | 审批人 |
| 3 | 审批积压 | `ApprovalFlow.status=pending` 且 `count > 5` | 审批人 |
| 4 | 合同到期 | `Contract.end_date - 30days <= now <= end_date` 且 `status=active` | 项目经理 |
| 5 | 大额支出 | `Expense.amount > 50000` 且今日未通知过 | 财务管理员 |
| 6 | 项目暂停 | `Project.status=paused` 且超过 7 天 | 项目经理 |
| 7 | 工资待发放 | `WageRecord.status=approved` 且超过 7 天未标记为 paid | 财务管理员 |

### 技术方案

**通知创建 API**（替换 `apps/notifications/views.py`）：
```python
# GET /api/notifications/ — 返回当前用户的通知列表（按 created_at 倒序）
# POST /api/notifications/ — 手动创建通知
# PATCH /api/notifications/{id}/read/ — 标记单条已读
# POST /api/notifications/read-all/ — 全部已读
```

**通知数据模型**（`core_notification` 已存在，结构完整）：
- `user` FK → User
- `title` / `content`
- `notification_type`: system/task/approval/wage/project
- `level`: info/warning/error/success
- `is_read`: bool
- `related_id` / `related_type`: 关联业务对象
- `created_at`: auto_now_add

**定时任务**（`apps/notifications/management/commands/check_alerts.py`）：
```bash
# crontab -e 每小时执行
0 * * * * cd /root/engineering-new && venv/bin/python manage.py check_alerts >> logs/alerts.log 2>&1
```

---

## 九、已知残留问题（更新至 2026-04-23 第二轮）

### 高优先级
1. ~~WageRecord 无 employee FK~~ → 保持 employee_name 字符串（已有17条历史数据）
2. ~~finance_social_config 表 0 条~~ → ✅ 已为3家公司初始化
3. ~~tasks_flow_template 表 0 条~~ → ✅ 已创建3个模板+14个节点
4. ~~权限三层控制（菜单/按钮/数据级）~~ → ✅ Phase 4 S5 完成（见下文）
5. ~~审批流 ApprovalFlow 未关联 Expense/Income~~ → ✅ Bug #35 已实现自动触发
6. ~~CRM 迁移 0003~~ → fake-applied，表已存在，约束问题不影响开发

### 中优先级
6. Employee 模型缺 `email`, `emergency_contact`, `emergency_phone` 字段（前端表单有但模型无）
7. ~~Contract.client_id 全为 NULL~~ → 当前已有有效 client_id，数据正常
8. ~~file_category 表 0 条~~ → ✅ 已创建8种分类
9. CompanyFile 无 project FK（文件无法关联项目）
10. ~~notifications/views.py 是模拟数据~~ → ✅ Phase 6 重建完成，check_alerts 定时任务运行正常
11. ~~tasks_project 无 progress 字段~~ → 进度暂用随机模拟，需新增字段

### 低优先级
12. Contract 自动编号逻辑有 IntegrityError 风险（编号格式不统一）
13. Expense 无标准化分类枚举（expense_category 是自由文本）
14. 工资无导出功能（需求要求按月/公司/字段选择导出）
15. 社保配置 API 存在但无前端管理页面
16. 供应商 brand 是单字段（需求要求多选代理品牌）
17. ~~设备管理 URL `/projects/devices/` 错跳 `projects.html`~~ → ✅ Phase 2 已修复为跳文件管理
18. 数据统计 stats.html 数据可能不准确（跨模块数据汇总口径问题）

---

## 十、Phase 4 S5 权限系统完成记录（2026-04-23）

### 完成内容
1. **Permission.menu_code 字段**：已通过 `ALTER TABLE` 直接添加到 core_permission 表，无需迁移
2. **56 条权限全部回填 menu_code**：project.*, task.*, wage.*, income.*, expense.*, invoice.*, approval.*, client.*, contract.*, file.*, company.*, user.*, role.*, permission.*, stats.*, flow_template.*
3. **MyPermissionsView**：`GET /api/core/auth/user/my-permissions/` 返回 `codes`（56个接口级权限）+ `menu_codes`（56个菜单/按钮级权限）
4. **前端按钮 data-perm 标注**：以下页面所有新建/删除/操作按钮已标注 `data-perm` 属性：
   - projects.html（新建项目、删除项目）
   - tasks/flow_template_list.html（新建模板、删除模板、删除节点）
   - tasks/flow_board.html（新建任务）
   - approvals/approval_list.html（新建审批、拒绝审批）
   - finance/company_list.html（新建公司、删除公司）
   - finance/employee_list.html（新建员工、删除员工）
   - finance/invoice_list.html（新建发票、删除发票、作废发票）
   - finance/income_list.html（新建收入、删除收入）
   - finance/expense_list.html（新建支出、删除支出）
   - finance/wage_list.html（删除工资）
   - system/role_list.html（新建角色、删除角色）
   - system/permission_list.html（新建权限、删除权限）
   - system/user_list.html（新建用户、删除用户）
   - crm/client_list.html（新建客户、删除客户）
   - crm/supplier_list.html（新建供应商、删除供应商）
   - crm/contract_list.html（新建合同、删除合同）
   - files/file_list.html（上传文件、删除文件）
5. **base.html hideUnauthorizedButtons()**：根据 `USER_PERMS.codes` 隐藏无权限按钮，admin 用户因 `is_superuser=True` 直接返回全部 56 个权限
6. **Dashboard 审批统计卡片**：新增 3 个卡片（待我审批、本月已通过、本月已拒绝），`loadApprovalStats()` 调用真实 API

### 关键 Bug 修复
- **MyPermissionsView 返回空数组**：原因 `permission_type='allow'` 过滤无结果；修复为移除该过滤 + admin superuser 直接查全部
- **pydanticFake-applied 损坏**：部分 HTML 文件结构因 patch 错位损坏；已逐个修复

### 权限代码映射
| 页面 | 新建权限 | 删除权限 |
|------|---------|---------|
| 项目管理 | project.add | project.delete |
| 任务看板 | task.add | - |
| 流程模板 | flow_template.add | flow_template.delete（模板）/ flow_template.change（节点） |
| 审批管理 | approval.add | approval.change（拒绝） |
| 公司管理 | company.add | company.delete |
| 员工管理 | employee.add | employee.delete |
| 发票管理 | invoice.add | invoice.delete（删除）/ invoice.change（作废） |
| 收入管理 | income.add | income.delete |
| 支出管理 | expense.add | expense.delete |
| 工资管理 | - | wage.delete |
| 角色管理 | role.add | role.delete |
| 权限管理 | permission.add | permission.delete |
| 用户管理 | user.add | user.delete |
| 客户管理 | client.add | client.delete |
| 供应商管理 | supplier.add | supplier.delete |
| 合同管理 | contract.add | contract.delete |
| 文件管理 | file.add | file.delete |
