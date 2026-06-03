# 124服务器权限实现差异分析

**编制时间**：2026-05-31
**对比服务器**：43服务器 (43.156.139.37) vs 124服务器 (124.222.227.28)

---

## 一、数据表对比总览

| 数据表 | 43服务器 | 124服务器 | 差异 |
|--------|----------|------------|------|
| Permission | 242条 | 242条 | ✅ 相同 |
| Module | 34条 | 33条 | ❌ 缺少1条 |
| approval权限 | 23条 | 23条 | ✅ 相同 |

---

## 二、Permission 表对比

###权限分布（完全相同）

| Category | 43服务器 | 124服务器 |
|----------|----------|------------|
| approval | 23 | 23 |
| bank | 19 | 19 |
| crm | 32 | 32 |
| equipment | 7 | 7 |
| files | 8 | 8 |
| finance | 42 | 42 |
| material | 5 | 5 |
| notifications | 6 | 6 |
| project | 12 | 12 |
| purchasing | 22 | 22 |
| repair | 4 | 4 |
| system | 19 | 19 |
| task | 43 | 43 |
| **总计** | **242** | **242** |

### approval 权限码（完全相同）

```
approval:approval:approve
approval:approval:create
approval:approval:delete
approval:approval:read
approval:approval:update
approval:approve
approval:create
approval:delete
approval:flow:approve
approval:flow:create
approval:flow:delete
approval:flow:read
approval:flow:update
approval:manage
approval:node:create
approval:node:delete
approval:node:read
approval:node:update
approval:read
approval:template:manage
approval:template:read
approval:template:update
approval:update
```

---

## 三、Module 表对比

| Module.name | Category | 43服务器 | 124服务器 | 状态 |
|-------------|----------|----------|----------|------|
| approval | approval | ✅ | ✅ |相同 |
| customer | crm | ✅ | ✅ | 相同 |
| contract | crm | ✅ | ✅ | 相同 |
| supplier | crm | ✅ | ✅ | 相同 |
| opportunity | crm | ✅ | ✅ | 相同 |
| stats | data | ✅ | ✅ | 相同 |
| notification | data | ✅ | ✅ | 相同 |
| file | files | ✅ | ✅ | 相同 |
| wage | finance | ✅ | ✅ | 相同 |
| employee | finance | ✅ | ✅ | 相同 |
| social_security | finance | ✅ | ✅ | 相同 |
| income | finance | ✅ | ✅ | 相同 |
| expense | finance | ✅ | ✅ | 相同 |
| invoice | finance | ✅ | ✅ | 相同 |
| report | finance | ✅ | ✅ | 相同 |
| budget | finance | ✅ | ✅ | 相同 |
| bank | finance | ✅ | ✅ | 相同 |
| material | operations | ✅ | ✅ | 相同 |
| equipment | operations | ✅ | ✅ | 相同 |
| repair | operations | ✅ | ✅ | 相同 |
| project | project | ✅ | ✅ | 相同 |
| gantt | project | ✅ | ✅ | 相同 |
| taskboard | project | ✅ | ✅ | 相同 |
| **flow_template** | **project** | ✅ | ❌ | **124缺少** |
| purchase_request | purchasing | ✅ | ✅ | 相同 |
| purchase_order | purchasing | ✅ | ✅ | 相同 |
| purchase_receive | purchasing | ✅ | ✅ | 相同 |
| company | system | ✅ | ✅ | 相同 |
| user | system | ✅ | ✅ | 相同 |
| audit_log | system | ✅ | ✅ | 相同 |
| setting | system | ✅ | ✅ | 相同 |
| channel | system | ✅ | ✅ | 相同 |
| api_doc | system | ✅ | ✅ | 相同 |
| permission_matrix | system | ✅ | ✅ | 相同 |

---

## 四、VIEW_CATEGORY_MAP 对比

| ViewSet | 43服务器 | 124服务器 | 状态 |
|---------|----------|----------|------|
| ApprovalFlowViewSet | ('approval', 'approval') | ('approval', 'approval') | ✅ 相同 |
| ApprovalNodeViewSet | ('approval', 'approval') | ('approval', 'approval') | ✅ 相同 |
| ApprovalTemplateViewSet | ('approval', 'approval') | ('approval', 'approval') | ✅ 相同 |
| BudgetViewSet | ('finance', 'budget') | ('finance', 'budget') | ✅ 相同 |
| FileCategoryViewSet | ('files', 'file') | ('files', 'file') | ✅ 相同 |
| CompanyFileViewSet | ('files', 'file') | ('files', 'file') | ✅ 相同 |
| SocialRecordViewSet | ('finance', 'social_security') | ('finance', 'social_security') | ✅ 相同 |
| TaskViewSet | ('project', 'taskboard') | ('project', 'taskboard') | ✅ 相同 |

---

## 五、结论

### 已同步完成 ✅
1. **Permission 表**：242条权限码完全一致
2. **approval 权限码**：23条完全一致
3. **VIEW_CATEGORY_MAP**：所有 ViewSet 映射配置一致
4. **permissions.py 代码**：ApprovalFlow/Node/Template 三个 ViewSet 已修复为 ('approval', 'approval')

### 待修复 ⚠️
1. **Module 表**：124服务器缺少 `flow_template -> project` 模块
   - 影响：`project:flow_template:*` 相关功能
   - 修复方案：插入缺失的 Module记录

---

## 六、修复状态

### ✅ 已修复：Module 表缺少 flow_template

在124服务器已成功创建缺失的 Module 记录：
```python
Module.objects.create(name='flow_template', category='project', description='流程模板', is_active=True)
```

**修复后验证**：124服务器 Module 总数从 33 条增加到 34 条，与43服务器完全一致。

---

## 七、最终结论

### 两台服务器权限系统配置已完全同步 ✅

| 检查项 | 43服务器 | 124服务器 | 状态 |
|--------|----------|----------|------|
| Permission 表 | 242条 | 242条 | ✅ 一致 |
| Module 表 | 34条 | 34条 | ✅ 一致 |
| VIEW_CATEGORY_MAP | 完整 | 完整 | ✅ 一致 |
| permissions.py | 修复后 | 修复后 | ✅ 一致 |

### 权限系统三层架构完全兼容
1. **认证层**：SessionAuthentication ✅
2. **权限层**：RoleRequired + VIEW_CATEGORY_MAP ✅
3. **数据层**：UserModulePermission + company_id 过滤 ✅
