# GREEN ERP 系统知识库

> 📖 按模块组织的文档总索引，方便快速查找。
> 新增功能 / 修改记录 → 见 [变更日志](CHANGELOG.md)

---

## 📊 财务报表模块

| 文档 | 说明 | 最后更新 |
|:-----|:-----|:--------:|
| [财务报表分析报告](FINANCIAL_REPORT_ANALYSIS_2026-05-26.md) | 11张报表全景分析 + P0-P3改造方案 | 2026-05-26 |
| [数据口径文档](FINANCIAL_REPORT_DATA_DICTIONARY.md) | 每个报表的数据来源、计算逻辑、业务含义 | 2026-05-27 |
| [API审计与修复日志](REPORTS_API_DAILY_DEBUG_LOG_2026-05-24.md) | 2026-05-24 全面审计过程记录 | 2026-05-25 |
|| [财务数据策略](FINANCIAL_DATA_STRATEGY_2026-05-26.md) | 数据筛选、科目化、预算方案 | 2026-05-26 |
|| [财务系统改造方案](FINANCIAL_SYSTEM_REFORM.md) | 科目分类重构 + 执行记录（含已修改数据状态） | 2026-05-27 |

**已实现的报表（共15张）：**

| 报表 | 端点 | 阶段 |
|:----|:-----|:----:|
| 月度报表 | `reports/monthly/` | 原有 |
| 年度报表 | `reports/yearly/` | 原有 |
| 收支汇总表 | `reports/revenue-expense-summary/` | P0 |
| 银行余额变动表 | `reports/cash-flow/` | P0 |
| 工资汇总 | `reports/wage-summary/` | P1 |
| 发票汇总 | `reports/invoice-summary/` | 原有 |
| 应收应付账龄 | `reports/ar-ap-aging/` | 原有 |
| 客户收入排行 | `reports/customer-revenue/` | 原有 |
| 供应商支出 | `reports/supplier-expense/` | 原有 |
| 税费汇总 | `reports/tax-summary/` | P1 |
| 预算执行表 | `reports/budget-execution/` | P2 |
| [发票多维汇总(3维度)](docs/invoice-multi-dim/) | P2 |
| [发票管理系统分析与改进计划](INVOICE_SYSTEM_ANALYSIS_2026-05-28.md) | 发票管理功能缺口分析与分阶段修复计划 | 2026-05-28 |
| 科目余额表 | `p3/trial-balance/` | P3 |
| 利润表 | `p3/income-statement/` | P3 |
| 资产负债表 | `p3/balance-sheet/` | P3 |

---

## 🔐 权限系统

| 文档 | 说明 | 最后更新 |
|:-----|:-----|:--------:|
| [UCP V7 规范](PERMISSION_SYSTEM_V7_SPEC.md) | 用户-公司-权限体系 V7 完整设计 | 2026-05-22 |
| [UCP 完整规范](PERMISSION_SYSTEM_SPEC.md) | 多公司细粒度权限定义 | 2026-05-21 |
| [角色 V5 规范](PERMISSION_SYSTEM_ROLE_V5.md) | 角色模板 + 权限分配机制 | 2026-05-20 |
| [修复记录](PERMISSION_SYSTEM_FIX_RECORD_2026-05-22.md) | 权限系统 Bug 修复记录 | 2026-05-22 |
| [自适应矩阵](PERMISSION_SYSTEM_ADAPTIVE_MATRIX.md) | 模块自适应菜单矩阵 | 2026-05-22 |
| [公司级权限](PERMISSION_SYSTEM_COMPANY_LEVEL.md) | 公司间的权限隔离方案 | 2026-05-22 |
| [跨公司数据聚合方案](CROSS_COMPANY_API.md) | 跨公司数据聚合方案 V1.0 | 2026-05-25 |

---

## 🚀 部署与运维

| 文档 | 说明 |
|:-----|:-----|
| [部署标准](DEPLOYMENT_STANDARDS.md) | 服务部署流程与规范 |
| [Docker 部署](docker-deployment.md) | Docker 化部署指南 |
| [124服务器知识库](SERVER_KB_124.md) | 124服务器常见问题 |

