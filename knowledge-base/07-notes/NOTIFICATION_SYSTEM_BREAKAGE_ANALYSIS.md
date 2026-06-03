# 通知系统全面断裂分析报告

**分析时间：** 2026-06-01
**分析人：** hermes-a002
**影响范围：** 所有外部渠道推送（飞书/企微/钉钉/邮件）

---

## 一、三层架构总览

```
第1层 业务事件触发层
  ├── check_alerts.py（定时任务） → 7类预警
  ├── check_task_timeouts.py（定时任务） → 阶段超时通知
  ├── email_service.py（审批流） → 审批创建/通过/驳回/催办
  └── notification_service.py（业务模块） → 任务/合同/设备/维修/项目变更
       ↓
第2层 路由分发层 ★ HERE BE DRAGONS ★
  └── dispatch_notify() → 解析用户 → 找渠道 → 发消息
       ↓
第3层 渠道基础设施层
  └── channels/services.py: send_notification() → 调插件API
       ├── 飞书插件（正常）
       ├── 企业微信插件（正常）
       ├── 钉钉插件（正常）
       └── 邮件（走 Django send_mail）
```

## 二、断裂点诊断

### 断裂点1：`apps/tasks/notification_service.py`

| 位置 | 代码 | 问题 |
|:----|:-----|:-----|
| 第14行 | `from apps.channels.services import ChannelNotificationService` | `ChannelNotificationService` 类已在重写时删除 |
| 第54行 | `ChannelNotificationService._send_via_channel(user, channel, ...)` | 调用不存在的方法 |

影响范围：所有调用 `dispatch_notify()` 的业务模块

**调用链：**
- `notify_task_created()` → dispatch_notify ❌
- `notify_task_completed()` → dispatch_notify ❌
- `notify_stage_completed()` → dispatch_notify ❌
- `notify_flow_completed()` → dispatch_notify ❌
- `notify_stage_timeout()` → dispatch_notify ❌（定时任务每小时执行）

### 断裂点2：`apps/core/email_service.py`

| 位置 | 代码 | 问题 |
|:----|:-----|:-----|
| 第113行 | `from apps.channels.services import ChannelNotificationService` | 同上，类不存在 |
| 第115行 | `ChannelNotificationService.send(user, title, content, ...)` | 调用不存在的方法 |

影响范围：审批流关键节点的多渠道通知

**调用链：**
- `notify_approval_created()` → `_send_to_binding_channel()` ❌
- `notify_approval_result()` → `_send_to_binding_channel()` ❌
- `notify_approval_urge()` → `_send_to_binding_channel()` ❌

### 断裂点3：`apps/notifications/services.py`

仅有一行残留注释，无实际代码——该文件已废弃。

### 断裂点根因

通知系统在 V5/V6 优化迭代中，`channels/services.py` 被重写：
- **旧方案：** `ChannelNotificationService` 类（classmethod 方式）
- **新方案：** `send_notification()` 函数（纯函数方式，更简洁）

重写后删除了旧类，但调用方未同步更新，导致两处 `import` 断裂。

## 三、修复方案

### 修复一：`notification_service.py`（P0）

**策略：** 保留用户解析+偏好检查逻辑，将调用 `_send_via_channel` 改为调用 `send_notification()`

**改动：**
1. `import ChannelNotificationService` → `import send_notification`
2. 内层循环调用 `_send_via_channel` → 统一调用 `send_notification(company_id, title, content, user_ids=[...])`
3. `ChannelPlugin` → `Channel`（向后兼容别名，无实际影响）

### 修复二：`email_service.py`（P0）

**策略：** `_send_to_binding_channel()` 本地获取 company_id，调 `send_notification()`

**改动：**
1. `import ChannelNotificationService` → `import send_notification`
2. `ChannelNotificationService.send(...)` → `send_notification(company_id, title, content, user_ids=[binding.user_id], notification_type='approval')`

### 影响评估

| 修复 | 文件 | 行数变化 | 风险 |
|:----|:-----|:--------|:-----|
| 修复一 | notification_service.py | ~20行（删约15行+增5行） | 低——函数签名适配，保留所有已有逻辑 |
| 修复二 | email_service.py | ~5行（删3行+增5行） | 低——仅替换调用方式 |

### 修复后效果预期

- ✅ 定时任务 `check_task_timeouts.py` 超时检测 → 通知用户飞书/企微/钉钉
- ✅ 定时任务 `check_alerts.py` 7类预警 → 通知相关用户
- ✅ 审批创建/通过/驳回/催办 → 多渠道推送
- ✅ 任务/合同/设备/维修/项目变更 → 通知负责人
- 内部"我的通知"记录不受影响（独立写入数据库）

---

## 四、验证方案

```
验证1: 导入测试
  → Python 导入不报错

验证2: URL测试（验证审批通知链路）
  → 跑一个审批创建，检查日志是否出现 [Notify] Sent via ...

验证3: 定时任务触发测试
  → 手动触发 check_task_timeouts.py，检查日志输出
  → 检查 NotificationLog 表是否有新记录

验证4: 端到端验证
  → 在 43 系统上创建一个审批，观察飞书/企微是否收到消息
  → 注意：飞书密钥已过期仅企微可用
```

---

## 五、事后总结

### 为什么会断

通知系统经历了 V3→V4→V5→V6 四轮优化迭代，每轮都改动了 `channels/services.py`：
- V3：引入 `ChannelNotificationService` 类
- V4：增加群发/广播模式
- V5：重写为 `send_notification()` 函数
- V6：删除旧类

问题在于：**每次迭代都改了接口，但没有同步更新所有调用方。** V6 删除了 `ChannelNotificationService` 类，但 `notification_service.py` 和 `email_service.py` 未跟进。

### 教训

```
1. 重写公共接口时，必须一次性更新所有引用方
2. 删除旧类前，用 grep 确认无其他文件引用
3. 重构前后应执行完整导入测试
4. 外部渠道推送没有端到端测试用例——这是不可接受的
```

### 改进建议

- 在 CI/CD 流程中加入导入完整性检查（`python -c "import apps.tasks.notification_service"`）
- 为关键通知链路编写端到端测试
- API 文档需标注每层接口的依赖关系
