# GREEN ERP 导入逻辑思维导图

---

## 1. 银行流水导入

### 1.1 核心流程

```
用户上传银行流水文件
    ↓
选择银行类型（前端传 bank_code）
    ↓
Backend: bank_import_views.preview_bank_statement
    ↓
BankAdapter.detect() 确认银行类型匹配
    ↓
BankAdapter.parse() 解析流水数据
    ↓
BankStatement 表（原始数据）
    ↓
用户确认预览
    ↓
Backend: bank_import_views.confirm_bank_import
    ↓
映射写入 Income（收入）或 Expense（支出）
```

### 1.2 收支字段映射（1:1 还原原则）

| 银行流水字段 | → | Income/Expense 字段 | 说明 |
|-------------|---|---------------------|------|
| 交易日期 | → | occurred_date | 照写 |
| 收入金额（收入流水） | → | amount | 照写 |
| 支出金额（支出流水） | → | amount | 照写，取正数 |
| 对方账户名称 | → | counterparty_name | **直接写入，不做任何标准化** |
| 对方账户账号 | → | counterparty_account | 照写 |
| 摘要/备注 | → | description | 照写 |
| 交易类型 | → | transaction_type | 照写（收入/支出） |
| 流水号 | → | bank_serial | 照写 |
| 余额 | → | balance | 照写 |

**关键原则：对方名称（counterparty_name）= 流水文件里「对方账户名称」列原始内容，不做任何转换、不过滤、不标准化。**

### 1.3 银行适配器

| 银行 | 文件 | detect 方式 |
|------|------|------------|
| 平安银行 | bank_adapters.PingAnAdapter | 账号含 1500 专属标志 |
| 招商银行 | bank_adapters.CMBAdapter | 表头特征 |
| 中国银行 | bank_adapters.BOCAdapter | 表头特征 |
| 建设银行 | bank_adapters.CCBAdapter | 表头特征 |
| 农业银行 | bank_adapters.ABCAdapter | 表头特征 |
| 工商银行 | bank_adapters.ICBCAdapter | 表头特征 |
| 交通银行 | bank_adapters.COMMAdapter | 表头特征 |

### 1.4 已知修复记录（2026-05-17）

| 日期 | 文件 | 问题 | 修复 |
|------|------|------|------|
| 2026-05-17 | bank_import_views.py | confirm_bank_import 中 cp_name 写入前被 strip() 后 to_python 标准化为空 | 移除 normalize("CounterpartyName")，改为直接写入原始值 |

---

## 2. 任务创建 Bug 修复

### 2.1 Bug 1: 新建任务 400 错误（2026-05-19）

**问题现象**：
- 任务看板 → 新建任务 → 填写信息 → 点击保存 → 返回 `400 Bad Request`
- 控制台: `保存任务失败: Error: 保存失败`

**根因**：前端传 `assignee: "admin"`（username字符串），后端 `TaskCreateSerializer` 的 assignee 是隐式 `PrimaryKeyRelatedField`，只接受 integer pk

**修复**：`apps/tasks/views.py` 中 `TaskCreateSerializer.assignee` 改为 `SlugRelatedField(slug_field='username')`

**验证**：43/124 服务器均已修复，3次连续浏览器UI测试全部通过

### 2.2 Bug 2: Modal 对话框保存后不关闭（2026-05-19）

**问题现象**：
- 保存成功后对话框不关闭，用户需手动点 X
- Bootstrap Modal.hide() 单独调用有效，但在真实按钮点击流程中失效

**根因**：saveTask() 的 catch 分支只 showToast，**没有调用 taskModal.hide()**。当 API 返回任何错误（400/403/500）时进 catch 分支，modal 一直开着。成功分支里 hide() 本来有效，但之前测试失败率高是因为表单填写不完整导致 API 400，进入 catch 后 modal 没关

**修复**：`templates/tasks/flow_board.html` 第 993-996行 catch 块中加 `taskModal.hide()`

**43服务器**：`/root/engineering-new/templates/tasks/flow_board.html`
**124服务器**：`/home/ubuntu/engineering-new/templates/tasks/flow_board.html`（已同步）

**验证**：3次连续浏览器UI测试，全部通过：modal 正常关闭、新任务出现在列表、DB 正确入库

### 2.3 经验教训

1. **Bootstrap Modal.hide() 单独调用有效**：console 诊断证明 hide() 方法本身没问题
2. **catch 分支漏掉清理逻辑**：成功分支和 catch 分支都要关闭 modal，不能只修一个
3. **API 失败率高时不要误判为 hide() 不工作**：先确认请求是否真的成功了
4. **表单必填字段要填完整**：project=null 会导致 400，后端验证失败进 catch

---

