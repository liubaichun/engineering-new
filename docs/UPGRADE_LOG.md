# 升级日志
**更新时间：** 2026-05-25

---

## 2026-05-25 社保管理模块上线 + 财务报表数据链修复（v2.3.0）

### 一、社保管理模块（SocialRecord）全新上线

#### 数据模型
| 文件 | 修改内容 |
|------|---------|
| `apps/finance/models.py` | 新增 `SocialRecord` 模型：员工×费款所属期唯一键，9个险种字段（养老/地补养老/医疗/失业/工伤/生育各分个人/单位）+ 公积金（个人/单位），`total_employee`/`total_company`/`total` 自动计算，`is_reconciled` 核销标志 |
| `apps/finance/serializers.py` | 新增 `SocialRecordSerializer`：包含 `social_total_employee`（4项社保个人合计）/ `social_total_company`（6项社保单位合计）计算字段，`total_employee`/`total_company` 包含社保+公积金 |
| `apps/finance/views.py` | 新增 `SocialRecordViewSet`：CRUD + `import_records` 导入接口 |
| `apps/finance/import_social_records.py` | 新增：深圳社保局 Excel 解析，支持按 Sheet 名解析公司名，自动匹配员工（证件号/姓名），导入时同步公积金数据（从 WageRecord 读当月扣款，无则读员工档案 `housing_fund_deduction`），自动设 `is_reconciled=True` |
| `apps/finance/urls.py` | 新增 `social-records` 路由 |
| `config/urls.py` | 新增 `finance/social-records/` 页面路由 |
| `templates/finance/social_record_list.html` | 新增列表页：月度筛选 + 导入按钮 + 8列表格（个人缴社保/个人缴公积金/单位缴社保/单位缴公积金/总合计/核销状态/操作）+ 详情弹窗（顶部三行汇总 + 险种明细网格） |
| `templates/base.html` | 侧边栏财务 Tab 下新增「社保管理」菜单入口 |
| `apps/finance/migrations/` | 新增迁移创建 `finance_social_record` 表 |

#### 关键设计决策
1. **社保费率字段存小数**（0.08=8%），计算时需×100转百分比再代入公式
2. **SocialRecord 是社保精准数据来源**，工资汇总表/税费汇总表/预算执行表直接从 SocialRecord 汇总，不走反推公式
3. **公积金导入时从 WageRecord 读当月扣款**写入 SocialRecord，无 WageRecord 则读员工档案 `housing_fund_deduction`，公司公积金按费率比计算（默认1:1）
4. `total_employee`/`total_company` 包含社保+公积金（参与运算），弹窗里用 JS 实时计算显示值确保等式恒成立
5. **社保局 Excel 格式**：单Sheet宽表，col[n]="费率"，col[n+1]="应缴费额"；公司名从 Sheet 名解析

### 二、工资汇总表社保公积金数据修复

#### 后端：wage_summary 接口从 SocialRecord 读数
| 文件 | 修复内容 |
|------|---------|
| `apps/finance/views.py:1744-1763` | 删除反推公式，改为从 SocialRecord 直接读取：公司社保成本 = 6项单位合计，公司公积金 = housing_fund_company，个人公积金 = housing_fund_employee |
| `apps/finance/reports_v2.py:531-570` | tax_summary 社保费率×100转换，从 CompanySocialConfig 读 |
| `apps/finance/reports_v2.py:640-660` | budget_execution 社保费率×100转换，从 CompanySocialConfig 读 |

#### 前端：report_dashboard.html 字段名对齐
| 文件 | 修复内容 |
|------|---------|
| `templates/finance/report_dashboard.html:501` | 明细行社保公积金列：`total_social_insurance` → 四个字段加总（个人社保+个人公积金+单位社保+单位公积金） |
| `templates/finance/report_dashboard.html:514` | 合计行社保公积金列：`data.summary.total_employees` → `data.summary.total_records`；社保公积金列从"-"改为加总计算 |
| `templates/finance/report_dashboard.html:515` | 合计行补回个税列（被误删） |

### 三、详情弹窗修复

| 问题 | 修复 |
|------|------|
| "个人缴合计"用JS计算绕开数据库字段，等式不恒成立 | 改为 `${fmt(rec.total_employee)}` 直接用数据库字段 |
| "单位缴合计"同样问题 | 改为 `${fmt(rec.total_company)}` |
| 两个等号"= =" | 已改为单个"=" |

### 四、已发现 Bug 待修复（优先级排序）

| # | 严重度 | 接口/文件 | 问题 |
|---|--------|---------|------|
| B1 | **P0** | `invoice_summary` | 变量名 `user_company_id` 写错，应为 `user_company_ids` |
| B3 | **P1** | `balance_sheet` (`views.py`) | 工资支出从 WageRecord 汇总（已完成） |
| B5 | **P1** | 驾驶舱 | 社保数据从 SocialRecord 读 |

---

## 2026-05-24 财务报表 API 全面审计修复（v2.2.1）

（内容见上方 v2.2.1 记录）

---

## 历史版本

- v2.2.0：权限系统 UCP 完全切换
- v2.1.x：通知系统重构（channels 架构）
- v2.0.x：多租户隔离修复（P0 级）
- v1.x：基础功能上线