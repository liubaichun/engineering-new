# engineering-new 企业信息化系统
## 全面质量评估报告

> **审查日期：** 2026-05-13
> **审查范围：** 12个业务模块、2041行核心视图、安全架构、数据隔离、业务逻辑
> **审查原则：** 只检查，不修改
> **项目路径：** `/root/engineering-new/`

---

## 一、技术架构总览

### 1.1 技术栈

| 层级 | 技术选型 | 版本 | 状态 |
|------|---------|------|------|
| 后端框架 | Django + Django REST Framework | 5.2.13 / 3.17.1 | 现代稳定 |
| 数据库 | PostgreSQL | - | 可靠关系型 |
| 认证方式 | Session + CSRFExemptSessionAuthentication | - | 见安全章节 |
| API文档 | drf-spectacular + Swagger | 0.29.0 | 完善 |
| Excel处理 | openpyxl | 3.1.5 | 安全解析器 |
| PDF处理 | PyPDF2 | 3.0.1 | 已知CVE |
| WSGI服务 | Gunicorn | 26.0.0 | - |
| 反向代理 | Nginx | - | - |

### 1.2 项目结构

```
engineering_new/
├── apps/                      # 12个业务模块
│   ├── finance/               # 财务核心 [2041行views.py]
│   │   ├── views.py          # 2041行（建议拆分）
│   │   ├── serializers.py     # 534行
│   │   ├── models.py          # 988行
│   │   ├── models_bank.py     # 银行流水
│   │   ├── bank_import_views.py # 983行
│   │   ├── filters.py         # 过滤器
│   │   └── bank_adapters.py   # 银行解析适配器
│   ├── core/                  # 通用基础设施
│   │   ├── views.py          # 1183行
│   │   ├── models.py          # 用户/角色/权限/审计
│   │   ├── auth.py           # CSRFExemptSessionAuthentication
│   │   ├── permissions.py    # RoleRequired权限装饰器
│   │   ├── middleware.py      # CompanyContextMiddleware
│   │   ├── audit.py          # 信号式操作审计
│   │   ├── import_excel.py    # 740行
│   │   ├── export_excel.py   # Excel导出
│   │   └── wage_email_service.py # 工资条邮件
│   ├── approvals/            # 审批流引擎
│   ├── tasks/                # 任务管理 [1114行views]
│   ├── crm/                  # 客户关系管理 [469行views]
│   ├── purchasing/           # 采购管理 [376行views]
│   ├── channels/             # 通知渠道 [902行views]
│   ├── equipment/           # 设备管理 [220行views]
│   ├── material/            # 物料管理 [279行views]
│   ├── repair/             # 维修管理 [165行views]
│   ├── notifications/       # 通知管理 [154行views]
│   └── files/              # 文件管理
├── config/                  # Django配置
│   ├── settings.py         # 主配置
│   └── urls.py             # URL路由（413行）
├── templates/              # 前端HTML模板
├── static/                  # 静态资源
├── company_files/           # 公司文件上传
├── requirements.txt        # Python依赖
└── deploy/                  # 部署脚本
```

### 1.3 业务模块规模

| 模块 | Views行数 | Models行数 | 核心功能 |
|------|-----------|-----------|---------|
| finance | 2041 | 988 | 收入/支出/工资/发票/银行流水/报表 |
| tasks | 1114 | 21246 | 任务/项目/看板/流程模板 |
| core | 1183 | ~400 | 用户/角色/权限/审计 |
| channels | 902 | - | 通知渠道/系统通知 |
| approvals | 483 | - | 审批流/节点/模板 |
| crm | 469 | - | 客户/供应商/合同/付款计划 |
| purchasing | 376 | - | 采购申请/订单/收货 |
| material | 279 | - | 物料/BOM |
| equipment | 220 | - | 设备/BOM |
| repair | 165 | - | 维修工单 |
| notifications | 154 | - | 通知管理 |
| files | - | - | 文件分类/公司文件 |

