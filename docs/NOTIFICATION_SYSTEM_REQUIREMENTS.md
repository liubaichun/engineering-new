# 通知系统 — 需求分析与实施计划

> **版本：** v2.0
> **日期：** 2026-06-01
> **状态：** ✅ 已实施（移除微信个人号/ PushPlus）
> **参考设计：** `knowledge-base/01-requirements/NOTIFICATION-SYSTEM-OPTIMIZATION-V6.md`

---

## 一、概述

### 设计目标

```
1. 邮件：保留 SMTP 配置入口，用户配好就能用
2. IM 捆绑：跟飞书/企微/钉钉绑定，重要信息实时推送到个人
3. 群通知与私信通知并存，由管理员配置决定
4. 用户操作要简单——扫码绑定优先，零输入
5. 插件化架构，每家公司独立配置渠道
```

### 通知分类

| 类别 | 含义 | 发送方式 | 使用场景 |
|:----|:-----|:---------|:---------|
| **群通知** | 一条消息发到群里，所有人都能看到 | 群机器人 Webhook | 系统公告、月结提醒、公司通告 |
| **私信通知** | 一条消息发到指定个人，只有他收到 | 渠道 API 点对点发送 | 审批待办、任务指派、合同到期预警 |

---

## 二、支持的渠道

| 渠道 | 支持群通知 | 支持私信通知 | 用户绑定方式 | 实现状态 |
|:----|:---------:|:-----------:|:-----------|:--------|
| **飞书** | ✅ 群机器人 Webhook | ✅ 会话 API（open_id） | 扫码绑定（OAuth） | ✅ 代码完整，需修 token |
| **钉钉** | ❌ | ✅ 应用消息 API | 扫码绑定（OAuth） | ⚠️ 代码完整，未实际验证（无钉钉账号） |
| **企业微信** | ✅ 群机器人 Webhook | ✅ 应用消息 API | 扫码绑定（OAuth） | ✅ 代码完整 |
| **邮件** | ❌ | ✅ SMTP | 自动使用员工档案邮箱 | ⚠️ 缺后台配置页面 |

> **注：** 微信个人号（PushPlus）已移除，原因：用户要求不使用第三方推送服务平台。

---

## 三、关键流程

### 3.1 群通知流程

```
管理员配置阶段：
  1. 在 IM 平台（飞书/企微）创建群机器人
  2. 复制 Webhook URL
  3. 进系统 → 通知渠道 → 添加渠道 → 选「群通知」→ 粘贴 URL → 保存
  4. 系统自动发测试消息验证

发送阶段：
  业务事件触发（如系统公告）
    ↓
  查 ChannelPlugin：company_id=当前公司, usage='broadcast', is_active=True
    ↓
  遍历群渠道，逐个 POST 到 Webhook URL
    ↓
  群里所有人都看到
    ↓
  记录 NotificationLog
```

### 3.2 私信通知流程

```
管理员配置阶段（配一次）：
  1. 添加私信渠道 → 填 App ID/App Secret / SMTP 等凭证
  2. 保存 → 系统验证连通性

用户绑定阶段（每个用户绑一次）：
  [飞书/钉钉/企微] → 系统生成二维码 → 用户扫码授权 → 自动绑定
  [邮箱]            → 员工档案已存邮箱 → 无需额外操作

发送阶段：
  业务事件触发（如审批创建）
    ↓
  确定接收人（审批节点的人 / 任务负责人 / 合同负责人）
    ↓
  查 ChannelPlugin：company_id, usage='personal', is_active=True
    ↓
  查 UserNotificationPreference：接收人是否开启该事件类型
    关闭 → 跳过该接收人
    开启 → 继续
    ↓
  查 ChannelBinding：user=接收人, channel__in=渠道列表, is_active=True
    ↓
  遍历绑定，逐个调用 plugin.send_message(open_id/token, title, content)
    ↓
  记录 NotificationLog
```

### 3.3 用户绑定方式

| 方式 | 适用渠道 | 用户操作步骤 | 复杂度 |
|:----|:---------|:-----------|:------|
| **扫码绑定** 🥇 | 飞书、钉钉、企微 | 点「绑定」→ 扫码 → 确认授权 → ✅ 完成 | 零输入 |
| **自动绑定** 🥇 | 邮箱 | HR 填员工档案时填邮箱 → 系统自动用 | 用户 0 操作 |

---

## 四、用户配置页面一览

| 页面 | 角色 | 功能 | 状态 |
|:----|:----|:-----|:-----|
| `/system/notification-channels/` | 管理员 | 添加/编辑/测试/删除渠道，区分群/私信 | ✅ 已有 |
| `/notifications/bind/` | 用户 | 扫码绑定个人渠道 | ✅ 已有 |
| `/system/notification-preferences/` | 用户 | 设置哪些事件通知我 | ✅ 已有 |
| `/system/notification-logs/` | 管理员 | 查看通知发送记录、统计 | ✅ 已有 |
| `/system/settings/` | 管理员 | 配置 SMTP 邮件参数 | ❌ 待实现 |

---

## 五、模型变更

### ChannelPlugin 加 usage 字段

