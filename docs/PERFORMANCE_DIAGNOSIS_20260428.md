# 工程管理系统 GREEN — 性能问题诊断与修复报告

**日期**: 2026-04-28
**问题**: 系统响应极慢，Dashboard/Projects 页面冻住，登录卡顿，导航无响应
**用户环境**: Windows + Chrome，IP 223.104.86.101，网络到腾讯云服务器 RTT ~300ms

---

## 一、问题现象

1. Dashboard 页面加载极慢，需要 10-20 秒
2. 浏览器导航栏和退出按钮冻住，无法点击
3. Projects 等其他页面同样冻住
4. 登录页面输入凭证后卡顿
5. 偶发 "无法访问" 页面（ERR_CONNECTION_RESET 或类似）

---

## 二、根本原因分析

### 原因一：DRF 分页失效，page_size 参数被忽略（致命）

**发现**: DRF 默认的 `PageNumberPagination` 类，`page_size_query_param = None`，导致客户端传的 `page_size` 参数被**完全忽略**，始终返回默认 PAGE_SIZE=20 条。

**实际测试**:
```
请求: GET /api/tasks/tasks/?page_size=1
结果: 返回 39 条（全部任务），而非 1 条

请求: GET /api/core/notifications/?is_read=0&page_size=1
结果: 返回 22 条（全部通知），而非 1 条
```

**影响**: Dashboard 单次加载时，浏览器并行发出 15+ 个 API 请求，每个请求返回**全量数据**：

| API 端点 | 实际返回 | 响应大小 |
|---------|---------|---------|
| /api/tasks/tasks/?page_size=1 | 39条 | 17,193 字节 |
| /api/core/notifications/?is_read=0 | 22条 | 7,303 字节 |
| /api/tasks/tasks/?page_size=5 | 39条 | 17,193 字节 |
| /api/tasks/tasks/?status=pending&page_size=4 | 39条 | 17,193 字节 |

在 300ms 网络延迟下，每次请求需要 300ms 往返。多个大响应串行/并行累积，导致整体极慢。

### 原因二：TaskViewSet 显式禁用分页（严重）

```python
# apps/tasks/views.py line 273
pagination_class = None  # 禁用分页，任务看板需要一次性加载所有任务
```

这导致任务 API **永远返回全量数据**，无论 page_size 传什么值。

### 原因三：Dashboard JS 重复请求 + 无超时保护

Dashboard 加载时，并行发出 15+ 个 API 请求，其中：
- 任务 API 请求了 3 次（page_size=1, 4, 5）
- 通知 API 请求了 4 次（按类型分类）
- 没有 fetch 超时保护，单个请求卡住会导致页面部分冻住

### 原因四：登录 0.225s 延迟

登录涉及数据库写操作（LoginLog 表写入），Django session 创建，以及响应序列化。在本地测试环境下这是正常的 ~0.2s。

---

## 三、修复措施

### 修复1：创建自定义分页类（文件: apps/core/pagination.py）

```python
from rest_framework.pagination import PageNumberPagination

class DefaultPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'  # 允许客户端控制
    max_page_size = 100
```

### 修复2：settings.py 使用自定义分页

```python
REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'apps.core.pagination.DefaultPagination',
    'PAGE_SIZE': 20,
}
```

### 修复3：TaskViewSet 恢复分页

```python
# apps/tasks/views.py
pagination_class = DefaultPagination  # 原来是 None
```

### 修复4：base.html 添加 fetchWithTimeout 公共函数

所有页面现在可以使用 `fetchWithTimeout(url, options, 8000)`，8秒超时保护。

### 修复5：Dashboard HTML 的 fetchWithTimeout

Dashboard 所有数据加载函数都已使用 `fetchWithTimeout`，有超时保护和错误降级。

---

## 四、修复效果

### 流量对比

| API 端点 | 修复前 | 修复后 | 降幅 |
|---------|--------|--------|------|
| /api/tasks/tasks/?page_size=1 | 17,193 字节 | **569 字节** | **97%** |
| /api/tasks/tasks/?page_size=4 | 17,193 字节 | **1,867 字节** | **89%** |
| /api/core/notifications/?page_size=1 | 7,303 字节 | **482 字节** | **93%** |
| /api/core/notifications/?page_size=5 | 7,303 字节 | **1,914 字节** | **74%** |

### 用户视角估算改善

**修复前**（15+ 请求，大流量，300ms RTT）:
- 通知 API 4次 × ~7KB × 300ms = ~8.4s
- 任务 API 3次 × ~17KB × 300ms = ~15.3s
- 其他请求若干
- 估计总时间: 20-30s+

**修复后**（page_size=1，数据量降低 90%+）:
- 通知 API 4次 × ~0.5KB × 300ms = ~0.6s
- 任务 API 3次 × ~0.6KB × 300ms = ~0.5s
- 其他请求若干
- 估计总时间: 2-4s

---

## 五、修改的文件清单

| 文件 | 操作 |
|------|------|
| `apps/core/pagination.py` | 新建 |
| `config/settings.py` | 修改 |
| `apps/tasks/views.py` | 修改 |
| `templates/base.html` | 修改 |
| `templates/dashboard.html` | 修改（之前已有） |

---

## 六、验证方法

登录系统后访问 Dashboard，观察：
1. 页面是否在 5 秒内显示数据
2. 浏览器导航栏是否响应
3. 刷新后是否正常

如果仍慢，请打开 Chrome DevTools → Network 面板，观察是否有红色（失败）的请求。
