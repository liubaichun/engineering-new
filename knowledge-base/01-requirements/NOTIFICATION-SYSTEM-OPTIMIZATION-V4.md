# 通知系统优化方案 v4.0

> **版本：** v4.0
> **日期：** 2026-05-28
> **参考：** NOTIFICATION-SYSTEM.md（原始设计）、NOTIFICATION-SYSTEM-UPGRADE.md（v2.0需求）

---

## 一、设计理念（两句话）

```
1. 邮件：留配置入口，用户配好就能用
2. IM 捆绑：跟飞书/钉钉/微信绑上，重要信息实时推
```

---

## 二、通知分类

| 类别 | 说明 | 发送方式 | 示例 |
|:----|:-----|:---------|:-----|
| **群通知** | 跟所有人相关，广播出去 | 发到群机器人（飞书群/企微群等） | 系统维护公告、月底关账提醒、公司通告 |
| **个人通知** | 跟具体的人相关，点对点发 | 发到个人的绑定渠道（飞书/微信/邮箱） | 张三的审批待办、李四的任务指派、王五的合同到期 |

---

## 三、配置方式（后台页面可配）

### 3.1 群通知配置

```
管理员在后台：
  1. 添加一个群机器人渠道（飞书群 Webhook URL / 企微群 Webhook URL）
  2. 在「群通知配置」里选：
     - 这个群负责哪些事件（如：系统公告、财务通告）
     - 哪些公司用这个群

系统发群通知时 → 直接 POST 到该群的 Webhook → 群内所有人都看到
```

### 3.2 个人通知配置

```
管理员/用户在后台：
  1. 管理员配置通知渠道（飞书应用 / 钉钉应用 / 邮件 SMTP）
  2. 个人绑定自己的渠道：
     - 飞书：扫码授权，自动获取 open_id
     - 微信：填入 PushPlus Token（第三方服务）
     - 邮箱：填自己的邮箱地址

系统发个人通知时 → 查该用户的绑定 → 推到他绑定的渠道
```

### 3.3 事件→类别 映射配置

管理员在后台指定每个事件属于群通知还是个人通知：

```
事件类型             通知类别    说明
─────────────────────────────────────────
系统公告             群通知      所有人都要知道的
财务月结提醒          群通知      跟公司相关的通知

审批待办             个人通知    推给当前审批人
审批结果             个人通知    推给申请人
任务指派             个人通知    推给负责人
合同到期             个人通知    推给合同负责人
工资发放             个人通知    推给员工本人
设备借出             个人通知    推给保管人
维修完成             个人通知    推给报修人
```

---

## 四、数据流

### 4.1 群通知流程

```
管理员配置好群机器人渠道（Webhook URL）
        ↓
业务发生群通知事件（如：系统公告）
        ↓
系统查「事件→类别映射」→ 属于群通知
        ↓
查「群通知配置」→ 找到对应公司的群机器人 Webhook
        ↓
POST 消息到群机器人 → 群里所有人都收到
        ↓
记录 NotificationLog
```

### 4.2 个人通知流程

```
用户绑定好渠道（飞书 open_id / 微信 PushPlus Token / 邮箱）
        ↓
业务发生个人通知事件（如：审批创建）
        ↓
系统查「事件→类别映射」→ 属于个人通知
        ↓
确定接收人（审批节点的人 / 任务负责人 / 合同负责人 等）
        ↓
查每个接收人的绑定 → 查用户偏好
        ↓
按渠道发送（飞书消息 / 微信推送 / 邮件）
        ↓
记录 NotificationLog
```

### 4.3 整体架构

