# 企业管理信息系统 — 开发状态追踪

**更新时间：** 2026年4月23日 10:00
**当前版本：** GREEN 系统 v3（第四轮开发完成）
**系统地址：** http://43.156.139.37:8001/

---

## 模块完成状态

| 模块 | Model | Serializer | ViewSet | API | 前端页面 | 状态 |
|------|-------|-----------|---------|-----|---------|------|
| 用户管理 | ✅ | ✅ | ✅ | ✅ | ✅ | 完成 |
| 角色管理 | ✅ | ✅ | ✅ | ✅ | ✅ | 完成 |
| 权限管理 | ✅ | ✅ | ✅ | ✅ | ✅ | 完成（但三层权限未生效） |
| 客户管理 | ✅ | ✅ | ✅ | ✅ | ✅ | 完成 |
| 供应商管理 | ✅ | ✅ | ✅ | ✅ | ✅ | 完成 |
| 合同管理 | ✅ | ✅ | ✅ | ✅ | ✅ | 完成 |
| 公司管理 | ✅ | ✅ | ✅ | ✅ | ✅ | 完成 |
| 员工管理 | ✅ | ✅ | ✅ | ✅ | ✅ | 完成（缺email/emergency字段） |
| 收支管理 | ✅ | ✅ | ✅ | ✅ | ✅ | 完成 |
| 发票管理 | ✅ | ✅ | ✅ | ✅ | ✅ | 完成 |
| 工资管理 | ✅ | ✅ | ✅ | ✅ | ✅ | 完成（WageRecord无employee FK） |
| 社保配置 | ✅ | ✅ | ✅ | ✅ | ❌ | 完成（无前端页面，数据0条） |
| 项目管理 | ✅ | ✅ | ✅ | ✅ | ✅ | 完成（无progress字段） |
| 任务看板 | ✅ | ✅ | ✅ | ✅ | ✅ | 完成（Kanban） |
| 流程模板 | ✅ | ✅ | ✅ | ✅ | ❌ | 部分完成（无前端管理页，0条数据） |
| 审批管理 | ✅ | ✅ | ✅ | ✅ | ✅ | 部分完成（无模板化，未关联业务） |
| 文件管理 | ✅ | ✅ | ✅ | ✅ | ⚠️ | 基础完成（分类数据0条） |
| 通知中心 | ✅ | ❌ | ❌ | ⚠️ | ⚠️ | 假数据（模拟数据未落地） |
| 数据统计 | ❌ | ❌ | ❌ | ❌ | ✅ | 部分完成（模板有，数据可能不准） |
| 智能预警 | ❌ | ❌ | ❌ | ❌ | ❌ | **未开始** |
| 物料管理 | ❌ | ❌ | ❌ | ❌ | ❌ | **未开始** |
| 设备管理 | ❌ | ❌ | ❌ | ❌ | ❌ | **未开始** |

**总进度：** 10/21 模块完全实现，6/21 部分实现，5/21 完全未开始

---

## API 路径速查（已确认正确）

| 功能 | 正确路径 | 分页 |
|------|---------|------|
| 登录 | `POST /api/core/auth/login/` | — |
| 用户列表 | `GET /api/core/users/` | ✅ |
| 员工列表 | `GET /api/finance/employees/` | ✅ |
| 供应商列表 | `GET /api/crm/suppliers/` | ✅ |
| 客户列表 | `GET /api/crm/clients/` | ✅ |
| 合同列表 | `GET /api/crm/contracts/` | ✅ |
| 发票列表 | `GET /api/finance/invoices/` | ✅ |
| 工资列表 | `GET /api/finance/wages/` | ✅ |
| 审批流列表 | `GET /api/approvals/flows/` | ✅ |
| 任务列表 | `GET /api/tasks/tasks/` | **❌ 裸数组** |
| 项目列表 | `GET /api/tasks/projects/` | ✅ |
| 流程模板 | `GET /api/tasks/flows/` | ✅ |
| 流程节点模板 | `GET /api/tasks/nodes/` | ✅ |
| 文件分类 | `GET /api/files/categories/` | ✅ |

