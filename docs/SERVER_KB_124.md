# 124服务器 共享知识库 (Server KB)

> 每次修改前必读。每次修复完成后，用浏览器做用户视角全方位验证，再更新本文件。
> 路径：`/home/ubuntu/engineering-new/docs/SERVER_KB_124.md`

---

## 服务器基本信息

| 项目 | 值 |
|------|-----|
| IP | 124.222.227.28 |
| SSH用户 | ubuntu |
| SSH密钥 | /root/.ssh/124_keys/124_hermes_ed25519 |
| SSH端口 | 22（默认） |
| Django项目 | /home/ubuntu/engineering-new |
| gunicorn端口 | 8001 |
| nginx端口 | 80 |
| 数据库 | PostgreSQL (settings_pg.py) |
| venv路径 | /home/ubuntu/engineering-new/venv |

---

## 当前问题清单 (截至 2026-05-21)

> ⚠️ **核心根因**：Invoice 表全部 77 条 company_id=NULL（遗留数据）。InvoiceViewSet 多租户过滤 `filter(company_id=user_cid)` 永远匹配不到，导致普通用户看到 0 条发票。

| 优先级 | 模块 | 问题 | 根因 | 状态 |
|--------|------|------|------|------|
| P0 | 发票管理 | Leyan 视图发票=0，stat=0 | Invoice 77条全部 company_id=NULL，普通用户过滤不到 | ✅ 已修复（get_queryset + invoice_summary 双修复） |
| P0 | 发票stat | stat 卡片 total_count/total_amount=0 | invoice_summary action 同样缺少 NULL 兼容 + 顶层聚合字段缺失 | ✅ 已修复 |
| P1 | 员工管理 | 页面空白 | Employee表为空（0条记录）+ 之前 session 丢失导致 403 | 数据层正常（YG-0001已创建），用户反映的可能是 session 问题 |
| P2 | 收支管理 | 初次加载显示"加载中" | loadYearOptions() 异步 JS，正常时序现象 | 已验证数据正常（admin 727条，Leyan 704条） |

---

## 关键数据分布（修正）

```
Invoice:   company_id=NULL → 77条（type=expense/支出发票55条 + type=income/收到发票22条）
           ⚠️ 注意：普通用户若只看 company_id=X 会匹配到 0 条！
Income:    company_id=1 → 727条（多租户过滤正常）
Expense:   company_id=1 → 1909条（多租户过滤正常）
Employee:  1条（YG-0001，测试员工）
Company:   2条（恒鑫兴智能科技id=1 / 恒鑫兴智能装备id=2）
```

---

## gunicorn 重启规范（重要！）

**必须从工程目录启动，否则 No module named 'config'：**
```bash
cd /home/ubuntu/engineering-new && nohup /home/ubuntu/engineering-new/venv/bin/gunicorn config.wsgi:application -c /home/ubuntu/engineering-new/gunicorn.conf.py >> /home/ubuntu/engineering-new/gunicorn.log 2>&1 &
```

**pkill -9 + 重启（最可靠）：**
```bash
pkill -9 -f "gunicorn.*config.wsgi"
sleep 2
cd /home/ubuntu/engineering-new && nohup .../gunicorn config.wsgi:application -c .../gunicorn.conf.py >> .../gunicorn.log 2>&1 &
```

**日志路径：** `/home/ubuntu/engineering-new/logs/gunicorn.log`

---

## 权限系统架构（124现状）

### 三层认证链
```
① 认证层（DRF SessionAuthentication）
  Cookie: sessionid → Django Session → User
  CSRF已通过 core/auth.py 的 CSRFExemptSessionAuthentication 豁免

② ViewSet RoleRequired 装饰器
  required_roles: 查 core_user_role（系统级，User.role 字段）
  action_perms: 查 core_role_permission（模块级，格式 finance:income:read）
  _perm_exists 兜底：code不在DB → 放行（防全站403）

③ get_queryset 租户过滤
  普通用户：filter(Q(company_id=user.company_id) | Q(company_id__isnull=True))
  超级用户（is_superuser=True）：跳过租户过滤
```

### 数据库权限数据（141条Permission）
```
core_permission: 141条记录（finance/task/project等模块）
core_role: 7个（系统管理员/财务经理/部门经理/人事经理/普通员工/游客/观察者）
core_user_role:
  admin (id=1) → 系统管理员（role=admin）
  Leyan (id=2) → 部门经理（role=manager）
core_role_permission: 系统管理员有全部finance/task/project权限
```

### 关键权限码（finance模块）
```
finance:income:read / write / delete
finance:expense:read / write / delete
finance:employee:read / write
finance:company:read / write
finance:invoice:read / write
finance:report:read  ← 报表模块（收入年份等数据依赖此权限）
```

### Finance模块过滤器差异
```
IncomeViewSet   → IncomeFilter   → 无 company_id 过滤字段（实际不过滤）
ExpenseViewSet  → ExpenseFilter → 无 company_id 过滤字段（实际不过滤）
InvoiceViewSet  → InvoiceFilter → 有 company_id 过滤字段（多租户关键点）
```