```
                    ┌─────────────────┐
                    │   配置管理页面    │
                    │  ┌───────────┐  │
                    │  │ 群通知配置  │  │
                    │  │ 个人绑定管理│  │
                    │  │ 事件类别映射│  │
                    │  │ 邮件SMTP配置│  │
                    │  │ 通知日志查看│  │
                    │  └───────────┘  │
                    └────────┬────────┘
                             │ 配置读取
                             ▼
┌──────────────────────────────────────────────┐
│          通知路由 & 发送引擎                   │
│                                               │
│  收到 notify(event_type, recipients, ...)     │
│      ↓                                        │
│  查事件类别 → 群通知 or 个人通知               │
│      ↓                                        │
│  群通知 → 查公司群机器人 Webhook → 发群消息    │
│  个人通知 → 查用户绑定 → 逐个渠道发送          │
│      ↓                                        │
│  记录 NotificationLog                          │
└──────────────────────────────────────────────┘
```

---

## 五、关于微信绑定的可行性

当前代码已经有 **WechatPlugin**（`apps/channels/plugins/wechat/plugin.py`），走的是 **PushPlus**（pushplus.plus）第三方服务。

| 问题 | 答案 |
|:----|:-----|
| 能不能绑个人微信？ | 能。PushPlus 是微信推送服务，用户关注公众号，填 token 绑定 |
| 怎么配置？ | 后台添加「微信」渠道，填入 PushPlus Token |
| 怎么发？ | POST 到 PushPlus API → 用户微信收到消息 |
| 有什么限制？ | PushPlus 免费版每天 200 条，内容 1 分钟内可达，足够用于审批/合同预警 |
| 有没有替代方案？ | Server酱（sct.ftqq.com）、WxPusher 都可以做同样的事 |

流程：

```
用户：
  1. 关注 PushPlus 公众号
  2. 在 PushPlus 里拿到个人 Token
  3. 在系统「通知设置」→ 添加微信绑定 → 填入 Token
  4. 绑定完成

系统：
  业务事件 → 查用户绑定的微信 Token
           → POST 到 PushPlus API
           → 用户手机微信收到消息
```

---

## 六、现状 vs 目标差距

| 现状 | 目标 | 差距 |
|:----|:----|:-----|
| `ChannelPlugin` 模型已有 — 含 channel_type, config, is_active | 需区分"群机器人类"和"个人绑定类" | 加一个字段 `usage`，值为 `broadcast` 或 `personal` |
| `ChannelBinding` 模型已有 — 用户绑定关系 | 需要区分绑定的是群还是个人 | 已有 `user` + `channel` 关系，个人绑定没问题 |
| 邮件配置通过环境变量，用户不可配 | 用户可在后台配 SMTP | 需要一个配置页面和对应的存储 |
| 事件→类别映射不存在 | 管理员可配哪个事件是群通知还是个人通知 | 需要新建配置表 + 配置页面 |
| `ChannelNotificationService.send(user, title, content)` 已存在 | 需要同时支持群发（broadcast）和点对点（personal） | `send_channel_broadcast()` 已能发群，`send()` 已能发个人 |

---

## 七、实施路径

### 第一步：渠道区分（加 usage 字段 + 清理）

给 `ChannelPlugin` 加一个 `usage` 字段：

```python
class ChannelPlugin(models.Model):
    USAGE_CHOICES = [
        ('broadcast', '群通知'),
        ('personal', '个人通知'),
    ]
    usage = models.CharField('用途', max_length=20, choices=USAGE_CHOICES, default='personal')
    # ... 其他已有字段不变
```

然后：
- 现有的渠道 ID:1（飞书，有 webhook_url + app_id）→ usage='broadcast'（用 webhook 发群）
- 现有的渠道 ID:2（钉钉，只有 app_key/app_secret）→ usage='personal'（发个人消息）
- 已删除的 4 个渠道：保持已删除状态不变

难度：★（加字段 + migration）

### 第二步：邮件 SMTP 可在后台配置

新建一个配置模型或利用已有的 `SystemSetting`：

```python
# 在 config/settings.py 里：优先读数据库配置，没有则读环境变量
def get_email_config():
    # 从 SystemSetting 表读，key='smtp_config'
    # 返回 {host, port, user, password, from_email}
```

