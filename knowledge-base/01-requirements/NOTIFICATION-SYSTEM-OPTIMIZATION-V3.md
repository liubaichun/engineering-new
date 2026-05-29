# 通知系统优化方案 v3.0

> **版本：** v3.0  
> **日期：** 2026-05-28  
> **状态：** 待评审  
> **参考：** NOTIFICATION-SYSTEM.md（原始设计）、NOTIFICATION-SYSTEM-UPGRADE.md（v2.0升级需求）  

---

## 一、现状评估：问题根源

### 1.1 架构碎片化

当前通知相关代码分散在 **5 个模块**，各管各的，互不连通：

| 模块 | 职责 | 实际状态 |
|------|------|---------|
| `apps/channels/` | 外部渠道插件 + 发送服务 | 代码完整但凭据过期、无路由规则 |
| `apps/notifications/` | 用户通知偏好 | 仅存 `UserNotificationPreference`，基本是空壳 |
| `apps/core/email_service.py` | 审批流邮件通知 | 邮件走 console，从未真正发出 |
| `apps/core/models.py` | `Notification` 站内通知表 | 有 19 条记录，只来自 crontab 预警 |
| `apps/tasks/notification_service.py` | `dispatch_notify` + 20+ 个 `notify_xxx()` | 全部写好，但无任何业务代码调用 |

### 1.2 核心断裂（最大问题）

需求文档定的架构是：

```
业务事件 → Notification.objects.create()
                      ↓
              post_save Signal
                      ↓
           ChannelNotificationService.send()
                      ↓
              飞书 / 邮件 / 钉钉
```

**但这个 Signal 从来没有被实现过。** 导致：
- 站长通知和外部渠道推送之间没有桥梁
- 各业务模块不知道该调什么 API
- 两个通知日志没有关联（`core.Notification` 有19条，`channels.NotificationLog` 只有2条失败的）

### 1.3 基础设施未就绪

- 邮件 SMTP：`EMAIL_HOST_USER=''`，`EMAIL_BACKEND=console`——邮件从未真实发出
- 飞书 Token：已过期，返回 `Invalid access token`
- 路由规则：`NotificationRouterRule` 表 **0 条记录**，事件→渠道映射未定义
- 渠道绑定：部分用户绑定了已软删除的渠道（ID:21），绑定也无效

### 1.4 业务流程未接入通知

`tasks/notification_service.py` 里定义了 20+ 个通知函数（合同创建/审批通过/项目变更/设备借出/维修单进度等），但**没有一个被业务视图调用过**。

---

## 二、优化目标

1. **打通站内通知 → 外部渠道的桥梁**（Signal 机制）
2. **恢复渠道基础设施**（邮件 SMTP + 飞书 Token）
3. **接入关键业务事件**（审批、合同、工资、任务等）
4. **简化调用链路**——业务模块只需一行代码触发通知

---

## 三、架构设计

### 3.1 统一通知流水线

```
┌─────────────────────────────────────────────────────┐
│                    业务模块                           │
│  审批创建 / 合同到期 / 任务指派 / 工资发放 / ...     │
└──────────────────┬──────────────────────────────────┘
                   │ 只需调：notify(event_type, context)
                   ▼
┌─────────────────────────────────────────────────────┐
│                apps/notify/pipeline.py              │ ← 统一入口（新增）
│                                                     │
│  1. 写入 Notification 表（站内通知）                │
│  2. 查路由规则（NotifyRule）→ 确定渠道 & 接收人     │
│  3. 查用户偏好 → 过滤                              │
│  4. 通过 ChannelNotificationService 发送外部渠道     │
│  5. 写入 NotificationLog                           │
└─────────────────────────────────────────────────────┘
```

### 3.2 核心变化

| 现状 | 优化后 |
|------|--------|
| `dispatch_notify()` 写了没人调 | **统一入口 `notify()`**，各业务模块只需调这一个函数 |
| 外部渠道和站内通知无关联 | 每次通知**同时写入站内 + 推外部** |
| 路由规则 0 条 | **预置默认规则** + 后台可配置 |
| 5 个分散模块 | **统一到 `notify()` 流水线**，模块各自只负责一件事 |