---

## 已修复历史（按时间顺序）

### 2026-05-21（下午）
| 序号 | 问题 | 修复方案 | 验证 |
|------|------|----------|------|
| 1 | gunicorn worker boot失败 | 启动命令加 `cd /home/ubuntu/engineering-new` | gunicorn.log 无错误 |
| 2 | 发票API返回count=0（gunicorn旧代码） | HUP reload 后正常 | API count=77 |
| 3 | 收支/发票"加载中"时序 | JS异步正常现象 | API返回正确数据 |
| 4 | 发票stat卡片显示0 | invoice_summary 缺少顶层聚合字段（total_count/total_amount/total_tax/net_amount） | expenseCount=55 ✅ |
| 5 | Leyan发票全0 | InvoiceViewSet.get_queryset: `filter(company_id=cid)` → `filter(Q(company_id=cid)\|Q(company_id__isnull=True))` | API count=77 ✅ |
| 6 | 发票stat为0（普通用户） | invoice_summary action: 同样加 Q(company_id__isnull=True) 兼容 + 顶层聚合改为直接 all_filtered.count()/aggregate | stat API ✅ |

---

## views.py 关键修改记录

路径：`/home/ubuntu/engineering-new/apps/finance/views.py`

### 1. 顶部 import（第1-2行）
```python
import functools
from django.db.models import Q   # ← 新增
from urllib.parse import urlparse
```

### 2. InvoiceViewSet.get_queryset（约第1347行）
```python
cid = _get_user_company_id(self.request.user)
if cid is not None:
    qs = qs.filter(Q(company_id=cid) | Q(company_id__isnull=True))
```

### 3. invoice_summary（约第1778行 + 第1814行）
```python
# 查询主体加 NULL 兼容
queryset = queryset.filter(Q(company_id=company_id) | Q(company_id__isnull=True))

# 顶层聚合改为直接对 all_filtered 计数/求和
all_filtered = Invoice.objects.filter(Q(company_id=cid)|Q(company_id__isnull=True))...
total_count = all_filtered.count()
total_amount = all_filtered.aggregate(total=Sum('amount'))['total'] or 0
total_tax = all_filtered.aggregate(total=Sum('tax_amount'))['total'] or 0
```

---

## 验证规范（修复后必做）

### 用户视角全方位验证流程
1. **登录验证**：登出 → 重新登录 → 确认侧边栏所有菜单可见
2. **员工管理**：访问 `/finance/employees/` → 有下拉公司选项 → 有数据行
3. **收支管理**：访问 `/finance/incomes/` → 年份/公司下拉框有选项 → 收入列表有数据
4. **发票管理**：访问 `/finance/invoices/` → stat 卡片有数字 → 表格有数据
5. **API健康检查**（浏览器Console）：
   ```js
   Promise.all([
     fetch('/api/finance/incomes/?page_size=2', {credentials:'include'}).then(r=>r.json()),
     fetch('/api/finance/invoices/?page_size=2', {credentials:'include'}).then(r=>r.json()),
     fetch('/api/finance/invoices/summary/?type=expense', {credentials:'include'}).then(r=>r.json()),
     fetch('/api/finance/reports/years/', {credentials:'include'}).then(r=>r.json())
   ]).then(([inc,inv,invsum,yrs])=>console.table({income:inc.count,invoice:inv.count,expense_summary:invsum.total_count,years:yrs.years}))
   ```

---

## 代码/模板同步记录

同步来源：43服务器（43.156.139.37）
同步方式：SCP（git push 因SSH权限失败）

| 日期 | 内容 | 目标路径 | 备注 |
|------|------|----------|------|
| 2026-05-21 | 权限修复包（approvals/finance/tasks views.py + templates + permissions.py） | /home/ubuntu/engineering-new/apps/ | commit ab521ed |
| 2026-05-21 | tasks model/migrations修复（project FK allow_null） | /home/ubuntu/engineering-new/apps/tasks/ | 需要 migrate |
| 2026-05-21 | 模板文件（income_list.html等，已含selectpicker fix） | /home/ubuntu/engineering-new/templates/finance/ | 已部署 |
| 2026-05-21 | views.py InvoiceViewSet NULL company_id 兼容修复 | /home/ubuntu/engineering-new/apps/finance/views.py | ✅ 已部署 |

---

## 联系方式 / 访问方式

```bash
# SSH连接124
ssh -i /root/.ssh/124_keys/124_hermes_ed25519 ubuntu@124.222.227.28

# SSH隧道（本地访问124的gunicorn:8001）
ssh -i /root/.ssh/124_keys/124_hermes_ed25519 -L 12444:127.0.0.1:8001 ubuntu@124.222.227.28

# 本地浏览器访问
http://127.0.0.1:12444/  （通过nginx:80）
```
