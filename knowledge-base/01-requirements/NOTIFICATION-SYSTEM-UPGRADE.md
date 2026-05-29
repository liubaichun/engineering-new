# 通知系统升级需求文档

> **版本：** v2.0
> **日期：** 2026-05-17~18
> **状态：** ✅ 已实施完成
> **来源：** 需求讨论记录（飞书群聊）

---

## 一、背景与目标

当前系统有站内通知（Notification），但通知只能被动查看，无法主动推送至外部渠道。用户需要登录系统才能看到待办/提醒，容易遗漏。

**目标：** 实现站内通知自动转发至外部渠道（飞书/企微/邮件等），通知可触达个人，确保重要信息不被遗漏。

---

## 二、现有系统分析

### 2.1 已有组件

| 组件 | 说明 | 现状 |
|------|------|------|
| `core_notification` | 站内通知表 | 已有，支持多种类型（审批/任务/合同/工资等） |
| `notifications_channel` | 外部渠道配置 | 已有，支持飞书/企微/钉钉/邮件/自定义 Webhook |
| `notify_app_binding` | 用户渠道绑定 | 已有，但绑定逻辑针对群机器人，非个人 |
| `Employee` | 员工档案 | 已有，无上级关联，无飞书 open_id |
| `User` | 系统用户 | 已有 |

### 2.2 现有通知类型（core_notification.notification_type）

- `task_overdue` — 任务超时
- `approval_timeout` — 审批超时
- `approval` / `approval_pending` — 待审批
- `contract_expiring` — 合同到期
- `large_expense` — 大额支出
- `project_overdue` — 项目超时
- `wage_pending` — 工资待发放

### 2.3 现有渠道类型（notifications_channel.channel_type）

- `feishu` — 飞书群机器人
- `wecom` — 企业微信群机器人
- `dingtalk` — 钉钉群机器人
- `email` — 邮件（SMTP）
- `webhook` — 自定义 Webhook

---

## 三、业务场景分析

### 场景一：审批通知

**现状：** 审批提交后，审批人不去系统看就不知道有待审批。

**目标流程：**
```
申请人提交审批
    ↓
系统记录审批流节点
    ↓
Notification(user=审批人, type='approval', ...)
    ↓
post_save signal 触发
    ↓
查该 User 的外部渠道绑定（飞书 open_id / 邮箱）
    ↓
通过飞书会话 API 发送卡片消息：
"【待审批】来自 张三 的 费用报销申请，金额 ¥3,500，请于 2026-05-20 前处理"
```

**注意：** 飞书机器人是群发，若要发给具体个人（不走群），需要用飞书应用 `send_message` API（需要用户授权安装应用）。

---

### 场景二：任务变更 + 截止提醒

**目标流程：**
```
任务状态变更（指派/推进/完成）
    ↓
Notification(user=负责人, type='task_xxx', ...)
    ↓
通知抄送：查任务负责人 → 查其 Employee.manager
    ↓
发送两条通知：
- 负责人：飞书卡片 → "【新任务】你有一个任务：XXX，请于 5月20日 前完成"
- 项目经理：抄送通知 → "【任务更新】XXX 已指派给 李四，截止 5月20日"

定时任务（每天扫描）：
- 找出接近截止日期的任务
- 提前 1 天/3 天发提醒
- 过期未完成的发送逾期通知
```

---

### 场景三：通知范围扩展

**目标：** 一个事件可同时通知多人，支持按角色/职位决定通知谁。

```
通知规则（NotifyRule 表）：
- 审批类 → 只发审批人（当前节点）
- 任务变更 → 发负责人 + 项目经理（抄送）
- 合同到期 → 发合同负责人 + 财务主管
- 工资条 → 发员工本人（点对点）
- 系统故障 → 发所有管理员
```

---

## 四、核心数据模型变更

### 4.1 Employee 表新增字段

```python
class Employee(models.Model):
    # 现有字段略...

    # 新增字段
    manager = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='subordinates',
        verbose_name='上级主管'
    )
    feishu_open_id = models.CharField(
        max_length=64, blank=True, default='',
        verbose_name='飞书 Open ID'
    )
```

