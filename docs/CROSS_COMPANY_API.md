# 跨公司数据聚合方案文档

> 版本：v1.0 | 日期：2026-05-25 | 作者：hermes-b001

---

## 一、背景

### 问题
权限系统重构后（v7），用户可以分别在不同公司获得不同模块的权限。但数据过滤机制仍然是**单公司模式**——用户只能看到"当前切换到的公司"的数据。这导致：

- 用户在绿聚能有收支权限、在百川也有收支权限 → 需要切换公司才能分别查看
- 用户想要看到**所有有权限公司的聚合数据**，而不是单公司切换

### 方案
按**模块粒度**返回用户有权限的公司列表，数据过滤从 `company_id = x`（单公司）改为 `company_id IN (x, y, z)`（多公司聚合）。

权限校验也相应调整：不再检查"当前公司是否有权限"，而是检查"任意公司是否有权限"。精确的数据范围由 `get_queryset()` 中的 `get_module_companies()` 控制。

---

## 二、核心工具函数

### `get_module_companies(user, module_name, action='read')`

**位置**：`apps/core/permissions.py`

**功能**：返回用户对指定模块有 `action` 权限的所有公司 ID 列表。

```python
def get_module_companies(user, module_name, action='read'):
    """
    返回用户对指定模块有 action 权限的所有公司 ID 列表。

    参数：
        user: User 对象
        module_name: str — 模块名（如 'income', 'expense', 'project'）
        action: str — 动作名（默认 'read'）

    返回：
        None — 超级用户，不过滤（见全公司数据）
        []   — 用户无任何公司有此权限
        [1, 2, 3] — 用户在此列表中的公司有此权限
    """
```

### 行为

| 用户类型 | action='read' | action='create' | 返回 |
|---------|--------------|----------------|:----:|
| 超级用户 | — | — | `None`（不过滤） |
| 普通用户 | 任意公司有此权限 | — | `[company_ids]` |
| 普通用户 | 无公司有此权限 | — | `[]` |

### 使用示例（ViewSet 中）

```python
from apps.core.permissions import get_module_companies

class IncomeViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        qs = super().get_queryset()
        cids = get_module_companies(self.request.user, 'income')
        if cids is not None:
            qs = qs.filter(company_id__in=cids)
        return qs
```

---

## 三、已修改的模块

### 3.1 财务管理（`apps/finance/views.py`）

| ViewSet | 模块名 | 过滤方式（旧→新） |
|---------|--------|-----------------|
| `IncomeViewSet` | `income` | `get_user_companies()` → `get_module_companies(user, 'income')` |
| `ExpenseViewSet` | `expense` | `get_user_companies()` → `get_module_companies(user, 'expense')` |
| `WageRecordViewSet` | `wage` | `get_user_companies()` → `get_module_companies(user, 'wage')` |
| `InvoiceViewSet` | `invoice` | `get_user_companies()` → `get_module_companies(user, 'invoice')` |
| `EmployeeViewSet` | `employee` | `user.company_id` → `get_module_companies(user, 'employee')` |
| `EmployeeCompanyViewSet` | `employee` | `user.company_id` → `get_module_companies(user, 'employee')` |
| `BankAccountViewSet` | `bank` | `user.company_id` → `get_module_companies(user, 'bank')` |
| `SocialRecordViewSet` | `company` | `user.company_id` → `get_module_companies(user, 'company')` |

### 3.2 采购管理（`apps/purchasing/views.py`）

| ViewSet | 模块名 | 备注 |
|---------|--------|------|
| `PurchaseRequestViewSet` | `purchase_request` | ⚠️ DB模块名是 `purchase_request`（不是 `request`） |
| `PurchaseOrderViewSet` | `purchase_order` | |
| `PurchaseReceiveViewSet` | `purchase_receive` | |
| `PurchaseRequestItemViewSet` | `purchase_request` | 继承父单公司 |
| `PurchaseOrderItemViewSet` | `purchase_order` | 继承父单公司 |
| `PurchaseReceiveItemViewSet` | `purchase_receive` | 继承父单公司 |

### 3.3 项目管理（`apps/tasks/views.py`）

| ViewSet | 模块名 |
|---------|--------|
| `ProjectViewSet` | `project` |
| `TaskViewSet` | `task` |
| `FlowTemplateViewSet` | `task` |
| `FlowNodeTemplateViewSet` | `task` |
| `TaskStageInstanceViewSet` | `task` |
| `StageActivityViewSet` | `task` |
| `FlowTransitionViewSet` | `task` |
| `TaskFlowInstanceViewSet` | `task` |

### 3.4 客户管理（`apps/crm/views.py`）

| ViewSet | 模块名 |
|---------|--------|
| `ClientViewSet` | `customer` |
| `SupplierViewSet` | `supplier` |
| `ContractViewSet` | `contract` |
| `OpportunityViewSet` | `opportunity` |
| `ContactViewSet` | `contact` |
| `ClientSourceViewSet` | `client_source` |
| `FollowUpRecordViewSet` | `followup` |
| `PaymentPlanViewSet` | `payment_plan` |
| `ContractChangeLogViewSet` | `contract_change_log` |

---

## 四、权限校验变更

### `RoleRequired._user_has_perm_for_company()`

**旧行为**：从请求中解析 `company_id`（session/query/body）→ 检查用户在该公司是否有此权限。

**新行为**：移除公司维度限制 → 检查用户在**任意公司**是否有此权限。只要有一条 `UserModulePermission` 记录满足条件就放行。

