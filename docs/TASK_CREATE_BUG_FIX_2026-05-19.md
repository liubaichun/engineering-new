# 任务创建400错误修复记录

**日期**: 2026-05-19
**影响**: 新建任务保存失败（编辑任务正常）
**状态**: ✅ 已修复

---

## 1. 问题现象

- 任务看板 → 新建任务 → 填写信息 → 点击保存 → 返回 `400 Bad Request`
- 浏览器控制台: `保存任务失败: Error: 保存失败`
- 网络面板: `POST /api/tasks/tasks/ 400`

---

## 2. 根因分析

**DRF Serializer 字段类型不匹配**

| 组件 | 字段类型 | 发送的值 | 期望的值 |
|------|---------|---------|---------|
| 前端 `flow_board.html` | `assignee` value (username字符串) | `"admin"` | - |
| 后端 `TaskCreateSerializer` | 隐式 `PrimaryKeyRelatedField` | `"admin"` (str) | integer pk |

**数据流**:
```
前端 loadUsers()
  → <option value="admin">  ← username作为value
  → saveTask() 读取 document.getElementById('taskAssignee').value
  → payload: { assignee: "admin" }
  → POST /api/tasks/tasks/
  → TaskCreateSerializer.assignee = PrimaryKeyRelatedField
  → "admin" is not a valid integer → 400 Bad Request
```

**关键发现**: `TaskSerializer`（编辑/PATCH）之前已修复，用的是 `SlugRelatedField`；但 `TaskCreateSerializer`（新建/POST）一直没修。

---

## 3. 修复方案

**文件**: `apps/tasks/views.py`

**修改前**:
```python
class TaskCreateSerializer(serializers.ModelSerializer):
    company_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Task
        fields = [ ..., 'assignee', ...]
```

**修改后**:
```python
class TaskCreateSerializer(serializers.ModelSerializer):
    company_id = serializers.IntegerField(read_only=True)
    assignee = serializers.SlugRelatedField(
        queryset=get_user_model().objects.all(), slug_field='username',
        required=False, allow_null=True
    )

    class Meta:
        model = Task
        fields = [ ..., 'assignee', ...]
```

**为什么 `validate_assignee` 不够**:
- `validate_<field>` 是 object-level 钩子，在 `PrimaryKeyRelatedField` 的类型检查**之后**才执行
- 字符串在到达 `validate_assignee` 之前就被 `PrimaryKeyRelatedField` 拒绝了
- 必须改字段类型为 `SlugRelatedField` 才能从根本上解决

---

## 4. 影响范围

| Serializer | 操作 | assignee类型 | 状态 |
|-----------|------|------------|------|
| `TaskSerializer` | 编辑(PATCH) | SlugRelatedField | ✅ 之前已修复 |
| `TaskCreateSerializer` | 新建(POST) | PrimaryKeyRelatedField(隐式) | ✅ 本次修复 |

---

## 5. 服务器修复记录

| 服务器 | 文件路径 | 修复方式 | 重启 |
|--------|---------|---------|------|
| 43 (43.156.139.37) | `/root/engineering-new/apps/tasks/views.py` | 直接patch | `kill -HUP` → 强制重启daemon |
| 124 (124.222.227.28) | `/home/ubuntu/engineering-new/apps/tasks/views.py` | Python脚本+SSH | `kill -HUP master_pid` |

---

## 6. 验证方法

### 6.1 Django Shell测试
```python
from apps.tasks.views import TaskCreateSerializer
# ... setup context ...
data = {'title': 'Test', 'code': 'TEST-XXX', 'project': 20, 'assignee': 'admin', ...}
serializer = TaskCreateSerializer(data=data, context=context)
assert serializer.is_valid(), serializer.errors  # 不再报 type_error
```

### 6.2 HTTP API测试
```bash
curl -X POST http://localhost:8001/api/tasks/tasks/ \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: <token>" \
  --cookies "sessionid=<sid>" \
  -d '{"title":"Test","code":"TEST","project":20,"assignee":"admin","priority":"medium","status":"pending"}'
# 期望: 201 Created
```

### 6.3 浏览器UI测试
- 打开任务看板 → 新建任务 → 选择处理人 → 保存 → 确认任务出现在列表

---

## 7. 经验教训

1. **同类问题要举一反三**: 修了 `TaskSerializer` 的同样问题，却忽略了 `TaskCreateSerializer`
2. **HUP重载不一定生效**: gunicorn的HUP信号对代码修改不总是可靠，修改关键代码后建议强制重启daemon进程
3. **Serializer字段默认行为要警惕**: `PrimaryKeyRelatedField` 是ForeignKey字段的默认隐式序列化器，改动字段行为时要显式声明
4. **两台服务器代码不同步**: 43和124的git HEAD不同，修复时要确认两台服务器都用同一版本

---

## 8. 相关文件

- `apps/tasks/views.py` — `TaskCreateSerializer` 定义（修复位置）
- `apps/tasks/models.py` — `Task` 模型
- `templates/tasks/flow_board.html` — 任务看板前端模板
