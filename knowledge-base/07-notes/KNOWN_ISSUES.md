# 已知问题

> 已知但暂不处理或无法处理的问题列表。

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