```python
# 旧：检查单公司
UserModulePermission.objects.filter(
    user=user, company_id=company_id, module__name=module_name, ...
)

# 新：跨公司检查
UserModulePermission.objects.filter(
    user=user, module__name=module_name, ...
)
```

**安全说明**：权限校验（gate）和 数据过滤（scope）是两层独立保护：
1. **权限校验**（`has_permission`）：用户是否有权访问这个页面/API → 跨公司检查
2. **数据过滤**（`get_queryset`）：用户在这个页面能看到哪些数据 → 按模块粒度过滤公司

---

## 五、新增/修复的 API

### 5.1 切换公司 API

**`POST /api/core/auth/switch-company/`**（新增端点，原 `@action` 无效已修复）

```json
// 请求
{"company_id": 4}

// 响应
{
    "status": "success",
    "message": "已切换到公司",
    "current_company_id": 4,
    "company_name": "深圳市绿聚能科技有限公司"
}
```

**`POST /api/core/auth/user/`**（复用 CurrentUserView，新增 action 模式）

```json
// 请求（切换公司）
{"action": "switch_company", "company_id": 4}

// 请求（查看可访问公司列表）
{"action": "my_companies"}
```

### 5.2 旧端点兼容

```http
POST /api/core/switch_company/      → 仍然可用，指向 SwitchCompanyView
POST /api/core/auth/switch-company/ → 新标准端点
POST /api/core/auth/user/           → POST 新增 action 模式
```

---

## 六、前端变更

### 6.1 采购管理 Tab 权限屏蔽

**文件**：`templates/purchasing/index.html`

三个 tab 分别受独立权限控制：

```html
{% if 'purchasing:purchase_request:read' in user_menu_codes or request.user.is_superuser %}
  <li>采购申请</li>
{% endif %}
{% if 'purchasing:purchase_order:read' in user_menu_codes or request.user.is_superuser %}
  <li>采购订单</li>
{% endif %}
{% if 'purchasing:purchase_receive:read' in user_menu_codes or request.user.is_superuser %}
  <li>采购入库</li>
{% endif %}
```

---

## 七、修复的 Bug

| Bug | 文件 | 影响 | 根因 |
|-----|------|------|------|
| 6个 ViewSet 的 `action_perms` 未赋值 | `finance/views.py` | 所有自定义 action（如 confirm/export/summary）权限失效 | bare `{dict}` 在类体中是空操作 |
| IncomeViewSet 用了 `'expense'` 模块名 | `finance/views.py:291` | 收入页面无数据 | 查找替换错位 |
| 采购模块名不匹配 | `purchasing/views.py` | 权限校验失败（DB 的 `purchase_request` vs action_perms 的 `request`） | 类定义与 DB 注册不一致 |
| `@action` 在 `APIView` 上无效 | `core/views.py` | switch_company 路由 404 | `@action` 仅对 ViewSet 生效 |
| 采购 tab 无权限屏蔽 | `templates/purchasing/index.html` | 无采购订单权限的用户也看到 tab | 缺少模板层条件判断 |

---

## 八、E2E 验证记录

**测试用户**：`yangxiaohui`（普通用户，非超管）

### 测试场景 1：增删权限 → 侧边栏实时响应

| 操作 | 预期 | 结果 |
|------|------|:----:|
| 初始 8 模块 | 侧边栏 8 个菜单 | ✅ |
| 添加 `file:read` | 出现「文件→文件管理」 | ✅ |
| 删除 `file` | 菜单消失 | ✅ |
| 删除 `income` | 「收支管理」消失 | ✅ |

### 测试场景 2：跨公司数据聚合（核心改动）

| 场景 | 公司权限 | 数据条数 | 结果 |
|------|---------|:--------:|:----:|
| 收入管理（初始） | 百川(3) + 绿聚能(4) | 159条 | ✅ 两个公司混排 |
| **删除百川收入权限** | 仅绿聚能(4) | **63条** | ✅ 仅绿聚能 |
| **恢复百川收入权限** | 百川(3) + 绿聚能(4) | **159条** | ✅ 恢复双公司 |
| 支出管理 | 百川(3) + 绿聚能(4) | 731条 | ✅ 两个公司混排 |
| 工资管理 | 仅绿聚能(4) | 29条 | ✅ 仅单公司 |

### 测试场景 3：采购 Tab 权限屏蔽

| 用户 | 权限 | 可见 Tab |
|------|------|---------|
| yangxiaohui | purchase_request 仅 | 采购申请 ✅（采购订单/采购入库隐藏） |

### 测试场景 4：新 API 验证

| API | 方法 | 结果 |
|-----|:----:|:----:|
| `POST /api/core/auth/user/` (action='my_companies') | POST | ✅ 返回 {companies: [{...}]} |
| `POST /api/core/auth/user/` (action='switch_company') | POST | ✅ 返回切换成功 |
| `POST /api/core/switch_company/` | POST | ✅ 兼容旧端点正常 |

---

## 九、如何为新增 ViewSet 接入

1. 确认模块名是否已在 `apps/*/modules.py` 中注册（`register_module()`）
2. 在 ViewSet 的 `get_queryset()` 中添加：
   ```python
   from apps.core.permissions import get_module_companies

   def get_queryset(self):
       qs = super().get_queryset()
       cids = get_module_companies(self.request.user, '<module_name>')
       if cids is not None:
           qs = qs.filter(company_id__in=cids)
       return qs
   ```
3. 确认 `action_perms` 字典中的模块名与 DB 注册的模块名一致
4. 确认 `action_perms` 使用正确赋值 `action_perms = {...}`（不是 bare `{...}`）