```python
class ChannelPlugin(models.Model):
    USAGE_CHOICES = [
        ('broadcast', '群通知'),
        ('personal', '私信通知'),
    ]
    usage = models.CharField('用途', max_length=20, choices=USAGE_CHOICES, default='personal')
    # 其他字段不变
```

迁移逻辑：有 `webhook_url` 的标 broadcast，有 `app_id`/`app_key` 的标 personal。

### SMTP 配置存 SystemSetting

```python
SystemSetting(key='smtp_host', value='smtp.example.com')
SystemSetting(key='smtp_port', value='587')
SystemSetting(key='smtp_user', value='')
SystemSetting(key='smtp_password', value='')
SystemSetting(key='smtp_from_email', value='')
```

优先读数据库，没有则回退到环境变量。

---

## 六、实施计划（已实施）

### P0 — 基础设施 ✅

| # | 任务 | 状态 |
|:-:|:----|:----:|
| 1 | `ChannelPlugin` 加 `usage` 字段 + 迁移 | ✅ |
| 2 | 渠道管理页面加 usage 选择器 | ✅ |
| 3 | 已有渠道数据迁移（webhook→broadcast, app→personal） | ✅ |

### P1 — 用户绑定体验 ✅

| # | 任务 | 状态 |
|:-:|:----|:----:|
| 4 | 用户端绑定页面（展示二维码、绑定状态、解绑操作） | ✅ |
| 5 | 用户偏好页面 | ✅ |
| 6 | 绑定成功/失败提示 | ✅ |
| 7 | 移除微信个人号（PushPlus）渠道 | ✅ |

### P2 — 邮件后台配置 ❌ 待实现

| # | 任务 | 状态 |
|:-:|:----|:----:|
| 8 | SMTP 配置页面（主机/端口/账号/密码/发件人） | ❌ |
| 9 | 读取数据库 SMTP 配置 + 回退环境变量 | ❌ |
| 10 | 测试发送按钮 | ❌ |

### P3 — 业务事件接入 ✅ 已实施

| # | 任务 | 说明 | 状态 |
|:-:|:----|:-----|:----:|
| 11 | 审批创建 → 通知审批人 | `apps/core/email_service.py` → channels 发送 | ✅ 已有 |
| 12 | 审批结果 → 通知申请人 | 同上 | ✅ 已有 |
| 13 | 合同到期预警 → 通知负责人 | `check_alerts` 定时任务（每小时） | ✅ 已有 |
| 14 | 任务指派 → 通知负责人 | `notify_task_created` → channels | ✅ 已有 |
| 15 | 工资发放 → 通知员工 | `notify_wage_paid` 新增 | ✅ 2026-06-02 新增 |
| 16 | 设备借出/归还 → 通知保管人 | `notify_equipment_action` → channels | ✅ 已有 |
| 17 | 维修进度更新 → 通知报修人 | 6个action全部调用`notify_repair_action` | ✅ 已有 |

---

## 七、验收标准

1. ✅ 管理员在后台添加飞书群机器人 → 测试发送 → 群里收到消息
2. ✅ 管理员添加飞书私信渠道 → 用户扫码绑定 → 发送测试 → 用户收到
3. ✅ 用户可在偏好页面关闭不需要的事件类型
4. ✅ 通知日志能看到每条记录的发送状态
5. ✅ 创建一条审批 → 审批人收到个人通知
6. ✅ 审批通过/拒绝 → 申请人收到结果通知
7. ❌ 邮件 SMTP 可在后台自行配置

---

## 八、API 接口汇总

| 端点 | 方法 | 说明 | 状态 |
|:-----|:----|:-----|:----:|
| `/api/channels/` | GET/POST | 渠道列表/创建 | ✅ |
| `/api/channels/<id>/` | GET/PATCH/DELETE | 渠道详情/编辑/删除 | ✅ |
| `/api/channels/<id>/validate/` | POST | 验证凭证 | ✅ |
| `/api/channels/<id>/send-test/` | POST | 发送测试消息 | ✅ |
| `/api/channels/bind/qrcode/` | POST | 生成绑定二维码 | ✅ |
| `/api/channels/bind/callback/<id>/` | GET/OAuth | 扫码回调处理 | ✅ |
| `/api/channels/bindings/` | GET/POST/DELETE | 绑定管理 | ✅ |
| `/api/channels/logs/` | GET | 通知日志（翻页+筛选） | ✅ |
| `/api/notifications/preferences/` | GET/PUT | 用户通知偏好 | ✅ |
| `/api/core/notifications/` | GET | 站内通知列表 | ✅ |

---

## 九、风险与预案

| 风险 | 概率 | 预案 |
|:----|:----|:-----|
| 飞书 Token 刷新后仍失效 | 中 | 飞书渠道标记「待修复」，降级到邮件 |
| SMTP 被邮件服务商拦截 | 中 | 提供 SMTP 配置文档，推荐使用企业邮箱 |
| 用户未绑定任何渠道 | 高（系统初期） | 通知只写站内通知列表，不报错 |
| 批量导入触发了大量通知 | 低 | 批量操作时跳过通知，仅写入站内通知 |