---

## 二、安全架构深度评估

### 2.1 致命漏洞（必须立即修复）

#### 漏洞1：CompanyViewSet 平行越权（IDOR）

**文件：** `apps/finance/views.py:132-140`

```python
def get_queryset(self):
    if not self.request.user.is_authenticated:
        return Company.objects.none()
    user = self.request.user
    if user.is_authenticated and not user.is_superuser:
        if hasattr(user, 'company') and user.company_id:
            return Company.objects.filter(id=user.company_id)
    return Company.objects.all()  # BUG: 非超管但无公司关联时返回所有公司
```

**触发条件：** 普通用户（is_superuser=False）如果没有任何 UserCompanyRole 关联，则 user.company_id 为空，进入 return Company.objects.all()。

**影响：** 该用户可枚举系统中所有公司信息，包括名称、税号、联系人、电话、银行账号。

**攻击方式：**
```bash
curl -H "Authorization: Session <token>" \
  http://43.156.139.37:8001/api/finance/companies/
# 返回所有公司完整列表
```

**修复建议：**
```python
def get_queryset(self):
    if not self.request.user.is_authenticated:
        return Company.objects.none()
    user = self.request.user
    if user.is_superuser:
        return Company.objects.all()
    if hasattr(user, 'company_id') and user.company_id:
        return Company.objects.filter(id=user.company_id)
    return Company.objects.none()  # 无公司关联则无权访问
```

---

#### 漏洞2：bank_accounts 端点无公司边界校验

**文件：** `apps/finance/views.py:149-161`

```python
def bank_accounts(self, request, pk=None):
    company = self.get_object()  # company来自URL路径pk
    accounts = BankAccount.objects.filter(company=company, is_active=True)
```

但 CompanyViewSet.get_queryset() 在非超管无公司关联时返回所有公司，导致用户A（属于公司甲）可通过 GET /api/finance/companies/乙/bank_accounts/ 获取竞争对手公司银行账户。

**修复建议：** 在 get_queryset() 修复后，此问题同时解决。

---

#### 漏洞3：bank_import_views 所有函数无公司权限校验

**文件：** `apps/finance/bank_import_views.py`

所有函数（preview_bank_statement / confirm_bank_import / upload_bank_statement）的 company_id 完全来自用户输入，无权限校验：

```python
company_id = body.get('company_id')  # 纯用户输入，无校验
company = Company.objects.get(id=company_id)  # 仅验证存在，不验证归属
```

**攻击场景：** 认证用户可以任意指定 company_id，为任意公司导入伪造的银行流水记录。

**修复建议：** 在所有函数入口添加：
```python
user_company_id = _get_user_company_id(request.user)
if user_company_id is not None and int(company_id) != user_company_id:
    return Response({'error': '无权操作该公司数据'}, status=403)
```

---

#### 漏洞4：Swagger/OpenAPI 对未认证用户开放

**文件：** `config/urls.py:357-358`

```python
path('api/schema/', SpectacularAPIView.as_view(
    authentication_classes=[], permission_classes=[]), name='schema'),
path('api/docs/', SpectacularSwaggerView.as_view(
    authentication_classes=[], permission_classes=[]), name='swagger-ui'),
```

**影响：** 任意互联网用户可访问完整 API schema，包含所有端点路径、请求格式、字段说明、业务逻辑。攻击者可从中提取金额阈值、审批规则等敏感信息。

**修复建议：** 改为 permission_classes=[permissions.IsAuthenticated]

---

#### 漏洞5：身份证/银行卡明文存储

**文件：** `apps/finance/models.py:18-20`

```python
id_card = models.CharField('身份证号', max_length=18, blank=True, default='')
bank_card = models.CharField('银行卡号', max_length=30, blank=True, default='')
```