---

## 四、分阶段实施计划

### 阶段一：基础设施恢复（1~2天）

**目标：让"能推"的通道先跑起来**

#### 1.1 配置邮件 SMTP
- 在 `.env` 或环境变量中配置真实的 `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD`
- 切换 `EMAIL_BACKEND` 从 console → smtp
- 验证：发一封测试邮件

#### 1.2 修复飞书 Token
- 飞书应用的 `app_id` / `app_secret` 已存在于渠道 ID:1 的配置中，但 token 过期
- 发送时自动检测 99991663/99991664 错误码并刷新 token——**代码里已经实现了**（`FeishuPlugin.send_message()` 第165-171行），但需要确认 refresh 后的 token 是否能成功
- 先在后台「渠道管理」→ 测试发送，确认后端连通性

#### 1.3 清理无效绑定
- 删除指向已软删除渠道（ID:21）的绑定（ID:3、ID:4）
- 保留指向活跃渠道（ID:1、ID:2）的有效绑定

#### 1.4 验证通道
- 通过后台「渠道管理」→「发送测试」，确认飞书/邮件能收到消息

---

### 阶段二：统一入口 + 路由规则（1~2天）

**目标：所有业务模块能通过同一行代码触发通知**

#### 2.1 实现 `notify()` 统一入口

```python
# 新增 apps/notify/pipeline.py

def notify(event_type, context, title, content):
    """
    统一通知入口
    
    参数：
        event_type: str — 事件类型，如 'contract_created'
        context: dict — 上下文，含 company_id, recipients, related_obj 等
        title: str — 通知标题
        content: str/list — 通知内容
    
    工作流：
        1. 写入站内 Notification 表（所有接收人各一条）
        2. 查路由规则 → 确定渠道和接收人
        3. 查用户偏好 → 过滤
        4. 通过 ChannelNotificationService 发送
        5. 记录 NotificationLog
    """
```

#### 2.2 预置默认路由规则

从需求文档提取的事件类型和默认路由：

| 事件类型 | 通知谁 | 渠道 | 优先级 |
|---------|--------|------|--------|
| `approval_created` | 审批人 | 邮件+飞书 | important |
| `approval_result` | 申请人 | 邮件+飞书 | important |
| `approval_timeout` | 审批人+上级 | 邮件+飞书 | critical |
| `task_overdue` | 负责人 | 邮件 | warning |
| `task_assigned` | 负责人 | 邮件+飞书 | normal |
| `contract_expiring_30d` | 负责人 | 邮件 | normal |
| `contract_expiring_7d` | 负责人 | 邮件+飞书 | important |
| `wage_released` | 员工本人 | 邮件 | normal |
| `project_overdue` | 项目经理 | 邮件 | warning |

**原则：**
- 邮件是保底渠道，至少确保所有人都能收到
- 飞书作为即时推送，用于紧急事项（审批、到期预警）
- 用户可在「通知偏好」页面关闭不需要的事件

#### 2.3 清理并合并 `tasks/notification_service.py`

当前的 `notify_contract_created()`、`notify_task_assigned()` 等 20+ 个函数，每个都自己处理 company_id、recipients 等逻辑。优化后全部改为：

```python
# 业务模块直接调统一入口
from apps.notify import notify

# 合同创建
notify('contract_created', {
    'company_id': contract.company_id,
    'recipients': [contract.created_by],
    'related_obj': contract,
}, title=f'合同「{contract.name}」已创建', content=[...])

# 一行搞定，不需要每个业务写一套通知逻辑
```

---

### 阶段三：业务事件接入（2~3天）

**目标：关键业务事件真正触发通知**

#### 3.1 优先级排序

