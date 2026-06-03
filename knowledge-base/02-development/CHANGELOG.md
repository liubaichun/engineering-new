# 变更日志

## [v2.3.0] 2026-06-01 — 通知系统断裂修复 + 菜单闪现/跳转登录修复

### 通知系统修复（P0）

**根因：** 通知系统 V5/V6 迭代中 `channels/services.py` 重写，删除了 `ChannelNotificationService` 类，但两处调用方未同步更新。

**修复文件：**
- `apps/tasks/notification_service.py` — `dispatch_notify()` 改用 `send_notification()` 函数，保留用户偏好检查
- `apps/core/email_service.py` — `_send_to_binding_channel()` 改用 `send_notification()` 函数

**效果：**
- ✅ 定时任务 `check_task_timeouts.py` 超时检测 → 通知用户飞书/企微/钉钉
- ✅ 定时任务 `check_alerts.py` 7类预警 → 通知相关用户
- ✅ 审批创建/通过/驳回/催办 → 多渠道推送
- ✅ 任务/合同/设备/维修/项目变更 → 通知负责人

### 菜单闪现修复（P0）

**根因：** `base_content.html` 继承 `base.html` 但用 JS 在 DOMContentLoaded 时才修正 CSS `margin-left`，产生 50-300ms 的 260px 空白闪烁。

**修复：**
- `templates/base_content.html` — 在 CSS 层面直接覆盖 `margin-left:0!important`，比 JS 早一个渲染周期生效
- `templates/crm/contact_followup_list.html` — `base.html` → `base_content.html`
- `templates/crm/contract_detail.html` — `base.html` → `base_content.html`

### 跳转登录页修复（P0）

**根因：** `app.js` 的 `checkAuth()` 在 API 返回非200时执行 `window.location.href = '/login/'`，快速切换模块时 API 瞬时故障导致用户被踢。

**修复：**
- `static/js/app.js` — API 失败或网络错误时不再跳转登录页，改为 `console.warn` 静默降级。真正的认证校验由 Django 服务端负责，前端 checkAuth 仅作辅助判断。

### 涉及文件
- 修改文件：6个
- 分析文档：`knowledge-base/07-notes/NOTIFICATION_SYSTEM_BREAKAGE_ANALYSIS.md`（通知系统断裂分析）
- 分析文档：`knowledge-base/07-notes/MENU_FLASH_LOGIN_REDIRECT_ANALYSIS.md`（菜单闪现分析）
- 部署：43服务器 ✅

---

## [v2.2.1] 2026-05-25 — 安全审计收官（17项权限修复）

### 安全加固
- 敏感数据脱敏：身份证号/银行卡号/手机号 `MaskedCharField` 自动脱敏
- Serializer 公司归属校验：`CompanyAccessValidatorMixin`（非超管校验）
- 银行导入 preview/confirm 加 `UserCompanyRole` 公司权限校验
- 6个 ViewSet 从未生效的 `action_perms` 补全（Company/Income/Expense/WageRecord/Invoice/ARAP）

### 权限修复
- CRM合同5个动作 approve/reject/activate/complete/terminate 权限码修正
- 审批流 create=read 修复
- finance 5个 ViewSet 权限前缀修正（company→employee/bank/social_security/employee）
- Equipment record_repair/export 权限注册
- user_list.html 权限码旧格式 `user.add` → `system:user:create`
- UserViewSet 补全 action-level 权限码

### 导入修复
- CRM导入（客户/供应商/合同）创建记录添加 company 关联
- 财务导入（收入/支出）改用 `auth_company` 替代硬编码 `Company.objects.first()`
- 发票导入优先 `auth_company`（当前选中公司）
- 员工导入缺公司列时 `auth_company` 兜底

### 涉及文件统计
- 修改文件：12个（views × 5, import_views × 3, serializers × 2, templates × 2）
- 函数/视图：17个修复点
- 部署：43服务器 ✅ 124服务器 ✅

---

## [v2.0] 2026-04-29 — 商业版开发启动

### 新增

- 新增 `knowledge-base/` 目录，知识库体系建立
- 需求报告 v2.0：`01-requirements/BUSINESS_REQUIREMENTS.md`
  - 飞书/企业微信/QQ 个人推送方案
  - 文件预览功能方案
  - 模块化设计方案
- 迭代计划：`01-requirements/SPRINT_PLAN.md`

---

## [v1.9] 2026-04-29 — 交付包完善

### 新增

- 交付包 `delivery/` 目录完整化
  - `docker-compose.yml` — PostgreSQL + Django + Nginx 三服务
  - `Dockerfile` — Python 3.11 slim 构建
  - `start.sh` — 一键部署脚本（118行）
  - `.env.example` — 环境变量模板
  - `config/nginx.conf` — 反向代理配置
  - `docs/DEPLOY.md` (326行) — 完整部署文档
  - `docs/QUICKSTART.md` (153行) — 快速开始指南
  - `docs/UPDATE.md` (77行) — 升级流程

### 修复

- 修复左侧菜单 40项→24项精简
- 修复 delivery/Dockerfile context 路径

---

## [v1.8] 2026-04-29 — 多租户隔离完成

### 新增

- `TenantMiddleware` 多租户中间件
- `DEPLOY_MODE` 开关（single/multi_tenant）
- 所有业务表 `company_id` 过滤
- `UserCompanyRole` 多公司角色

### 修复

- Material/Equipment/Supplier/Client/Contract 全部加租户隔离

---

## [v1.7] 2026-04-29 — gunicorn进程管理修复

### 修复

- 修复 `pkill -9` 只杀 master 不杀 workers 的问题
- systemd ExecStart 改为进程遍历方案
- KillMode=process 防 OOM 孤儿

---

## [v1.6] 2026-04-28 — openclaw修复

### 修复

- 修复 `/root/.local/share/pnpm/` 误删后 openclaw CLI 失效
- 重写 openclaw.mjs 为 node dist/index.js 包装脚本
- 修复 openclaw-gateway.service ExecStart 路径

---

## 早期版本

见 `../docs/BUG_FIX_RECORD.md` 和 `../docs/DEVELOPMENT_STATUS.md`