**风险场景：** 数据库被拖库或磁盘被非法访问时，身份证号和银行卡号直接泄露。

**修复建议：** 使用 Fernet 对称加密：
```python
from cryptography.fernet import Fernet
# 存储时加密：fernet.encrypt(id_card.encode())
# 读取时解密：fernet.decrypt(encrypted_value).decode()
```

---

#### 漏洞6：两套工资税计算算法导致财务数据失真

**文件：** `apps/finance/views.py:1077-1129` vs `apps/finance/models.py:650-746`

| 接口 | 算法 | 函数位置 |
|------|------|---------|
| calc_preview (正确) | 累计预扣法（7级超额累进） | calculate_wage_tax() models.py:650 |
| calc (错误) | 单月税率表（7级超额累进） | calc_tax() views.py:1081 |

calc_tax 的问题是每月独立查表计算，而非累计应税收入查表。这导致员工月度工资波动时税额计算错误，用户用 calc 预览的结果与实际扣税金额不一致。

**示例：** 某员工1-6月工资均为20000元
- 正确算法（累计预扣法）：每月税额约 778元
- 错误算法（单月查表）：每月税额约 1690元（差额912元/月）

---

### 2.2 高风险问题

#### 问题7：无请求频率限制 / 无暴力破解保护

- reset_password 接口无图形验证码
- 登录接口无失败次数限制
- 无 IP 黑名单机制
- 攻击者可以无限次尝试密码爆破

#### 问题8：超管 bypass 所有公司边界

```python
# finance/views.py:65-66
if user.is_superuser:
    return None  # 不限制公司，可访问所有公司数据
```

超管账户滥用或被盗 = 全量数据泄露

#### 问题9：密码重置无复杂度校验

```python
# core/views.py:439
new_password = request.data.get('new_password')
# 无任何校验
user.set_password(new_password)
```

#### 问题10：PyPDF2 已知 CVE 未修复

PyPDF2 == 3.0.1 已知漏洞：CVE-2022-4060（路径遍历）、CVE-2023-27103 等
建议升级到 pypdf >= 4.0.0

#### 问题11：无单元测试

项目中无 tests/ 目录，无法保证代码变更的安全性。

---

### 2.3 中等风险

#### 问题12：calc_preview 与 calc 算法不一致

与漏洞6相关，前端预览使用 calc_preview（正确），但某些批量计算场景可能调用 calc（错误）。

#### 问题13：报表 net_salary 计算错误

```python
# views.py:1617
'total_net': float(wage_total),  # 注释说"粗略用总额代替"
```

#### 问题14：登录失败无审计记录

审计日志只记录成功登录。密码爆破攻击无痕迹可追踪。

#### 问题15：NotificationChannel 无多租户隔离

```python
# notifications/views.py:17-22
def get_queryset(self):
    """多租户隔离已移除 - 所有用户可见所有通知渠道"""
    queryset = NotificationChannel.objects.filter(is_deleted=False)
    return queryset  # 所有认证用户可见所有渠道
```

用户可枚举系统中所有通知渠道配置（Webhook URL/机器人Token等）。

#### 问题16：CORS 配置依赖环境变量

```python
CORS_ALLOWED_ORIGINS = [
    for h in os.environ.get('CORS_ALLOWED_ORIGINS', '').split(',')
    if h
]
```

如果环境变量未设置或为空，任何 Origin 都可以访问。

---

## 三、多租户数据隔离全面审计

### 3.1 隔离机制正确的模块