---

## 📋 需求与审计

| 文档 | 说明 | 最后更新 |
|:-----|:-----|:--------:|
| [补充需求分析](SUPPLEMENTARY_REQUIREMENTS_ANALYSIS_2026-05-07.md) | 补充需求分析与方案 | 2026-05-07 |
| [补充需求 05-07](SUPPLEMENTARY_REQUIREMENTS_2026-05-07.md) | 补充需求完整内容 | 2026-05-07 |
| [补充需求 05-06](SUPPLEMENTARY_REQUIREMENTS_2026-05-06.md) | 原始需求文档 | 2026-05-06 |
| [ERP 审计报告](ERP_AUDIT_2026-05-06.md) | 系统全面审计 | 2026-05-06 |
| [代码质量报告](CODE_QUALITY_REPORT.md) | 代码质量分析与改进建议 | - |

---

## 🔔 通知系统

| 文档 | 说明 | 最后更新 |
|:-----|:-----|:--------:|
| [通知系统需求分析与实施计划](NOTIFICATION_SYSTEM_REQUIREMENTS.md) | 完整需求分析、架构设计、实施优先级 | 2026-05-28 |
| [通知系统优化方案 v6](knowledge-base/01-requirements/NOTIFICATION-SYSTEM-OPTIMIZATION-V6.md) | 群通知/私信通知详细设计与用户绑定方案 | 2026-05-28 |
| [企业微信通道配置说明](WECOM_CONFIG_GUIDE.md) | 企业微信自建应用完整配置流程 | 2026-05-28 |
| [飞书通知通道配置说明](飞书通知通道配置操作手册.docx) | 飞书自建应用完整配置流程 | 2026-05-28 |

**通知分类：** 群通知（广播到群） / 私信通知（点对点推个人）
**支持渠道：** 飞书、钉钉、企业微信、微信（PushPlus）、邮件
**用户绑定方式：** 扫码绑定 🥇 / 填 Token 🥈 / 自动使用档案邮箱 🥇

---

## 🏗️ 系统架构

| 文档 | 说明 |
|:-----|:-----|
| [系统架构](SYSTEM_ARCHITECTURE.md) | 整体架构设计 |
| [架构图](green-system-architecture.html) | 可视化架构图 |

## 🚀 SaaS多租户设计

| 文档 | 说明 | 最后更新 |
|:-----|:-----|:--------:|
| [多租户SaaS平台设计规范](多租户SaaS平台设计规范.md) | 完整多租户架构方案(租户隔离/路由/认证/平台管理/性能/安全/计费/退租/灾备/Webhook/FeatureFlags) | 2026-05-29 |
| [系统升级方向需求分析报告](系统升级方向需求分析报告.md) | 全景模块分析+差异化升级方案(销售合同/应收应付/物料流转/驾驶舱/客户360°)+实施路线图 | 2026-05-29 |
| [质量安全与认证合规规范](质量安全与认证合规规范.md) | 等保二级合规+双软认证规范+API/代码/字段标准+安全审计/加密/备份规范+上线检查清单 | 2026-05-29 |
| [系统深度审计报告与修改计划](系统深度审计报告与修改计划.md) | 全量代码扫描结果+3项P0/6项P1/8项P2问题+分阶段修复计划+预期效果 | 2026-05-29 |

---

## 📝 变更历史

- [统一变更日志](CHANGELOG.md) — 按时间倒序 + 模块分组，记录所有修改
- [升级日志](UPGRADE_LOG.md) — 原始升级日志（已迁移至 CHANGELOG，保留以兼容旧链接）

---

> 💡 **维护说明：**
> - 新增功能 / 修改 → 更新 `CHANGELOG.md`
> - 新增模块文档 → 更新本索引
> - 入口访问：`/docs/README/`（需将文件名改为 readme 或直接访问 `/docs/`）
