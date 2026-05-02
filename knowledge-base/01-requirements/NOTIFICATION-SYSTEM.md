# 通知渠道系统 — 多租户插件架构

> 参考 OpenClaw Plugin Architecture 设计，商业化多租户通知体系

## 核心概念

```
每个租户 = 一个独立的通知机器人（飞书/企微/QQ/Telegram）
凭证由租户管理员在后台配置，用户扫码自助绑定
```

## 数据模型

### NotifyApp — 通知应用配置
每个租户配置的独立通知渠道（一个租户可配多个渠道）

| 字段 | 类型 | 说明 |
|------|------|------|
| `company` | FK(Company) | 所属公司 |
| `channel_type` | choice | feishu/wecom/qq/telegram/email |
| `app_name` | str | 机器人显示名 |
| `app_id` | str | 飞书 CLI_xxx / 企微 CorpID / QQ AppID |
| `app_secret` | str | 凭证 |
| `connection_mode` | choice | websocket（长连接）/ webhook（回调）|
| `pairing_mode` | choice | pairing（扫码配对）/ allowlist（手动）|
| `allow_from` | str | 白名单 open_id，逗号分隔 |
| `is_active` | bool | 是否启用 |
| `binding_count` | int | 已绑定用户数（自动更新）|

### NotifyBinding — 用户绑定关系
用户扫码配对后的绑定记录

| 字段 | 类型 | 说明 |
|------|------|------|
| `user` | FK(User) | 绑定的用户 |
| `notify_app` | FK(NotifyApp) | 绑定的通知应用 |
| `platform_open_id` | str | 平台用户标识 |
| `platform_display_name` | str | 用户昵称 |
| `notify_contract` | bool | 合同通知 |
| `notify_equipment` | bool | 设备通知 |
| `notify_project` | bool | 项目通知 |
| `notify_approval` | bool | 审批通知 |
| `notify_wage` | bool | 工资通知 |
| `bound_at` | datetime | 绑定时间 |
| `last_notified_at` | datetime | 最后通知时间 |

### NotificationLog — 发送日志
每次通知的发送记录

| 字段 | 类型 | 说明 |
|------|------|------|
| `binding` | FK(NotifyBinding) | 关联的绑定 |
| `title` | str | 通知标题 |
| `content` | str | 通知内容 |
| `notify_type` | str | contract/equipment/project/approval/wage/system |
| `related_id` | int | 关联记录 ID |
| `status` | choice | pending/sent/failed/read |
| `error_message` | str | 错误信息 |

## API 接口

### 1. 生成绑定二维码
```
POST /api/notifications/bind/qrcode/
Body: { "channel_type": "feishu" }

返回:
{
  "qrcode_url": "https://open.feishu.cn/open-apis/authen/v1/index?app_id=CLI_xxx&...",
  "bind_token": "随机32位token",
  "expires_in": 300,
  "channel_type": "feishu",
  "app_name": "工程管理系统通知"
}
```

### 2. 飞书 OAuth 回调
```
GET /api/notifications/bind/callback/?code=xxx&state=bind_token

处理流程:
1. 解析 bind_token，获取 user_id/company_id/channel_type
2. 用 code 向飞书换 open_id
3. 写入/更新 NotifyBinding 表
4. 发"绑定成功"消息给用户
5. 重定向到前端 /?bind_success=1
```

### 3. 绑定列表
```
GET /api/notifications/bindings/

返回:
{
  "results": [
    {
      "id": 1,
      "channel_type": "feishu",
      "channel_label": "飞书",
      "app_name": "工程管理系统通知",
      "company_name": "测试公司",
      "platform_open_id": "ou_xxx",
      "platform_display_name": "张三",
      "notify_contract": true,
      "notify_equipment": true,
      "notify_project": true,
      "notify_approval": true,
      "notify_wage": true,
      "bound_at": "2026-04-29T18:00:00Z"
    }
  ]
}
```

### 4. 解绑
```
DELETE /api/notifications/bindings/{binding_id}/
```

### 5. 更新通知偏好
```
PATCH /api/notifications/bindings/{binding_id}/
Body: { "notify_contract": false, "notify_wage": true }
```

## 飞书机器人配置步骤（管理员）

1. 打开 https://open.feishu.cn/app
2. 创建自建应用 → 填名称/图标
3. 添加应用能力 → 「机器人」
4. 配置权限：
   - `im:message`（发消息）
   - `contact:user.id:readonly`（获取用户 ID）
5. 发布应用（或加入测试版本）
6. 获取 `App ID`（`CLI_xxx`）和 `App Secret`
7. 在 GREEN 后台 → 通知应用 → 添加应用 → 填入凭证

## 用户绑定流程

```
1. 用户进入「通知设置」页面
2. 看到自己公司已配置的机器人列表
3. 点「绑定飞书」→ 调用 POST /bind/qrcode/
4. 拿到 qrcode_url，用二维码组件展示给用户
5. 用户用飞书扫码 → 授权 → 自动跳转回调
6. 回调处理完成 → 重定向到前端「绑定成功」页
7. 用户发任意消息给机器人 → 机器人回复「绑定成功」
8. 绑定完成
```

## 通知发送流程

```
业务触发（cron/信号）→ notify_user() 
  → 遍历用户所有有效 NotifyBinding
  → 按 channel_type 调用对应发送函数
  → 飞书: send_feishu_message(app_id, app_secret, open_id, text)
  → 写入 NotificationLog
  → 更新 binding.last_notified_at
```

## Cron 定时通知

| 任务 | 频率 | 说明 |
|------|------|------|
| `check_contract_expiring` | 每天 | 合同到期前7天提醒 |
| `check_equipment_expiring` | 每天 | 设备保修到期前30天提醒 |
| `check_approval_timeouts` | 每5分钟 | 审批超时提醒 |

## 待接入渠道

- [ ] 企业微信（`wecom`）— 应用消息 API
- [ ] QQ 机器人（`qq`）— QQ 开放平台机器人
- [ ] Telegram（`telegram`）— Bot API
- [ ] 邮件（`email`）— 已有 SMTP

## 文件清单

| 文件 | 说明 |
|------|------|
| `apps/notifications/models.py` | NotifyApp/NotifyBinding/NotificationLog 模型 |
| `apps/notifications/views.py` | 所有 API 视图 |
| `apps/notifications/urls.py` | URL 路由 |
| `apps/notifications/admin.py` | 后台管理 |
| `apps/notifications/migrations/0001_add_notify_app_binding.py` | 数据库迁移 |