| 模块 | ViewSet | 隔离方式 | 评估 |
|------|---------|---------|------|
| 收入 | IncomeViewSet | filter(company_id=cid) | 正确 |
| 支出 | ExpenseViewSet | filter(company_id=cid) | 正确 |
| 工资 | WageRecordViewSet | filter(company_id=cid) | 正确 |
| 发票 | InvoiceViewSet | filter(company_id=cid) | 正确 |
| 应收应付 | ARAPViewSet | 强制用户公司ID | 正确 |
| 客户 | ClientViewSet | filter(company_id=user.company_id) | 正确 |
| 供应商 | SupplierViewSet | filter(company_id=user.company_id) | 正确 |
| 合同 | ContractViewSet | filter(company_id=user.company_id) | 正确 |
| 审批 | ApprovalFlowViewSet | filter(company_id=user.company_id) | 正确 |
| 任务 | TaskViewSet | filter(project__company_id=user.company_id) | 正确 |

### 3.2 隔离失效模块

| 模块 | 问题 | 严重度 |
|------|------|--------|
| CompanyViewSet | IDOR漏洞1：无公司关联用户返回所有公司 | 致命 |
| CompanyViewSet.bank_accounts | IDOR漏洞2：可获取任意公司银行账户 | 致命 |
| bank_import_views (所有函数) | 无公司权限校验 | 致命 |
| NotificationChannel | 所有用户可见所有渠道 | 中等 |

---

## 四、业务逻辑正确性评估

### 4.1 正确的实现

| 功能 | 位置 | 说明 |
|------|------|------|
| 累计预扣税算法 | models.py:650-746 | 7级超额累进，公式正确，符合中国个税规定 |
| 工资 calc_preview | views.py:656-698 | 前后端算法一致 |
| 审批流超时升级 | flow_builder.py | 按金额自动路由 + 超时升级 |
| 银行流水去重 | bank_import_views.py | bank_serial + transaction_date + amount |
| 发票核销 | bank_import_views.py | 预加载优化，避免N+1 |
| 工资条邮件发送 | wage_email_service.py | 独立 service |
| 公司简称映射 | import_excel.py:366-375 | 软编码，运营可配置 |

### 4.2 业务逻辑错误

| 问题 | 位置 | 影响 |
|------|------|------|
| calc_tax 使用单月税率表 | views.py:1081-1089 | 税额计算错误，与实际不符 |
| 报表 net 字段用总额代替 | views.py:1617 | 财务数据失真（已知为近似值） |
| 多租户隔离逻辑缺失 | CompanyViewSet | IDOR漏洞 |

---

## 五、数据安全与加密

### 5.1 敏感数据存储现状

| 数据类型 | 字段位置 | 存储方式 | 风险等级 |
|---------|---------|---------|---------|
| 用户密码 | core/models.py | Django PBKDF2+SHA256 | 安全 |
| 身份证号 | finance/models.py:Employee.id_card | 明文 CharField | 高 |
| 银行卡号 | finance/models.py:Employee.bank_card | 明文 CharField | 高 |
| 银行流水对方账号 | finance/models_bank.py | 明文 | 高 |
| API SECRET_KEY | settings.py | 硬编码+环境变量 | 高 |
| 数据库密码 | settings.py:PG_PASSWORD | 环境变量默认值 | 中 |
| 员工薪资 | WageRecord.net_salary | 明文 | 高 |
| 税务数据 | Income/Expense | 明文 | 高 |
| 通知渠道凭证 | NotificationChannel.config | 明文JSON | 中 |

### 5.2 SECRET_KEY 风险

```python
# settings.py:18-21
SECRET_KEY = os.environ.get('SECRET_KEY', '02)mkk9yif^d!rsg26f1epk%%k)xe9cf6)0odggsf-3)8(!^yf')
if not os.environ.get('SECRET_KEY'):
    warnings.warn('SECRET_KEY not set — using insecure default.', RuntimeWarning)
```

如果部署时环境变量未正确设置，使用了不安全的默认密钥。

---

## 六、审计与合规

### 6.1 审计机制亮点

| 机制 | 实现 | 评估 |
|------|------|------|
| 操作审计 | audit.py 信号拦截所有 post_save/post_delete | 全面 |
| 线程安全 | threading.local() 设计 + pause/resume 嵌套 | 优秀 |
| 批量导入兼容 | on_commit() 延迟写入，不干扰原子事务 | 周全 |
| 登录日志 | LoginLog 模型 | - |
| 权限变更审计 | PermissionAuditLog | - |