---

## 数据库记录数

| 表名 | 记录数 | 状态 |
|------|--------|------|
| core_user | 1 | ✅ |
| core_role | 1 | ✅ |
| core_permission | 57 | ✅ |
| crm_supplier | 4 | ✅ |
| crm_client | 8 | ✅ |
| crm_contract | 7 | ⚠️ client_id 全 NULL |
| finance_company | 3 | ✅ |
| finance_employee | 5 | ⚠️ 缺 email/emergency |
| finance_income | 10 | ✅ |
| finance_expense | 15 | ✅ |
| finance_wage_record | 17 | ⚠️ 无 employee FK |
| finance_invoice | 16 | ✅ |
| finance_social_config | 0 | ❌ **缺失** |
| tasks_project | 7 | ⚠️ 无 progress 字段 |
| tasks_task | 40 | ✅ |
| tasks_flow_template | 0 | ❌ **缺失** |
| tasks_flow_node_template | 0 | ❌ **缺失** |
| approvals_flow | 8 | ✅ |
| approvals_node | 16 | ✅ |
| file_category | 0 | ❌ **缺失** |
| company_file | 0 | ✅（无上传） |
| core_notification | 0 | ❌ **假数据** |

---

## 已知残留问题（按优先级）

### P0 - 核心功能缺失
1. 任务流程可视化 — 无前端管理页，流程模板数据0条，flow_board.html 未集成流程节点
2. 审批系统 — 未关联业务对象（Expense/Income），无模板化配置，无金额触发逻辑
3. 权限三层控制 — 菜单/按钮/数据权限均未实现

### P1 - 数据完整性
4. WageRecord 无 employee FK — 工资单无法关联员工
5. finance_social_config 无数据 — 3家公司均无社保配置
6. tasks_flow_template 无数据 — 流程引擎无法使用
7. file_category 无数据 — 文件管理无分类
8. Employee 缺 email/emergency 字段
9. Contract.client_id 全 NULL

### P2 - 功能完善
10. notifications 是模拟数据
11. 工资列表无公司筛选
12. 工资无导出功能
13. 社保配置无前端页面
14. 数据统计页面数据可能不准确

### P3 - 新增模块
15. 物料管理（整个模块未开始）
16. 设备管理（整个模块未开始，URL 错跳 projects.html）
17. 智能预警（整个系统未开始）

---

## 技术债

| # | 债项 | 影响 | 修复方案 |
|---|------|------|---------|
| 1 | tasks_project 无 progress | Dashboard 进度随机 | 添加 progress 字段 |
| 2 | WageRecord 无 employee FK | 工资单无法关联员工 | 重构 WageRecord |
| 3 | Contract.client_id NULL | 合同无客户关联 | 回填 client_id |
| 4 | Employee 缺字段 | 信息不完整 | 添加3个字段 |
| 5 | finance_social_config 空 | 社保配置无法用 | 初始化3条记录 |
| 6 | file_category 空 | 文件无分类 | 插入6个分类 |
| 7 | notifications 模拟数据 | 无法真正使用 | 接入 core_notification |
| 8 | CompanyFile 无 project FK | 文件无项目关联 | 添加 FK |

---

## 下一步开发计划

### Phase 1（核心流程）
1. FlowTemplate 前端管理页面 + 插入示例数据
2. flow_board.html 集成流程节点展示
3. 审批流关联 Expense/Income 业务对象

### Phase 2（数据完整性）
4. Employee 添加 email/emergency_contact/emergency_phone
5. WageRecord 添加 employee FK 并重构
6. 初始化 finance_social_config（3条）
7. 初始化 file_category（6个分类）
8. 回填 Contract.client_id

### Phase 3（智能预警）
9. notifications 接入 core_notification
10. 定时任务实现7种预警
11. Dashboard 预警卡片

### Phase 4（新增模块）
12. 物料管理 apps/material/
13. 设备管理 apps/equipment/
14. 权限三层控制前端实现
