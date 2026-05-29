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

---

## ADR-007：权限体系改造方案

**日期**：2026-05-21
**状态**：❌ 已废弃（2026-05-22）

**决策**：
采用独立 `apps/permission_registry` app + `@register_module` 装饰器 + `AppConfig.ready()` 机制实现模块自注册 + 五档权限矩阵。

**废弃原因**：与 Phase2 UCP 冲突，v2.2.1 当天确认删除。详见 `PERMISSION_REGISTRY_REQUIREMENTS.md` 第五节。

---

## ADR-008：多公司用户数据隔离方案

**日期**：2026-05-21
**状态**：✅ 已采纳

**决策**：`get_user_companies(user)` 返回用户有权限的全部 company_id 列表，`get_queryset()` 用 `filter(company_id__in=company_ids)` 替代原来的单值过滤。

**根因**：原 `_get_user_company_id()` 只取 `.first()`，导致多公司用户数据大量丢失。

**理由**：
- 多公司用户（如人事/财务）需要同时看到所有关联公司的数据
- 改为 `__in` 列表后，业务逻辑不变，数据不丢失
- `company_ids=None` 时（超管）不过滤，等于全公司可见

**风险**：
- `company_id=NULL` 的历史数据会被 `__in` 过滤掉（不影响普通用户，因为普通用户没有 NULL 关联）
- 超管仍可看到所有数据（包括 NULL）

---

## ADR-009：敏感数据脱敏方案（MaskedCharField）

**日期**：2026-05-22
**状态**：✅ 已采纳

**决策**：自定义 `MaskedCharField`（继承 `serializers.CharField`），写入时存完整值，读取时脱敏返回。仅影响Serializer层（controller），不破坏数据库原始数据。

**脱敏规则**：
- 身份证号：保留前6位+后4位，中间星号（`110101****1234`）
- 银行卡号：保留前6位+后4位，中间星号（`622202****0123`）
- 手机号：保留前3位+后4位，中间星号（`138****8000`）
- 银行账号：保留前4位+后4位，中间星号（`3100****7890`）

**理由**：
- 不改变数据库存储，不影响搜索/排序/统计
- 前端无需额外处理，直接展示
- 导出Excel时也自动脱敏

**涉及文件**：`finance/serializers.py`

---

## ADR-010：Serializer 公司归属校验（CompanyAccessValidatorMixin）

**日期**：2026-05-22
**状态**：✅ 已采纳

**决策**：`CompanyAccessValidatorMixin` — 在 Serializer `validate()` 阶段校验 `company` 字段是否属于用户可访问的公司范围。超级用户豁免。

**理由**：
- 防止用户通过 API 直接指定他人公司的 company_id
- 不修改 create 逻辑（只校验不注入）
- 利用 DRF `validate()` 天然位置，不增加请求次数
- 超级用户豁免（管理后台正常使用）

**风险**：
- `company` 字段不在 request.data 中时不做校验（如 inherit 场景）
- 与 `UserCompanyPermission` 权限体系配合使用，不做重复校验

---

## ADR-011：导入视图公司来源统一方案

**日期**：2026-05-25
**状态**：✅ 已采纳

**决策**：所有导入视图（CRM/财务/银行/员工）统一使用 `request.auth_company` 作为公司默认值来源替代硬编码 `Company.objects.first()`。

**优先级链**：
1. Excel 中明确指定了公司列 → 取Excel值
2. 无公司列 → `request.auth_company`（当前选中公司/默认公司）
3. 无选中公司 → `user.company_id` 后备

**涉及文件**：`crm/import_views.py`, `finance/import_views.py`, `apps/equipment/bank_import_views.py`
