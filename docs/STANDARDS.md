# 企业信息化管理系统 开发标准与规范

> 本文档是企业信息化管理系统的**强制执行标准**。所有开发人员、sub-agent 必须严格遵守，不得擅自偏离。
> 违反以下规范导致的 Bug，视为生产事故。

---

## 一、字段命名规范

### 1.1 通用原则

| 层级 | 命名方式 | 示例 | 禁止 |
|------|---------|------|------|
| Python 模型/Serializer | snake_case | `employee_no`, `hire_date` | camelCase, PascalCase |
| JavaScript/JSON | camelCase | `employeeNo`, `hireDate` | snake_case |
| 数据库列 | snake_case | `employee_no` | 大写、驼峰 |
| API URL 路径 | kebab-case | `/wage-records/` | snake_case |
| Choice 值 | snake_case | `probation`, `enterprise` | 中文、中划线 |
| Choice 显示值 | 中文 | `'试用期'`, `'企业客户'` | 英文 |

### 1.2 强制规则：前端模板 JS 变量名必须与 API 响应字段名一致

**每次修改 Serializer 或模型后，必须同步更新前端模板。**

```
API 响应字段名（camelCase） = 前端 JS 引用字段名（camelCase）
模型字段名（snake_case）    = Serializer Meta.fields 中的字段名（snake_case）
```

**错误示例（已造成 Bug）：**
```javascript
// ❌ 直接在 JS 里写了模型字段名（snake_case）
emp.employee_no        // 模型是 code
emp.resignation_date   // 模型是 leave_date
emp.remark             // 模型是 remarks

// ✅ 正确：用 API 返回的字段名
emp.code
emp.leave_date
emp.remarks
```

### 1.3 状态/枚举类字段命名

Choice 字段必须在 Serializer 中暴露 `_display` 版本：

```python
# ✅ 正确：必有 _display 字段
status = serializers.ChoiceField(choices=Employee.EMPLOYEE_STATUS_CHOICES)
status_display = serializers.CharField(source='get_status_display', read_only=True)

class Meta:
    fields = ['id', 'status', 'status_display', ...]
```

前端 JS **禁止**自己写映射表，必须直接用 API 返回的 `xxx_display` 字段：

```javascript
// ✅ 正确
td.textContent = emp.status_display || '未知';

// ❌ 错误（已造成 Bug）
const statusText = { active: '在职', trial: '试用期', ... };
td.textContent = statusText[emp.status] || '未知';
```

### 1.4 Choice 值命名规则

```
模型 choice 值必须用英文 snake_case（禁止中文）
显示值（_display）用中文
API 接收/返回时用英文值
```

```python
# ✅ 正确
EMPLOYEE_STATUS_CHOICES = [
    ('active', '在职'),
    ('probation', '试用期'),
    ('intern', '实习'),
    ('resigned', '已离职'),
]
CLIENT_CATEGORY_CHOICES = [
    ('enterprise', '企业客户'),
    ('government', '政府事业单位'),
    ('special', '特殊客户'),
]

# ❌ 错误
EMPLOYEE_STATUS_CHOICES = [
    ('在职', '在职'),      # 值不能用中文
    ('trial', '试用期'),  # 'trial' 不是合法的 choice 值（模型实际用 'probation'）
]
```

### 1.5 FK 字段处理

Serializer 中 FK 字段命名规则：
- **写入力（输入）**：用 `_id` 后缀 → `company`, `project`（DRF 自动处理）
- **读取（输出）**：同时暴露对象详情 → `company_name`, `project_name`

```python
# ✅ 正确
company = serializers.PrimaryKeyRelatedField(queryset=Company.objects.all(), write_only=True)
company_name = serializers.CharField(source='company.name', read_only=True)

class Meta:
    fields = ['id', 'company', 'company_name', ...]
```

---

## 二、API 数据交换规范

### 2.1 认证方式

```
登录端点：POST /api/core/auth/login/
    Body: { "username": "...", "password": "..." }
    Response: { "status": "success", "user": { ... }, "token": "..." }

认证方式：CSRFExemptSessionAuthentication（基于 Cookie + Session）
    前端 Header: credentials: 'include'
    CSRF Token: X-CSRFToken（从 document.cookie 中读取 csrftoken）
```

**所有需要认证的 API 在无 cookie 时应返回 401/403，前端据此跳转登录页。**

### 2.2 响应格式标准

所有 API 响应必须遵循统一格式：

```json
// 成功（列表）
{
    "count": 42,
    "next": "/api/xxx/?page=2",
    "previous": null,
    "results": [ ... ]
}

// 成功（单个对象）
{ "id": 1, "name": "...", ... }

// 错误
{
    "detail": "Error message",
    "field_errors": { "field_name": ["Error"] }
}
```

### 2.3 API 开发 Checklist（每新增/修改 API 必须执行）

- [ ] 对照模型 `class Meta: fields` 列出所有字段，逐个确认字段名一致
- [ ] 对照 Choice 字段，确认 `xxx_display` 已加入 `Meta.fields`
- [ ] 对照 FK 字段，确认 `xxx_name`（或 `xxx_xxx_name`）已加入 `Meta.fields`
- [ ] 对照 `created_at`/`updated_at`，确认只读
- [ ] 对照 `id`，确认只读
- [ ] 计算字段（`tax_amount`、`net_salary` 等）确认 `read_only_fields`
- [ ] `create()` 方法中所有 `request.user` 引用前必须检查 `is_authenticated`
- [ ] 新增字段已在迁移文件中处理默认值

