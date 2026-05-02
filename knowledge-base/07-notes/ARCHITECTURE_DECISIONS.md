# 架构决策记录（ADR）

> Architecture Decision Records - 重要的架构决策记录备案。

## ADR-001：多租户隔离方案

**日期**：2026-04-29
**状态**：✅ 已采纳

**决策**：通过 `TenantMiddleware` 在请求级别注入 `company_id`，所有业务 ViewSet 的 `get_queryset()` 统一加 `company_id` 过滤。

**理由**：
- 改动量最小，不破坏现有 Model 结构
- 与 Django ORM 结合紧密，天然防注入
- superuser bypass 便于管理后台操作

**备选方案**：
- 每个表加 `company` FK（Django-filter 方案）：改动太大，影响所有迁移
- 请求头 `X-Company-ID` 传递：简单但缺乏校验

---

## ADR-002：通知渠道策略

**日期**：2026-04-29
**状态**：✅ 已采纳

**决策**：采用「策略模式」实现多通道通知，NotifyService 统一调度，各通道独立实现。

**理由**：
- 扩展方便，新增渠道只需实现 `Channel.send()` 接口
- 故障隔离，某通道失败不影响其他通道
- 用户可按偏好选择接收渠道

**备选方案**：
- 观察者模式（信号）：耦合太紧，调试困难
- 消息队列（Celery）：过度设计，单机部署简单场景不需要

---

## ADR-003：个人推送渠道选择

**日期**：2026-04-29
**状态**：✅ 已采纳

**决策**：
- 飞书：Open ID 个人推送 ✅
- 企业微信：UserID 个人推送 ✅
- QQ：机器人私聊 ✅
- 个人微信：不实现 ❌

**理由**：
- 飞书：已有开发经验，Open Platform API 完整
- 企业微信：适合公司统一部署，用户基数大
- QQ：适合年轻团队，按需启用
- 个人微信：微信不开放 API，任何第三方都是违规的

---

## ADR-004：审批流不内置 webhook

**日期**：2026-04-29
**状态**：✅ 已采纳

**决策**：审批结果不提供 HTTP webhook 回调机制，仅通过 NotifyService 推送。

**理由**：
- webhook 需要客户有公网回调地址，增加了部署复杂度
- NotifyService 已经覆盖了所有常用渠道
- 如需 webhook，可以后续在 NotifyService 层面扩展

---

## ADR-005：交付包结构

**日期**：2026-04-29
**状态**：✅ 已采纳

**决策**：Docker Compose 单机部署，PostgreSQL + Django + Nginx 三服务，通过 `start.sh` 一键启动。

**理由**：
- 单机部署简单，客户服务器有 Docker 即可
- Nginx 作为反向代理，静态文件缓存，上传限制
- 未来如需集群，可以在 Kubernetes 上迁移

**备选方案**：
- Kubernetes：过度设计，小客户用不上
- Docker Swarm：不如 K8s 通用

---

## ADR-006：文件预览方案

**日期**：2026-04-29
**状态**：✅ 已采纳

**决策**：前端 JS 库预览（PDF.js / docx-preview / SheetJS），后端只提供文件 URL 和类型标识。

**理由**：
- 不依赖外部预览服务（如 Office Online）
- 无需在服务器端转换文件
- CDN 引入库，前端直接渲染
- 对于不支持的格式，fallback 到下载

**限制**：无法预览加密/受保护的 Office 文件。