## 3. 供应商导入

### 3.1 接口

```
POST /api/crm/import/suppliers/
```

### 3.2 Excel 列映射

| Excel 列名 | → | Supplier 字段 |
|-----------|---|---------------|
| 供应商名称 | → | name（必填） |
| 联系人 | → | contact_person |
| 联系电话 | → | contact_phone |
| 邮箱 | → | contact_email |
| 代理品牌 | → | brands |
| 地址 | → | address |
| 备注 | → | remark |

### 3.3 逻辑特点

- **必填**：供应商名称
- **自动生成编码**：`GYS-{年份}-{序号}`，如 GYS-2026-0001
- **状态默认**：`status='active'`（合作中）
- **公司关联**：company 字段为空（未实现多公司隔离时直接留空）

### 3.4 模型字段 vs 导入字段（差距分析）

| Supplier 模型字段 | 导入支持 | 说明 |
|-----------------|---------|------|
| code | ❌ | 自动生成 |
| name | ✅ | 必填 |
| company | ❌ | 留空 |
| counterparty_type | ❌ | 写死 enterprise |
| tax_id | ❌ | 未导入 |
| bank_account | ❌ | 未导入 |
| bank_name | ❌ | 未导入 |
| bank_branch | ❌ | 未导入 |
| bank_code | ❌ | 未导入 |
| contact_person | ✅ | |
| contact_phone | ✅ | |
| contact_email | ✅ | |
| brands | ✅ | |
| address | ✅ | |
| remark | ✅ | |
| status | ✅ | 写死 active |

---

## 4. 客户导入

### 4.1 接口

```
POST /api/crm/import/clients/
```

### 4.2 Excel 列映射

| Excel 列名 | → | Client 字段 |
|-----------|---|------------|
| 客户名称 | → | name（必填） |
| 客户类别 | → | category |
| 联系人 | → | contact_person |
| 联系电话 | → | contact_phone |
| 邮箱 | → | contact_email |
| 地址 | → | address |
| 备注 | → | remark |

### 4.3 逻辑特点

- **必填**：客户名称
- **自动生成编码**：`KH-{年份}-{序号}`，如 KH-2026-0001
- **类别默认值**：`企业客户`
- **公司关联**：company 字段为空

### 4.4 模型字段 vs 导入字段（差距分析）

| Client 模型字段 | 导入支持 | 说明 |
|----------------|---------|------|
| code | ❌ | 自动生成 |
| name | ✅ | 必填 |
| company | ❌ | 留空 |
| counterparty_type | ❌ | 写死 enterprise |
| tax_id | ❌ | 未导入 |
| bank_account | ❌ | 未导入 |
| bank_name | ❌ | 未导入 |
| source | ❌ | 未导入 |
| category | ✅ | |
| contact_person | ✅ | |
| contact_phone | ✅ | |
| contact_email | ✅ | |
| address | ✅ | |
| remark | ✅ | |
| is_active | ❌ | 写死 True |

---

## 5. 合同导入

### 5.1 接口

```
POST /api/crm/import/contracts/
```

### 5.2 Excel 列映射

| Excel 列名 | → | Contract 字段 |
|-----------|---|--------------|
| 合同编号 | → | contract_no（必填） |
| 合同名称 | → | name（必填） |
| 对方类型 | → | counterparty_type（客户/供应商） |
| 金额 | → | amount |
| 签订日期 | → | sign_date（必填） |
| 到期日期 | → | expire_date |
| 状态 | → | status |
| 备注 | → | remark |
| 客户名称 | → | 查找 Client FK |
| 供应商名称 | → | 查找 Supplier FK |
| 项目名称 | → | 查找 Project FK |

### 5.3 逻辑特点

- **必填**：合同编号、合同名称、金额、签订日期
- **FK 查找**：通过名称字符串查找已存在的 Client/Supplier/Project
- **对方类型映射**：`客户→client`，`供应商→supplier`

---

## 6. 核心差距总结

### 6.1 供应商/客户导入 vs 模型字段

**未实现的银行字段（两者都有）：**
- bank_account（银行账号）
- bank_name（开户行）
- bank_branch（开户行支行）
- bank_code（支行联行号）
- bank_addr（支行地址）
- tax_id（纳税人识别号）
- counterparty_type（对方类型：企业/个人/政府）

**未实现的客户专属字段：**
- source（客户来源）

### 6.2 潜在改进方向

1. **供应商/客户导入加上银行字段**：税号、银行账号、开户行等
2. **counterparty_type 智能化判断**：根据名称/税号自动判断企业/个人/政府
3. **供应商客户合并导入**：同一批数据里同时包含供应商和客户
4. **company 字段自动填充**：根据当前登录用户的公司自动填充