| 优先级 | 业务事件 | 接入位置 | 预期效果 |
|--------|---------|---------|---------|
| P0 | **审批创建** | `ApprovalFlow` 创建时 | 审批人立即收到通知，不用登系统 |
| P0 | **审批结果** | 审批通过/拒绝时 | 申请人知道结果 |
| P1 | **合同到期** | `check_alerts` 已有但只写站内通知 | 加一行调 `notify()` 推外部 |
| P1 | **任务指派** | `Task.assignee` 变更时 | 负责人知道有新任务 |
| P2 | **工资发放** | 工资审批通过 → paid 时 | 员工收到工资条邮件 |
| P2 | **设备借出/归还** | 设备状态变更时 | 保管人知道 |
| P3 | **维修单进度** | 维修状态变更时 | 报修人知道进度 |

#### 3.2 接入方式（统一模式）

**所有业务模块** 按照同一模式接入：

```python
# 在 views.py 的 create/update 方法末尾
from apps.notify import notify

# 审批创建时
def create(self, request, *args, **kwargs):
    response = super().create(request, *args, **kwargs)
    if response.status_code == 201 and hasattr(self, 'get_notify_context'):
        ctx = self.get_notify_context(response.data)
        notify(**ctx)
    return response
```

或者用 Signal（如果业务模块已有 post_save）：

```python
@receiver(post_save, sender=ApprovalFlow)
def on_approval_created(sender, instance, created, **kwargs):
    if not created:
        return
    notify('approval_created', {
        'company_id': instance.company_id,
        'recipients': [instance.current_approver],
        'related_obj': instance,
    }, title=f'【待审批】{instance.name}', content=[...])
```

**推荐前者（view 层）**，因为 `created` 后不一定立即需要通知（用户可能有批量导入），放在 view 层让开发者显式控制。

---

### 阶段四：用户通知偏好 + 通知管理页面（持续优化）

**目标：用户能自控通知，管理员能监控通知**

#### 4.1 数据模型清理

当前 `UserNotificationPreference` 已在 `notifications/models/__init__.py`，可以继续使用。

#### 4.2 通知偏好页面

`/system/notification-preferences/` 模板已写好，但联调未验证。

#### 4.3 通知日志仪表盘

`/system/notification-logs/` 已实现，包含统计卡片、筛选、分页。

#### 4.4 通知失败告警

- 如果连续 3 次通知发送失败，给管理员发内部系统通知
- 渠道凭证过期时，在后台提示

---

## 五、风险与预案

| 风险 | 概率 | 预案 |
|------|------|------|
| 飞书 token 刷新后仍然失败 | 中 | 降级到仅邮件，飞书渠道标记为"待修复" |
| 邮件被收件方拦为垃圾邮件 | 中 | 配置 SPF/DKIM 记录，设置合适的发件名称 |
| 批量业务操作（如导入100条合同）导致同时发大量通知 | 低 | `notify()` 内部做 dedup：同一事件、同一用户、同一天不重复发 |
| Employee.manager 缺失 | 高 | 上级抄送暂不启用，等员工档案完善后开启 |
| 邮件发给无邮箱的用户 | 中 | `notify()` 检查收件人是否有邮箱/open_id，无则静默跳过 |

---

## 六、文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `apps/notify/pipeline.py` | **新增** | 统一入口 `notify()`，核心流水线 |
| `apps/notify/__init__.py` | **新增** | 包初始化 |
| `apps/notify/default_rules.py` | **新增** | 默认路由规则（迁移数据用） |
| `apps/core/email_service.py` | 精简 | 去掉旧逻辑，调新 `notify()` |
| `apps/tasks/notification_service.py` | 精简/保留 | 保留 `dispatch_notify()` 作兼容，重写 `notify_xxx()` 调新入口 |
| `apps/channels/views.py` | 不动 | 已有测试发送功能 |
| `apps/channels/services.py` | 微调 | 确保 `ChannelNotificationService.send()` 兼容新入口 |
| `config/settings.py` | 改 | `EMAIL_BACKEND=smtp` + 从环境变量读配置 |

---

## 七、验收标准

1. ✅ 管理员可以在后台「通知渠道」添加/测试渠道
2. ✅ 创建一个审批后，审批人立即收到邮件/飞书通知
3. ✅ 员工能在「通知偏好」关闭不需要的事件
4. ✅ 通知日志能看到每次发送记录
5. ✅ 5分钟为一个超时轮询周期，超时审批触发提醒