通知发送时一律从数据库配置读取 SMTP 参数，不依赖环境变量。

难度：★★（需要改 settings.py 和发送逻辑）

### 第三步：事件→类别映射表 + 配置页面

```python
class EventNotifyConfig(models.Model):
    """事件通知配置"""
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    event_type = models.CharField('事件类型', max_length=50)
    notify_mode = models.CharField('通知模式', max_length=20, choices=[
        ('broadcast', '群通知'),
        ('personal', '个人通知'),
        ('disabled', '不通知'),
    ], default='personal')
    # 如果是群通知，指定走哪个群渠道
    broadcast_channel = models.ForeignKey(
        ChannelPlugin, on_delete=models.SET_NULL,
        null=True, blank=True, limit_choices_to={'usage': 'broadcast'},
    )
    is_active = models.BooleanField(default=True)
```

配置页面放在 `/system/notification-router/`（已有模板，改造即可）。

难度：★★★（模型 + 页面 + 接口）

### 第四步：修复通道连通性

| 任务 | 操作 |
|:----|:-----|
| 飞书 Webhook URL 是否有效 | 去飞书群检查机器人是否还在，测试发送 |
| 飞书 App Token 是否过期 | 重新获取 token，测试发送个人消息 |
| PushPlus / 微信 | 用户关注公众号 + 获取 token，后台添加微信渠道 |
| 邮件 SMTP | 后台填 SMTP 配置 → 测试发送 |

难度：★（人工操作 + 后台点点）

### 第五步：业务事件接入

逐个业务模块，在关键位置加一行：

```python
from apps.channels.services import send_channel_broadcast  # 群通知
from apps.channels.services import ChannelNotificationService  # 个人通知

# 以审批创建为例：
def create(self, request, *args, **kwargs):
    response = super().create(request, *args, **kwargs)
    if response.status_code == 201:
        instance = self.get_object()
        # 查事件配置 → 确定是群发还是个人
        from apps.notify.dispatcher import dispatch
        dispatch('approval_created', instance, request)
    return response
```

难度：★★～★★★（每个事件约 5 行代码，接入 10 个事件约半天）

---

## 八、文件变更总览

| 文件 | 操作 | 说明 |
|:----|:-----|:-----|
| `apps/channels/models.py` | 改 | `ChannelPlugin` 加 `usage` 字段 |
| `apps/channels/migrations/` | 新增 | 加字段 + 类型转换 |
| `apps/notify/dispatcher.py` | **新增** | `dispatch()` 统一调度——查事件类别→群发 or 个人 |
| `apps/notify/models.py` | **新增** | `EventNotifyConfig` 事件→类别映射表 |
| `apps/notify/views.py` | **新增** | 配置 API |
| `apps/notify/__init__.py` | **新增** | 包初始化 |
| `templates/system/notification_router.html` | 改 | 改成事件→类别映射配置页面 |
| `templates/system/notification_channels.html` | 改 | 加 usage 选择（群通知/个人通知） |
| `config/settings.py` | 改 | 支持读数据库邮件配置 |
| `apps/notifications/views.py` | 保留 | `UserNotificationPreferenceView` 保留 |

---

## 九、验收清单

1. ✅ 管理员在后台添加群机器人渠道 → 测试发送 → 群里收到消息
2. ✅ 用户在后台绑微信（PushPlus Token）→ 测试发送 → 微信收到消息
3. ✅ 用户在后台配邮箱 → 测试发送 → 收到邮件
4. ✅ 管理员在「通知配置」指定"审批创建"走群通知 → 创建审批 → 群里收到
5. ✅ 管理员指定"任务指派"走个人通知 → 创建任务指派张三 → 张三的微信收到
6. ✅ 通知日志能看到每条记录的发送状态
7. ✅ 用户不要的事件类型可以关掉
