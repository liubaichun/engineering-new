# CHANGELOG - GREEN ERP

All notable changes to this project will be documented in this file.

## [v2.2.0] - 2026-05-11

版本代号：核心Bug修复稳定版（Core Stability Release）

### 新增
- **InvoiceSerializer** 新增`project_id`字段，前端编辑弹窗项目下拉可正确回显
- **VERSION管理规范**：新增`VERSION`文件，建立Git标签/CHANGELOG/分支策略规范
- **CHANGELOG**：建立标准化的变更日志记录格式

### 修复 🐛

#### 权限管理模块（红色警报问题）
- `waitForPermissions`正确等待fetch完成才执行callback，superuser用户不再被错误拦截
- `waitForPermissions`超时时间从3秒延长到30秒，防止网络慢时误判无权限
- `loadPermissions`修复分页bug（只加载第一页导致95条权限只显示20条）
- `showPermissionModal`在modal未初始化时自动创建bootstrap.Modal
- 权限管理页面modal移到block modal区域，避免被子模板覆盖
- `hasPermission`和`waitForPermissions`新增`is_superuser`检查

#### 发票管理模块
- `InvoiceSerializer`返回`project_id`字段，解决编辑弹窗中项目无法回显
- 发票导入按钮type参数修复
- 税率/税额的序列化字段修复

#### 银行流水导入模块
- 修复预览返回全部rows（移除[:200]截断）
- 排除词优先于档案精确匹配，防止已建档案的排除词对手方被错误写入
- `_is_excluded_counterparty`增加空字符串判断
- 扩展排除词列表（暂收款/对公中间业务收入/应付利息/自动计提等）
- 新增自然人姓名识别（2-4字纯中文无公司后缀视为自然人，不建档）
- 每行事务独立，消除atomic事务污染导致全批回滚
- audit log改用`on_commit`避免污染主事务
- 银行流水导入3大架构缺陷修复

#### 税费汇总表
- 按税单号前缀拆分为个税/企业所得税/增值税
- 社保公积金改从`Expense(social)`读取，不再依赖空的`WageRecord`
- 拆分为6列展示（进项税/销项税/个税/社保公积金/银行实时缴税/公司税费合计）
- 修复查询条件`expense_category='税款'`覆盖tax+other类型

#### 财务报表/驾驶舱
- `build_qs`按`expense_date`过滤（而非创建时间）
- 报表页自动选中最近有完整数据的年份（而非当前空年）
- 财务报表三项修复
- `parse_date_range`支持superuser全视图

#### 文件/文档模块
- PDF预览改为渲染全42页，每页带页码标签
- PDF预览改用PDF.js渲染，加载状态和错误提示更友好

#### 用户界面
- 用户管理操作按钮从图标改为文字，提高可辨识度
- 分类树+表格分组全部用中文显示名做key（`approval`/`审批管理`重复问题消除）
- 分类合并大小写不敏感（`crm`/`CRM`、`equipment`/`Equipment`等合并显示）
- settings_pg添加`X_FRAME_OPTIONS=SAMEORIGIN`，允许同源iframe嵌入

### 基础设施

#### 数据库/迁移
- 43服务器2个悬停迁移（0021/0022）标记为已应用
- 清理`django_migrations`历史重复记录（finance id=97 `0008_wage_cumulative_tax`）
- 清理`django_migrations`孤岛记录（notifications id=70）
- finance迁移历史整理完毕，112个迁移记录全部对齐
- **124服务器Schema修复**：
  - 从43导出20个缺失表DDL（CRM/tasks/purchasing/repair/channels）
  - 补全finance表缺失字段（`balance`/`source`/`transaction_time`等）
  - 修复`BankStatement`模型未注册（E300错误）
  - 修复notifications迁移文件名错位

### v2.1.2 → v2.2.0 贡献统计
- commit数量：235个
- 涉及模块：权限管理、发票、银行流水、税费、报表、文件、用户界面、基础设施
- 修复的P0问题：5个（红色警报、编辑键不工作、税费表取错表、报表年份默认值、事务污染）

---

## [v2.1.2] - 2026-05-08
- 上一稳定版本