**说明：**
- `manager`：用于通知抄送链（张三的上级李四也要收到通知）
- `feishu_open_id`：用于飞书会话 API（个人消息，非群机器人）

### 4.2 User 与 Employee 关联

已有 `Employee.user` 字段（通过 `OneToOneField`），无需新增。

### 4.3 通知规则表（建议新增）

```python
class NotifyRule(models.Model):
    """通知规则配置"""
    event_type = models.CharField(max_length=30, verbose_name='事件类型')
    notify_owner = models.BooleanField(default=True, verbose_name='通知负责人')
    notify_manager = models.BooleanField(default=False, verbose_name='抄送上级的管理者')
    channel = models.CharField(max_length=20, verbose_name='优先渠道')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
```

### 4.4 NotifyAppBinding 打通个人渠道

当前 `NotifyAppBinding` 绑定的是应用（飞书/企微/钉钉），需要扩展支持：
- 个人飞书 open_id
- 个人邮箱
- 每个用户可有多个渠道偏好

---

## 五、架构设计

### 5.1 通知转发 Signal

```python
@receiver(post_save, sender=Notification)
def forward_notification(sender, instance, created, **kwargs):
    if not created:
        return

    user = instance.user
    content = instance.content
    title = instance.title

    # 1. 站内通知已写入（自动完成）

    # 2. 查用户外部渠道绑定
    bindings = NotifyAppBinding.objects.filter(user=user, is_active=True)

    # 3. 按渠道类型发送
    for binding in bindings:
        if binding.channel_type == 'feishu':
            send_feishu_personal(binding.feishu_open_id, title, content)
        elif binding.channel_type == 'email':
            send_email(user.email, title, content)

    # 4. 如果配置了抄送，通知上级
    if rule.notify_manager:
        employee = Employee.objects.filter(user=user).first()
        if employee and employee.manager:
            manager_user = employee.manager.user
            if manager_user:
                Notification.objects.create(user=manager_user, title=f"[抄送] {title}", content=content)
```

### 5.2 飞书个人消息发送（vs 群机器人）

**群机器人 Webhook（现有）：**
- 只需要 Webhook URL，无需用户授权
- 发到群里，所有人可见
- 无法指定个人

**飞书应用会话 API（需新增）：**
- 需要在飞书开放平台创建应用
- 需要用户安装并授权
- 可发给指定 open_id，点对点
- 需要处理 token 刷新

```
发送个人飞书消息流程：
1. 获取 tenant_access_token（应用凭证）
2. 构造消息体（msg_type + open_id）
3. 调用 POST /im/v1/messages?receive_id_type=open_id
4. 处理响应错误
```

### 5.3 定时任务

```
Celery 定时任务（每天 9:00 / 14:00 扫描）：

check_task_deadlines：
    找出 deadline 在 1 天内且未完成的任务
    → Notification(user=负责人, type='task_overdue', title='任务即将到期')
    → 触发 signal 转发

check_contract_expiring：
    找出合同到期前 30/7/1 天的合同
    → Notification(user=负责人, type='contract_expiring', title='合同即将到期')
    → 触发 signal 转发

check_approval_timeout：
    找出审批超时（如 7 天未处理）的审批
    → Notification(user=审批人, type='approval_timeout', title='审批超时提醒')
```

---

## 六、当前系统缺项清单

| 序号 | 缺项 | 优先级 | 说明 |
|------|------|--------|------|
| 1 | Employee.manager 字段 | P1 | 上级关联，用于抄送 |
| 2 | Employee.feishu_open_id 字段 | P1 | 个人飞书 ID |
| 3 | 通知转发 Signal | P1 | 站内通知 → 外部渠道 |
| 4 | 飞书应用会话 API | P2 | 个人消息发送（非群机器人） |
| 5 | NotifyRule 通知规则表 | P2 | 配置化通知规则 |
| 6 | Celery 定时任务 | P2 | 扫描快到期任务/合同 |
| 7 | 用户渠道偏好设置页 | P2 | 用户自选接收渠道 |
| 8 | 抄送机制 | P2 | 通知同时发给多人 |
| 9 | 站内通知列表已读/未读状态 | P3 | 当前已有字段，可优化 |
| 10 | 通知历史查看 | P3 | NotificationLog 表已有 |

