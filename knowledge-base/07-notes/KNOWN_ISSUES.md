# 已知问题

> 已知但暂不处理或无法处理的问题列表。

## ✅ 近期已修复

| # | 问题 | 修复时间 | 修复方案 |
|---|------|---------|---------|
| ~~-~~ | ~~敏感数据明文返回（身份证/银行卡/手机号）~~ | 2026-05-22 | `MaskedCharField` 自动脱敏 ✅ |
| ~~-~~ | ~~CRM合同动作权限码越权~~ | 2026-05-24 | 权限码 `client_source:*` → `contract:*` ✅ |
| ~~-~~ | ~~审批流create=read~~ | 2026-05-24 | `read` → `create` ✅ |
| ~~-~~ | ~~finance 5个ViewSet权限前缀全是 company~~ | 2026-05-24 | 逐项修正 ✅ |
| ~~-~~ | ~~Equipment record_repair/export无权限限制~~ | 2026-05-24 | 权限注册 ✅ |
| ~~-~~ | ~~6个Finance ViewSet action_perms从未生效~~ | 2026-05-24 | 补 `action_perms = {...}` ✅ |
| ~~-~~ | ~~CRM导入无公司关联~~ | 2026-05-25 | 加 `auth_company` ✅ |
| ~~-~~ | ~~财务导入硬编码 Company.objects.first()~~ | 2026-05-25 | 改用 `auth_company` ✅ |
| ~~-~~ | ~~银行导入preview/confirm无权限校验~~ | 2026-05-25 | 加 `UserCompanyRole` ✅ |
| ~~-~~ | ~~UserViewSet无action-level权限~~ | 2026-05-25 | 补 `action_perms` ✅ |

## 外部依赖（无法推进）

| # | 问题 | 影响 | 原因 | 替代方案 |
|---|------|------|------|---------|
| - | 个人微信推送 | 无法实现 | 微信不开放个人消息API | 企业微信替代 |
| - | Let's Encrypt HTTPS | 需域名 | Let's Encrypt不支持裸IP | Cloudflare代理或购买域名 |

## 延迟处理

| # | 问题 | 影响 | 原因 | 计划处理 |
|---|------|------|------|---------|
| 1 | 无 API 限流 | 安全风险 | 未集成 django-ratelimit | v1.1 |
| 2 | gunicorn workers=2 | 性能低 | 配置未优化 | v1.1 |
| 3 | settings.py DEBUG硬编码 | 安全风险 | 未完全迁移到环境变量 | v1.1 |
| 4 | 旧Dockerfile在根目录 | 混淆 | 与delivery/重复 | v1.1 |

## 设计决策（有意为之）

| # | 决策 | 理由 |
|---|------|------|
| 1 | Notification在core/models不在notifications app | notifications是空壳app，避免循环导入 |
| 2 | admin.py用传统写法不用admin.register装饰器 | 统一风格，与其他app保持一致 |
| 3 | 审批流不内置webhook | 飞书/企微推送已通过NotifyService实现 |