### 6.2 审计缺陷

| 问题 | 影响 |
|------|------|
| 登录失败不记录 | 密码爆破无痕迹 |
| Swagger 访问不记录 | API schema 被爬取无感知 |
| Excel 导入导出操作不记录 | 批量数据操作无追踪 |
| 审计日志字段无加密 | 审计日志本身含敏感数据 |

---

## 七、依赖安全

### 7.1 安全依赖

```
Django==5.2.13          无已知CVE
djangorestframework==3.17.1  无已知CVE
django-filter==25.2     无已知CVE
django-cors-headers==4.9.0   无已知CVE
drf-spectacular==0.29.0 无已知CVE
openpyxl==3.1.5         安全解析器
gunicorn==26.0.0        无已知CVE
psycopg2-binary==2.9.11 无已知CVE
Pillow==12.2.0          无已知CVE
PyYAML==6.0.3           无已知CVE
cryptography>=42.0.0    无已知CVE
certifi==2026.4.22      无已知CVE
idna==3.13              无已知CVE
```

### 7.2 需要升级

| 库 | 当前版本 | 已知CVE | 建议版本 |
|---|---------|---------|---------|
| PyPDF2 | 3.0.1 | CVE-2022-4060, CVE-2023-27103 | pypdf >= 4.0.0 |

---

## 八、代码质量

### 8.1 超大文件问题

| 文件 | 行数 | 问题 | 建议 |
|------|------|------|------|
| finance/views.py | 2041行 | 包含11个ViewSet，职责过重 | 按业务拆分 |
| tasks/models.py | 21246行 | 超大模型文件 | 拆分到多个模型文件 |
| import_excel.py | 740行 | 混合多种导入逻辑 | 按模块拆分 |

### 8.2 代码组织亮点

- flow_builder.py - 清晰的审批流构建逻辑
- audit.py - 信号 + thread-local 的巧妙设计
- bank_import_views.py - 原子事务 + 幂等去重 + 预加载优化

### 8.3 其他问题

| 问题 | 位置 | 影响 |
|------|------|------|
| .bak 备份文件残留 | bank_import_views.py.bak | 可能泄露旧代码逻辑 |
| 无单元测试 | 整个项目 | 代码变更风险高 |
| 超大函数 | calc_tax / _detect_往来_subtype 等 | 可维护性差 |

---

## 九、部署与运维

### 9.1 当前部署配置

```
Gunicorn: 2 workers, port 8001
Nginx: 反向代理 + 静态文件
数据库: PostgreSQL (外置)
备份: 每日 3:00 AM, 保留 5+ 天
```

### 9.2 备份状况

| 类型 | 路径 | 大小 | 评估 |
|------|------|------|------|
| 工程代码 | /root/engineering-new/ | - | Git管理 |
| 数据库 | PostgreSQL外置 | - | 每日备份 |
| Hermes状态 | /root/.hermes/state.db | 310 MB | 异常大 |
| 定时任务 | /root/.openclaw/ | 140 MB | 无备份 |

**风险：**
- 无异地容灾（单机备份）
- state.db 310MB 需定期清理
- .openclaw 目录无备份策略

---

## 十、问题汇总（按严重度排序）