---

## 七、实施计划建议

### 第一阶段（最小可行）

目标：跑通审批通知流程

1. Employee 表加 `manager` 字段
2. Employee 表加 `feishu_open_id` 字段（留空，暂不用）
3. 写通知转发 Signal（站内通知 → 邮件）
4. 邮件发送走 SMTP（邮件是个人渠道，现有能力可实现）
5. 审批模块触发通知 → 验证 Signal 打通

### 第二阶段

目标：完善飞书渠道

1. 飞书开放平台创建应用
2. 实现飞书应用 API（获取 tenant_access_token + send_message）
3. 用户绑定飞书 open_id
4. 通知 Signal 支持飞书个人消息

### 第三阶段

目标：通知智能化

1. NotifyRule 表 + 配置页面
2. Celery 定时任务（任务/合同到期提醒）
3. 抄送机制（manager 链）
4. 用户通知偏好设置

---

## 八、讨论记录

### 8.1 渠道选择

| 渠道 | 发送方式 | 接收对象 |
|------|---------|---------|
| 飞书 | 群机器人 Webhook | 群成员（广播） |
| 飞书（个人） | 会话 API | 指定 open_id（点对点） |
| 企业微信 | 群机器人 Webhook | 群成员（广播） |
| 钉钉 | 自定义机器人 | 群成员（广播） |
| 邮件 | SMTP | 指定邮箱（点对点） |

**结论：** 邮件是最简单的个人渠道，飞书群机器人最常用但只能广播。

### 8.2 绑定对象

- **渠道** 绑定在 `User`（系统账号）上，不是 Employee
- 原因：不是每个员工都有系统账号，但只要有账号就需要收通知

### 8.3 通知转发逻辑

- 站内通知（Notification）是根本，所有外部通知都基于它触发
- post_save Signal 自动监听 Notification 创建事件并转发
- 业务模块只需写 `Notification.objects.create(...)` 即可，无需关心外部渠道

### 8.4 通知范围规则

- 负责人必须收到
- 上级管理者（抄送）通过 Employee.manager 关联获取
- 可配置化（NotifyRule）

---

## 九、已实施功能（v2.0）

### 9.1 路由引擎 NotificationRouter
- 表：`notification_router`，字段：event_type / priority / channel_type / recipient_scope / custom_user_ids / company_id / is_active
- 路由逻辑：按 event_type 查找，优先公司级 fallback 全局，按 priority 排序
- 文件：`apps/notifications/models/router.py`

### 9.2 用户偏好过滤 UserNotificationPreference
- 表：`user_notification_preference`，字段：user / event_type / is_enabled / allowed_channels
- 发送前检查：若用户禁用该事件类型通知，直接跳过
- 文件：`apps/notifications/models.py`

### 9.3 动态表单 config_schema
- `ChannelListView` GET 增加 `config_schema`（required_fields + optional_fields）
- `ChannelDetailView` GET 新增（之前只有 PATCH），返回完整渠道详情含配置字段定义
- 前端可根据 channel_type 动态渲染表单

### 9.4 通知日志 API
- `GET /api/channels/logs/`：支持按 notification_type / status / start_date / end_date 过滤，分页
- `NotificationLogView`（`apps/channels/views.py`）

### 9.5 dispatch_notify 入口
- 文件：`apps/tasks/notification_service.py`
- 各业务模块调用 `dispatch_notify(event_type, context, title, content_lines)` 即可触发路由+发送

---

## 十、参考文件

- 知识库：`knowledge-base/01-requirements/NOTIFICATION-SYSTEM.md`
- 通知服务：`apps/notifications/services.py`
- 站内通知模型：`apps/core/models.py` → `Notification`
- 渠道配置模型：`apps/notifications/models.py` → `NotificationChannel`
- 员工模型：`apps/finance/models.py` → `Employee`

---

**下一步行动：**

1. 先在测试环境跑通现有通知流程（站内通知 + Signal 转发邮件）
2. 评估第一阶段改动量
3. 确认飞书开放平台应用申请流程
