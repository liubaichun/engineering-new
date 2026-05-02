# 变更日志

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