```
致命（必须立即修复）:
  [1] CompanyViewSet IDOR - 非超管无公司关联时返回所有公司
  [2] CompanyViewSet.bank_accounts - 任意公司银行账户泄露
  [3] bank_import_views 全局无公司权限校验
  [4] 身份证/银行卡明文存储
  [5] Swagger 对未认证用户开放 - API schema 全泄露
  [6] calc 与 calc_preview 算法不一致，calc 使用错误算法

高风险:
  [7] 无请求频率限制 / 无暴力破解保护
  [8] 超管 bypass 所有公司边界
  [9] 密码重置无复杂度校验
  [10] PyPDF2 已知 CVE 未修复
  [11] 无单元测试

中等:
  [12] calc_preview/calc 算法不一致导致预览失真
  [13] 报表 net_salary 计算错误（已知为近似值）
  [14] 登录失败无审计记录
  [15] NotificationChannel 无多租户隔离
  [16] state.db 310MB 需定期清理
  [17] 无异地备份容灾
  [18] finance/views.py 2041行超大文件
  [19] tasks/models.py 21246行超大文件
  [20] .bak 备份文件残留
```

---

## 十一、优先修复路线图

### 第一优先级（1-2天内，止血）

1. 修复 CompanyViewSet IDOR - 加 else return Company.objects.none()
2. Swagger 添加认证 - permission_classes=[IsAuthenticated]
3. bank_import_views 加公司边界校验 - 校验 company_id 与用户归属

### 第二优先级（1周内）

4. 身份证/银行卡字段加密存储
5. calc_tax 算法统一 - 删除 calc 或修正为累计预扣法
6. PyPDF2 升级到 pypdf >= 4.0.0
7. NotificationChannel 恢复多租户隔离

### 第三优先级（1个月内）

8. 添加单元测试框架
9. 登录失败审计记录
10. 请求频率限制（django-ratelimit）
11. state.db 清理脚本
12. 异地备份机制

### 长期优化

13. 拆分 finance/views.py（按 Income/Expense/Wage/Invoice 分文件）
14. 拆分 tasks/models.py
15. 添加 Redis 缓存层
16. 密码复杂度校验

---

## 附录

### A. 项目关键文件路径

| 文件 | 路径 |
|------|------|
| 主配置文件 | /root/engineering-new/config/settings.py |
| URL路由 | /root/engineering-new/config/urls.py |
| 财务视图 | /root/engineering-new/apps/finance/views.py |
| 财务模型 | /root/engineering-new/apps/finance/models.py |
| 核心认证 | /root/engineering-new/apps/core/auth.py |
| 审计模块 | /root/engineering-new/apps/core/audit.py |
| 审批流构建 | /root/engineering-new/apps/approvals/flow_builder.py |
| 银行流水导入 | /root/engineering-new/apps/finance/bank_import_views.py |
| Excel导入 | /root/engineering-new/apps/core/import_excel.py |

### B. 关键 API 端点

| 功能 | 端点 |
|------|------|
| 收入列表 | GET /api/finance/incomes/ |
| 支出列表 | GET /api/finance/expenses/ |
| 工资单列表 | GET /api/finance/wages/ |
| 工资预览 | POST /api/finance/wages/calc_preview/ |
| 工资错误计算 | POST /api/finance/wages/calc/ |
| 发票列表 | GET /api/finance/invoices/ |
| 公司列表 | GET /api/finance/companies/ |
| 银行流水确认 | POST /api/finance/import/bank-statement/confirm/ |
| 应收应付 | GET /api/finance/ar-ap/ |
| API Schema | GET /api/schema/ |
| API Docs | GET /api/docs/ |

### C. 相关环境变量

```bash
SECRET_KEY              # Django密钥（必须设置）
PG_DATABASE            # PostgreSQL数据库名
PG_USER                 # PostgreSQL用户名
PG_PASSWORD            # PostgreSQL密码
PG_HOST                # PostgreSQL主机
TENANT_MODE            # 租赁模式（standalone/subscription）
DEFAULT_COMPANY_ID     # 买断版默认公司ID
ALLOWED_HOSTS          # 允许的域名/IP
CORS_ALLOWED_ORIGINS   # 允许的CORS源
```

---

报告生成时间：2026-05-13
审查工具：A001 (hermes-b001) autonomous code review
审查范围：全盘代码审查（不含测试修改）
