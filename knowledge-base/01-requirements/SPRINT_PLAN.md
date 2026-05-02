# 当前迭代计划

**迭代版本**：v2.0 商业版
**开始日期**：2026-04-29
**目标**：P0修复 + 通知系统（飞书/企业微信个人推送）
**状态**：🟡 进行中

---

## 迭代目标

1. 修复 P0 所有阻塞问题（10项）
2. 构建多通道通知系统（飞书 + 企业微信 + QQ + 邮件）
3. 建立知识库文档体系
4. 准备交付包 v2.0

---

## 需求来源

- 需求报告：`01-requirements/BUSINESS_REQUIREMENTS.md`

---

## Sprint Backlog

### Sprint 1：P0 修复（目标：1-2天）

| # | 任务 | 优先级 | 状态 | 负责人 | 备注 |
|---|------|--------|------|--------|------|
| P0-1 | Invoice.tax_amount 自动计算 | P0 | ⬜ | | |
| P0-2 | Expense date/expense_date 冗余统一 | P0 | ⬜ | | |
| P0-3 | 审批超时 cron 集成 | P0 | ⬜ | | |
| P0-4 | ApprovalFlow 加 company 字段 | P0 | ⬜ | | |
| P0-5 | Notification ViewSet | P0 | ⬜ | | |
| P0-6 | CRM admin.py | P0 | ⬜ | | |
| P0-7 | 物料 admin.py | P0 | ⬜ | | |
| P0-8 | 文件 admin.py | P0 | ⬜ | | |
| P0-9 | 设备 admin.py 完善 | P0 | ⬜ | | |
| P0-10 | 工资权限码初始化 | P0 | ⬜ | | |

### Sprint 2：通知系统（目标：2-3天）

> ✅ 架构已重新设计为「多租户插件体系」，参考 OpenClaw Plugin Architecture

|| # | 任务 | 优先级 | 状态 | 负责人 | 备注 |
|---|------|--------|------|--------|------|
| N-1 | NotifyApp/NotifyBinding 模型 | P1 | ✅ 完成 | | 多租户通知应用+绑定 |
| N-2 | 飞书渠道 Binding API | P1 | ✅ 完成 | | POST /bind/qrcode/ + GET /bind/callback/ |
| N-3 | NotifyBinding CRUD API | P1 | ✅ 完成 | | GET/DELETE/PATCH /bindings/{id}/ |
| N-4 | NotifyService 发送服务 | P1 | ✅ 完成 | | notify_user() + 定时任务 |
| N-5 | 管理员后台配置 | P1 | ✅ 完成 | | NotifyAppAdmin + NotifyBindingAdmin |
| N-6 | 飞书应用配置（需用户提供凭证）| P1 | 🔴 阻塞 | | 需在飞书开放平台创建应用 |
| N-6 | 通知偏好设置页面 | P1 | ⬜ | | |
| N-7 | 合同到期提醒 cron | P1 | ⬜ | | |
| N-8 | 设备保修到期提醒 cron | P1 | ⬜ | | |
| N-9 | 物料库存预警 cron | P1 | ⬜ | | |

### Sprint 3：P1 功能（目标：2-3天）

| # | 任务 | 优先级 | 状态 | 备注 |
|---|------|--------|------|------|
| P1-1 | Project.progress 自动同步 | P1 | ⬜ | |
| P1-2 | Task 自动编号 | P1 | ⬜ | |
| P1-3 | CRM import_records | P1 | ⬜ | |
| P1-4 | 文件预览功能 | P1 | ⬜ | |
| P1-5 | 驳回重审 resubmit | P1 | ⬜ | |
| P1-6 | check_alerts 进 crontab | P1 | ⬜ | |

---

## 燃尽图

```
日期       4/29  4/30  5/1   5/2   5/3   5/4
Sprint1   10    8    6     4     2     0
Sprint2   -     9    7     5     3     1
Sprint3   -     -    6     4     2     0
```

---

## 决策记录

| 日期 | 决策 | 理由 |
|------|------|------|
| 2026-04-29 | 通知渠道优先实现飞书+企业微信 | 用户已有飞书开发经验，企业微信适合公司统一使用 |
| 2026-04-29 | 不实现个人微信推送 | 微信不开放个人消息API，无法绕过 |
| 2026-04-29 | 通知策略：系统通知始终记录DB | 确保有记录可查 |

---

## 迭代会议记录

（每次任务执行后更新）

| 日期 | 内容 |
|------|------|
| 2026-04-29 | 迭代启动，确认需求报告v2.0，建立知识库 |