### 2.4 迁移前必查 FK 约束

```bash
# 迁移前执行，确保 FK 有效性
python manage.py shell -c "
from apps.crm.models import Client
from apps.finance.models import Invoice
from apps.tasks.models import Project

# 检查无效 FK
print('Invoice 无效 project_id:', Invoice.objects.exclude(project_id__in=Project.objects.values_list('id', flat=True)).count())
"
```

---

## 三、流程引擎运行规范

### 3.1 核心概念

| 概念 | 说明 |
|------|------|
| `FlowTemplate` | 流程模板（定义整个流程结构） |
| `FlowNodeTemplate` | 节点模板（定义每个步骤） |
| `TaskStageInstance` | 节点实例（运行时实例） |
| `StageActivity` | 活动记录（每个操作的审计日志） |
| `FlowTransition` | 流转记录（节点间流转历史） |

### 3.2 节点类型定义

```python
class NodeType:
    START = 'start'       # 开始节点（自动创建第一个实例）
    APPROVAL = 'approval' # 审批节点（人工审批）
    CONDITION = 'condition' # 条件节点（分支路由）
    ACTION = 'action'     # 自动执行节点
    END = 'end'           # 结束节点
```

### 3.3 流转规则

```
1. 顺序流转：节点按 order 字段顺序执行
2. 条件流转：condition_type + condition_value 决定下一节点
3. 审批规则：approval_type（单人/会签/或签）+ assignee_type（user/role/dept）
4. 超时处理：timeout_hours > 0 时自动提醒/升级
```

### 3.4 引擎接口标准

```python
class FlowEngine:
    def start_flow(self, template_id) -> {
        'success': bool,
        'instance_id': int,
        'current_node': str,
        'status': str
    }

    def complete_current_node(self, actor, action, comment) -> {
        'success': bool,
        'message': str,
        'next_node': str | None,
        'flow_completed': bool
    }

    def get_flow_status(self) -> {
        'has_flow': bool,
        'template_name': str,
        'current_node': str,
        'current_status': str,
        'current_assignee': str,
        'completed_nodes': list,
        'total_nodes': int,
        'completed_count': int
    }
```

### 3.5 状态机定义

```
Task.status: pending → in_progress → completed
              ↑___________↓
StageInstance.status: pending → in_progress → approved/rejected
                                       ↓
                    （有下一节点）→ 创建下一 StageInstance
                    （无下一节点）→ Task.status = completed
```

---

## 四、数据统计接口规范

### 4.1 统计口径标准

所有统计 API 必须明确口径（时间范围、筛选条件、数据来源）：

```python
# ✅ 正确：口径明确
GET /api/finance/reports/wage_summary/?year=2026&month=4
Response: {
    "口径": "2026年4月在岗员工工资统计",
    "count": 5,
    "total_gross": 35000.00,
    "total_net": 28000.00,
    "summary": { ... }
}

# ❌ 错误：口径不明确，返回模糊数字
Response: { "total": 35000 }
```

### 4.2 聚合维度标准

| 维度 | 字段 | 说明 |
|------|------|------|
| 时间 | `year`, `month` | 必选，用于同环比 |
| 主体 | `company`, `department` | 可选，分类汇总 |
| 类型 | `category`, `type` | 可选，细分统计 |

### 4.3 缓存策略

```
实时统计（count）：TTL=60s，允许误差
月报/年报：TTL=1小时，每天 0 点刷新
Dashboard 概览：前端每 60s 自动刷新
```

### 4.4 Dashboard 统计接口规范

Dashboard 调用的所有统计接口必须满足：

```javascript
// ✅ 正确：返回 count 字段供前端聚合
GET /api/tasks/projects/?status=active&page_size=1
Response: { "count": 5, "results": [...] }

// ❌ 错误：返回列表无 count 字段
Response: { "results": [...] }  // 前端无法获取总数
```

---

## 五、违规记录（已发生的事故）

| # | 事故 | 根因 | 规范依据 |
|---|------|------|---------|
| 1 | `EmployeeSerializer` 报 `ImproperlyConfigured` | Serializer 字段名与模型不一致 | §1.3, §2.3 |
| 2 | Employee 列表页工号显示 `undefined` | 前端用 `emp.employee_no` 但 API 返回 `emp.code` | §1.2 |
| 3 | Employee 状态显示英文 `probation` | 前端本地映射表缺少 `probation` | §1.3 |
| 4 | Client category 更新返回 400 | 发送中文值 `"企业客户"` 但模型期望 `"enterprise"` | §1.4 |
| 5 | 匿名 POST `/api/crm/suppliers/` 500 错误 | `create()` 中 `request.user` 未检查 `is_authenticated` | §2.3 |
| 6 | `make migrations` FK 约束失败 | 迁移前未清理无效 FK 数据 | §2.4 |
| 7 | `RoleSerializer.get_user_count` JSON 序列化失败 | 返回 Django `Count` 对象而非 Python 整数 | §2.3 |
| 8 | Dashboard 统计数字为 `-` | `/api/core/users/` 返回 403（权限配置问题） | §4.4 |
| 9 | `FilterSet` 导入错误 | 误 `from filters import X` 但 X 定义在 views.py 内联 | §2.3 |
| 10 | Invoice 模板缺 5 个字段 | 模型加字段后未同步前端模板 | §1.2 |
