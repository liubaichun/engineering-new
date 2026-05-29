# 升级日志

> ⚠️ **已迁移至 [CHANGELOG.md](CHANGELOG.md)**，本文件保留以兼容旧链接。
> 新修改请记录到 CHANGELOG.md，不再更新本文件。

**最后更新：** 2026-05-26

---

## 2026-05-26 全模块分页统一化 + 发票排序及年份筛选修复（v2.3.1）

### 一、全模块分页统一化

将所有需要分页的模块统一添加"每页条数"下拉选择器，以社保管理模块的 `select#pageSize` 为模板，每个模块按数据量设置合理的默认条数和可选范围。

#### 修改原则
- 默认值根据模块数据量设定：数据少的模块用小默认值（如公司管理10条、员工管理15条），数据多的用20条
- 可选值统一包含3-4档，确保小数据量模块有更细的分页粒度
- 切换条数后自动重置到第1页并重新加载数据
- 保留原有 pagination 逻辑，仅在 UI 层增加选择器

#### 修改的文件清单

| # | 模块 | 文件 | 默认条数 | 可选范围 |
|---|------|------|---------|---------|
| 1 | 发票管理 | `templates/finance/invoice_list.html` | 20 | 20/50/100 |
| 2 | 收入管理 | `templates/finance/income_list.html` | 20 | 20/50/100 |
| 3 | 支出管理 | `templates/finance/expense_list.html` | 20 | 20/50/100 |
| 4 | 工资管理 | `templates/finance/wage_list.html` | 20 | 20/50/100 |
| 5 | 公司管理 | `templates/finance/company_list.html` | 10 | 10/20/50/100 |
| 6 | 员工管理 | `templates/finance/employee_list.html` | 15 | 15/20/50/100 |
| 7 | 应收应付 | `templates/finance/ar_ap_list.html` | 20 | 20/50/100 |
| 8 | 社保管理（原有） | `templates/finance/social_record_list.html` | 20 | 20/50/100（未改动） |
| 9 | 物料管理 | `templates/purchase/material_list.html` | 15 | 15/20/50/100 |
| 10 | 设备管理 | `templates/purchase/equipment_list.html` | 15 | 15/20/50/100 |
| 11 | 审批管理 | `templates/approval/flow_list.html` | 20 | 20/50/100 |
| 12 | 通知列表 | `templates/core/notification_list.html` | 20 | 20/50/100 |
| 13 | 通知日志 | `templates/core/notification_log_list.html` | 50 | 20/50/100 |
| 14 | 登录日志 | `templates/core/login_log_list.html` | 20 | 20/50/100 |
| 15 | 操作日志 | `templates/core/operation_log_list.html` | 20 | 20/50/100 |
| 16 | 客户管理 | `templates/crm/client_list.html` | 20 | 20/50/100 |
| 17 | 供应商管理 | `templates/crm/supplier_list.html` | 20 | 20/50/100 |

#### 标准分页选择器 HTML 模板

```html
<select class="form-select form-select-sm" id="pageSize"
        style="width: auto;" onchange="changePageSize()">
    <option value="20">20条/页</option>
    <option value="50">50条/页</option>
    <option value="100">100条/页</option>
</select>
```

#### 标准 changePageSize() 函数

```javascript
function changePageSize() {
    pageSize = parseInt(document.getElementById('pageSize').value);
    currentPage = 1;
    loadData();
}
```

#### 部署服务器
- 43服务器（43.156.139.37）✅
- 124服务器（124.222.227.28）✅

### 二、发票排序修复

#### 问题
Invoice 模型的 `Meta.ordering = ['-created_at']`，导致发票列表按创建时间排序，而非发票日期。用户期望按开票日期（issue_date）倒序排列。

#### 修复
| 文件 | 修改内容 |
|------|---------|
| `apps/finance/models.py` | Invoice 模型 `Meta.ordering` 从 `'-created_at'` 改为 `'-issue_date'` |

#### 部署（两台服务器）
| 服务器 | 操作 |
|--------|------|
| 43.156.139.37 | 修改文件 → gunicorn HUP 热重启（未重启服务，只重载worker） |
| 124.222.227.28 | 修改文件 → gunicorn HUP 热重启 |
| 验证 | curl 接口返回数据按 issue_date 倒序 ✅ |

### 三、发票年份筛选修复

#### 问题
`templates/finance/invoice_list.html` 的 `loadInvoices()` 函数中，定义了 `filterYear` 变量但未拼接到 API 请求 URL 的 `year` 参数中，导致年份筛选无效。

#### 修复
| 文件 | 修改内容 |
|------|---------|
| `templates/finance/invoice_list.html` | `loadInvoices()` 函数增加 `year` 参数拼接：`year=${filterYear}` |

### 四、社保导入错误展示修复

#### 问题
社保导入操作中，后端返回的错误信息在前端被吞掉，用户看到导入总数 0 但不知原因。

#### 修复
| 文件 | 修改内容 |
|------|---------|
| `templates/finance/social_record_list.html` | 新增错误信息展示区域：文件格式/列位置/日期格式等异常不再被吞掉 |

#### 根因
用户提供的 Excel 文件格式与导入代码预期不匹配（列位置或日期格式差异），非代码 bug。

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