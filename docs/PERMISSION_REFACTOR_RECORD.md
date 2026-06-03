# 权限管理系统重构 - 执行记录

**日期**: 2026-05-31
**版本**: v2.2.3
**状态**: ✅ 完成
**目标**: 统一使用UMP系统，废弃UCP系统

---

## 一、问题分析

### 1.1 发现的问题

| 问题 | 说明 |
|------|------|
| 两套权限系统并存 | UMP(19条) + UCP(5686条) 互不同步 |
| 数据隔离失效 | API用UCP过滤，权限检查用UMP，数据不一致 |
| 维护困难 | 两个表要同时维护，容易出错 |

### 1.2 根因

```
历史原因：分阶段开发，逐渐演变成两套系统
- UMP系统：位掩码压缩存储，适合批量授权
- UCP系统：单条记录精确控制，适合细粒度授权
```

---

## 二、重构方案

### 2.1 方案概述

```
保留：UMP表（位掩码，高效简洁）
废弃：UCP表（单条记录，数据冗余）
```

### 2.2 实施步骤

| 步骤 | 操作 | 状态 |
|------|------|------|
| 0 | 检查当前状态 | ✅ 完成 |
| 1 | 备份UCP表数据 | ✅ 完成 |
| 2 | UCP数据迁移到UMP | ✅ 完成 |
| 3 | 验证UMP表数据 | ✅ 完成 |
| 4 | 创建统一查询函数 | ✅ 完成 |
| 5 | 修改ViewSet使用新函数 | ✅ 完成 |
| 6 | 验证数据隔离 | ✅ 完成 |
| 7 | 同步43→124代码 | ✅ 完成 |
| 8 | 124数据迁移 | ✅ 完成 |

---

## 三、执行记录

### 3.1 步骤0-3：数据迁移（43服务器）

**执行时间**: 2026-05-31 16:24

**迁移前状态**:
```
UMP表: 19条
UCP表: 5686条
用户数: 3
```

**迁移后状态**:
```
UMP表: 152条 (增加133条)
UCP表: 5686条 (保留备份)
用户UMP分布:
  - yangxiaohui: 10条UMP记录
  - liubc: 74条UMP记录
  - admin: 68条UMP记录
```

**备份文件**: `docs/ucp_backup_20260531_162425.json`

### 3.2 步骤4：创建统一权限模块

**文件**: `apps/core/permissions_unified.py`

**核心函数**:
- `get_user_companies(user)` - 获取用户有权限的公司列表（基于UMP表）
- `get_module_companies(user, module_name, action)` - 获取用户在指定模块有权限的公司
- `check_permission(user, module, action)` - 检查用户权限
- `check_all_permissions(user, permissions)` - 检查多个权限
- `RoleRequired` - DRF权限类

### 3.3 步骤5：修改API层

修改以下文件使用统一的 `permissions_unified.get_user_companies`：

| 文件 | 修改内容 |
|------|----------|
| `apps/finance/views_income.py` | import改用permissions_unified |
| `apps/finance/views_expense.py` | import改用permissions_unified |
| `apps/finance/views_invoice.py` | import改用permissions_unified |
| `apps/finance/views_wage.py` | import改用permissions_unified |
| `apps/finance/views_report.py` | import改用permissions_unified |
| `apps/core/services.py` | 全部改用UMP表 |

### 3.4 步骤6：验证数据隔离（43服务器）

**验证结果**:

| 用户 | 可看公司数 | 收入记录数 | 预期 |
|------|-----------|-----------|------|
| admin | 超级用户 | 看全部219条 | ✅ |
| liubc | 4家 | 219条 | ✅ |
| yangxiaohui | 1家(绿聚能) | 63条 | ✅ |

数据隔离验证通过。

### 3.5 步骤7-8：同步124服务器

**代码同步**（43→124）:
```
rsync 8个文件到 ubuntu@124.222.227.28:/home/ubuntu/engineering-new/
```

**数据迁移**（124）:
```
迁移前: UMP=53条, UCP=280条
迁移后: UMP=94条 (增加41条)
用户UMP分布:
  - admin: 38条UMP记录
  - Leyan: 56条UMP记录
```

**备份文件**: `docs/ucp_backup_124_20260531_163207.json`

---

## 四、API文档

### 4.1 核心函数

#### get_user_companies(user)
- **功能**: 获取用户有权限的所有公司ID列表
- **返回**: 
  - `None`: 超级用户，不限制
  - `[]`: 无权限用户
  - `[id,...]`: 普通用户有权限的公司列表

#### check_permission(user, module, action)
- **功能**: 检查用户权限
- **返回**: True/False

#### get_module_companies(user, module_name, action='read')
- **功能**: 获取用户在指定模块有权限的公司
- **返回**: None/[id,...]/[]

### 4.2 位掩码定义

```python
ACTION_BITS = {
    'read':    0b0000000000000001,   # bit 0
    'create':  0b0000000000000010,   # bit 1
    'update':  0b0000000000000100,   # bit 2
    'delete':  0b0000000000001000,   # bit 3
    'approve': 0b0000000000010000,   # bit 4
    'submit':  0b0000000000100000,   # bit 5
    'pay':     0b0000000001000000,   # bit 6
    'export':  0b0000000010000000,   # bit 7
    'import':  0b0000000100000000,   # bit 8
}
```

---

## 五、后续新模块自动注册

### 5.1 模块定义

```python
# apps/core/modules.py
register_module(
    name='new_module',
    label='新模块',
    category='business',
    actions=[
        {'name': 'read', 'label': '查看', 'bit_position': 0},
        {'name': 'create', 'label': '新建', 'bit_position': 1},
    ]
)
```

### 5.2 自动生成

1. `Module`记录
2. `ModuleAction`记录
3. `Permission`记录

---

## 六、完成情况

- [x] UCP数据迁移到UMP ✅
- [x] 创建统一权限模块 ✅
- [x] 修改API层使用新函数 ✅
- [x] 验证数据隔离 ✅
- [x] 同步124服务器 ✅
- [x] 删除旧角色管理5张表（迁移0028） ✅
- [x] 修复VIEW_CATEGORY_MAP（ClientSourceViewSet 403） ✅
- [x] 修复用户管理500错误（import + related_name） ✅
- [x] 删除前端角色引用（3个模板文件） ✅
- [x] 补全UMP权限（yangxiaohui invoice/client_source） ✅

---

## 七、风险控制

| 风险 | 缓解措施 |
|------|----------|
| 数据丢失 | 已备份UCP表到JSON文件（43和124都有备份） |
| 权限遗漏 | 迁移后验证UMP表记录数 |
| API不兼容 | 修改后测试所有API |
| 服务器不同步 | 已同步代码和数据 |