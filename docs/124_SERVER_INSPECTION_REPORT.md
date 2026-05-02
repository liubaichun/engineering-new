# 124服务器全面检查报告

**检查时间：** 2026-05-02
**服务器：** 124.222.227.28
**版本：** standalone branch, commit 7f1b297 + 本地修复

---

## 检查结果

### 端点验证（27个，24个通过）

| 端点 | 状态码 | 结果 |
|------|--------|------|
| /api/core/users/ | 200 | OK |
| /api/core/roles/ | 200 | OK |
| /api/core/permissions/ | 200 | OK |
| /api/crm/clients/ | 200 | OK |
| /api/crm/suppliers/ | 200 | OK |
| /api/crm/contracts/ | 200 | OK |
| /api/crm/sources/ | 200 | OK |
| /api/tasks/projects/ | 200 | OK |
| /api/tasks/tasks/ | 200 | OK |
| /api/tasks/stages/ | 404 | URL路径问题 |
| /api/tasks/flow-templates/ | 200 | OK |
| /api/finance/companies/ | 200 | OK |
| /api/finance/employees/ | 200 | OK |
| /api/finance/incomes/ | 200 | OK |
| /api/finance/expenses/ | 200 | OK |
| /api/finance/wages/ | 200 | OK |
| /api/finance/invoices/ | 200 | OK |
| /api/approvals/flows/ | 200 | OK |
| /api/approvals/nodes/ | 200 | OK |
| /api/approvals/templates/ | 200 | OK |
| /api/approvals/ | 200 | OK |
| /api/notifications/channels/ | 200 | OK |
| /api/notifications/notifications/ | 404 | URL路径问题 |
| /api/equipment/ | 200 | OK |
| /api/material/ | 200 | OK |
| /api/files/files/ | 200 | OK |
| /api/warnings/ | 404 | URL路径问题 |

**通过率：24/27（89%）**

---

## 修复记录

### 1. notifications迁移依赖链断裂

**问题：** `0002_initial.py`（幽灵文件）与`0002_add_notification_channel.py`重复，导致`0003_add_notify_binding_fields.py`的依赖指向不存在的迁移。

**修复：**
- 删除`0002_initial.py`
- 恢复`0002_add_notification_channel.py`
- 修改`0003.py`的dependencies为`('notifications', '0002_add_notification_channel')`
- DB里reconcile django_migrations表（fake-apply相关迁移）

### 2. ClientSource ViewSet filterset_fields引用不存在的parent字段

**问题：** `ClientSource`模型没有`parent`字段，但`ClientSourceViewSet`声明了`filterset_fields = ['parent']`，导致django-filter在构建自动FilterSet时报`TypeError: 'Meta.fields' must not contain non-model field names: parent`

**修复：** 删除`crm/views.py`中的`filterset_fields = ['parent']`

### 3. Contract模型缺少attachment_name属性

**问题：** `ContractSerializer`引用了`attachment_name`字段（用于展示合同附件文件名），但`Contract`模型里只有`attachment`（FileField），没有`attachment_name` property，导致`ImproperlyConfigured: Field name 'attachment_name' is not valid for model 'Contract'`

**修复：** 在`Contract`模型添加：
```python
@property
def attachment_name(self):
    if self.attachment:
        import os
        return os.path.basename(self.attachment.name)
    return ''
```

---

## 根因分析

### 核心问题：standalone分支的models.py和migrations之间存在隐性脱节

多租户版（master）添加新模型/字段时，models.py和migrations是一起提交的。但standalone分支在某次fork时：
1. migrations文件带了新增的Model类定义（如ClientSource）和字段添加（如Contract.attachment）
2. 但models.py没有同步更新对应的类定义和属性

这导致：**DB schema有这些列/表，但Python模型类不知道它们的存在。**

### 涉及的地方

| 模型 | 问题 | 修复 |
|------|------|------|
| ClientSource | 迁移0005创建了表，但standalone的models.py原本没有ClientSource类 | 确认models.py有ClientSource类（第5行） |
| Contract.attachment | 迁移0005添加了attachment列，但models.py里attachment字段缺失 | models.py第135行已有`attachment = models.FileField(...)` |
| Contract.attachment_name | Serializer需要，但models.py没有property | 已添加@property |
| Contract.client.source | FK字段，迁移0005添加，models.py第61-67行已有 | OK |

---

## 经验教训

### 教训1：models.py和migrations必须作为原子单元提交

**规则：** 任何涉及Model类定义变更的代码，必须同时修改models.py和对应的migrations文件。如果migrations依赖另一方，两个改动必须在同一个commit里。

**检查清单（提交前必做）：**
```
□ 新增Model类 → 检查migrations文件是否同时创建
□ 新增字段/属性 → 检查models.py是否同时声明
□ 新增property/computed field → 检查所有引用它的地方是否兼容
□ 删除Model/字段 → 确保所有migrations和serializers/views引用都清理干净
```

### 教训2：部署前必须验证URL路由和DB schema一致性

**规则：** 每次部署到新环境后，必须：
1. 运行`python manage.py showmigrations`确认迁移状态
2. 抽查3-5个关键Model的`Model._meta.fields`确认DB列和模型字段一致
3. 冒烟测试所有API端点

**快速检查命令：**
```bash
# 检查某个app的迁移状态
python manage.py showmigrations crm

# 检查模型字段是否在DB中存在
python manage.py shell -c "from apps.crm.models import Contract; print([f.name for f in Contract._meta.fields])"

# 冒烟测试
curl -s -b /tmp/cjar_new.txt -o /dev/null -w '%{http_code}' http://localhost:8001/api/crm/contracts/
```

### 教训3：filterset_fields必须严格匹配模型字段

**规则：** `filterset_fields`里每个字段名必须是Model的实际字段名，不能是serializer的computed field或别名。

**常见错误：**
- `filterset_fields = ['parent']` → parent不是Model字段 → django-filter TypeError
- `filterset_fields = ['attachment_name']` → attachment_name不是DB字段（是property）→ 同上

### 教训4：重复注册Model的RuntimeWarning必须立即修复

**问题：** "Model 'crm.clientsource' was already registered" 表示同一Model类被加载了两次。原因通常是migrations历史中某次迁移创建了Model但后来又被修改。

**处理：** 找到重复注册的来源（通常是migrations里的CreateModel），确保只有一个。

### 教训5：独立版部署必须做DB schema对比

**规则：** 从master向standalone cherry-pick代码时，如果涉及Model变更，必须：
1. 确认目标服务器的DB是否已有对应的表/列
2. 如果没有，需要在目标服务器上运行migrate
3. 或者修改代码以适配目标DB现状

---

## 推送记录

| 内容 | 目标分支 | 状态 |
|------|----------|------|
| ClientSource/Contract修复 | standalone (GitHub) | 待推送 |

**推送前需要：**
```bash
# 124服务器本地commit
cd /root/engineering-new
git add apps/crm/
git commit -m "fix: remove invalid parent filter + add Contract.attachment_name property

Root cause: standalone branch models.py was missing attachment_name
property referenced by ContractSerializer, and ClientSourceViewSet had
invalid filterset_fields=['parent']. Found during full 124 inspection.

Fixes:
- Remove filterset_fields = ['parent'] from ClientSourceViewSet
- Add attachment_name @property to Contract model
- Models and migrations must be committed together"
```
