# 菜单闪现 + 跳转登录页 根因分析报告

**分析时间：** 2026-06-01
**分析人：** hermes-a002
**影响范围：** 客户管理、采购管理、运营管理、系统管理模块

---

## 一、问题描述

用户反馈：
1. **模块页面右侧闪现左侧菜单栏** — 点击客户管理/采购管理/运营管理/系统管理时，页面右侧短暂出现左侧菜单
2. **top页面报错跳转登录页** — 菜单内部页面渲染时报错，直接跳转到 `/login/`
3. **来回切换菜单多次闪退到登录页** — 短时间快速切换几个模块，最终被踢到登录页

---

## 二、系统架构

```
┌──────────────────────────────────────────┐
│  base.html (外层页面)                      │
│  ┌──────┐  ┌───────────────────────────┐  │
│  │      │  │  main-content              │  │
│  │sidebar│  │  margin-left: 260px       │  │
│  │260px │  │  ┌───────────────────────┐ │  │
│  │      │  │  │ tabs (nav-tabs)       │ │  │
│  │      │  │  ├───────────────────────┤ │  │
│  │      │  │  │ iframe                │ │  │
│  │      │  │  │ ┌───────────────────┐ │ │  │
│  │      │  │  │ │ base_content.html │ │ │  │
│  │      │  │  │ │ (无sidebar)       │ │ │  │
│  │      │  │  │ └───────────────────┘ │ │  │
│  └──────┘  └───────────────────────────┘  │
└──────────────────────────────────────────┘
```

**关键结构：**
- 外层页面 `base.html`：侧边栏 260px + 主内容区 `margin-left: 260px`
- 模块页面（CRM/采购/运营/系统）继承 `base.html`，内容区包含 tab 切换 + iframe
- iframe 内页面继承 `base_content.html`（清空 sidebar 块）
- `app.js` 在 DOMContentLoaded 时运行 JS 注入 CSS 修正

---

## 三、根因分析

### 问题1：页面右侧闪现左侧菜单栏

**根因：JS 修正前 CSS 已渲染，产生 260px 空白闪烁**

`base_content.html` 只有：
```django
{% extends "base.html" %}
{% block sidebar %}{% endblock %}
```

`app.css` 定义了：
```css
.main-content { margin-left: var(--sidebar-width); }
```

`app.js` 在 `DOMContentLoaded` 时检测 iframe 并注入修复 CSS：
```javascript
if (window.self !== window.top) {
    // 设置 margin-left: 0!important
}
```

**时序问题：**
```
1. HTML 加载 ───→ CSS 应用到 DOM ───→ DOMContentLoaded ───→ JS 注入修正 CSS
                    │                                          │
                    │  margin-left: 260px                       │  margin-left: 0
                    │  内容区偏移260px（≈侧边栏宽度）            │  恢复正常
                    └── 闪现 ──────────────────────────────────→│
```

这 50-300ms 的间隔，用户看到内容区右移 260px（看似"侧边栏在右侧闪现"）。

**严重程度：** 所有 iframe 内页每次加载都会复现，包括：
- CRM 的4个tab（客户/合同/供应商/商机）
- 采购的3个tab（申请/订单/入库）
- 运营的3个tab（物料/设备/报修）
- 系统的6个tab

### 问题2：top页面报错跳转登录页

**根因：`checkAuth()` 强依赖 API 端点，失败后跳 `/login/`**

`app.js` 中的核心认证逻辑：
```javascript
function checkAuth() {
    if (window.self !== window.top) return;  // iframe 跳过
    fetchWithTimeout('/api/core/auth/user/', ..., 8000)
    .then(function(response) {
        if (response.ok) return;  // ✅ 正常
        // 403/500 重试2次，失败后 redirect
        if (authAttempts < MAX_AUTH_RETRIES && ...) { retry(); return; }
        window.location.href = '/login/';  // ❌ 跳转
    })
    .catch(function(err) {
        if (err.name === 'AbortError') return;  // ✅ 导航中止不处理
        // 网络错误重试2次，失败后 redirect
        if (authAttempts < MAX_AUTH_RETRIES) { retry(); return; }
        window.location.href = '/login/';  // ❌ 跳转
    });
}
```

**触发场景：**
| 场景 | 原因 | 概率 |
|:----|:-----|:----:|
| 页面加载时 API 返回 500 | gunicorn worker 不稳定 | 低 |
| 页面加载时 API 返回 403 | session 未就绪 | 低 |
| 页面加载时 API 超时 (8s) | 4个worker同时处理大量请求 | 中 |
| 快速切换页面时 fetch 被 abort | 旧页面 beforeunload 触发 abortAllFetches() | 高 |

> **关键发现：** 当用户快速切换菜单时，旧页面的 `beforeunload` 触发 `abortAllFetches()`，如果新页面的 auth fetch 正好在旧页面被关闭的瞬间发起，可能被旧页面的 AbortController 意外冲突。虽然 `_sharedControllers` 做了隔离，但 `DOMContentLoaded` 和 `beforeunload` 的时序竞态难以完全避免。

### 问题3：来回切换菜单多次闪退

**根因：同问题2，快速切换放大了 API 失败的概率**

额外因素：
1. 每隔个切换都是 **完整页面刷新**（非 SPA），每次都触发了 `checkAuth()`
2. 4个 gunicorn worker 在快速切换时可能被旧的请求占满
3. `SESSION_SAVE_EVERY_REQUEST = True` 让每次请求都写 session，增加磁盘 I/O 竞争

### 问题4：2个 CRM 内页用错模板

`contact_followup_list.html` 和 `contract_detail.html` 使用了 `base.html` 而非 `base_content.html`。当它们被作为 iframe 子页面加载时，会多渲染一个侧边栏在 iframe 内部。

不过好在 `app.js` 的 iframe 检测（line 8-13）会注入 CSS `display:none!important` 隐藏额外渲染的 sidebar，所以这个错误被 JS 掩盖了大部分，但仍有以下风险：
- JS 注入前侧边栏会短暂可见
- 如果侧边栏内部的脚本/样式冲突，可能报错

---

## 四、修复方案

### 修复A：`base_content.html` CSS 闪现（P0）

**策略：** 从 CSS 层面解决，不依赖 JS 运行时修复

```html
{% extends "base.html" %}
{% block sidebar %}{% endblock %}
{% block styles %}
<style>
/* iframe 内页不需要侧边栏边距 */
.main-content { margin-left: 0 !important; }
</style>
{% endblock %}
```

**效果：** CSS 在 HTML 解析阶段即生效，远早于 JS 的 DOMContentLoaded，彻底消除时序窗口。

### 修复B：2个CRM模板用 `base_content.html`（P1）

**文件：**
- `templates/crm/contact_followup_list.html` → `{% extends "base_content.html" %}`
- `templates/crm/contract_detail.html` → `{% extends "base_content.html" %}`

### 修复C：`checkAuth()` 降低敏感度（P0）

**策略：** API 失败时不跳登录页，改为静默降级

```javascript
function checkAuth() {
    if (window.self !== window.top) return;
    var retried = false;
    fetchWithTimeout('/api/core/auth/user/', { credentials: 'include' }, 5000)
    .then(function(response) {
        if (response.ok) { /* 正常 */ }
        else if (!retried) { retried = true; setTimeout(checkAuth, 1000); }
        /* 失败也不跳转，用户后续操作会在服务端验证时自动跳 */
    })
    .catch(function(err) {
        if (err.name === 'AbortError') return;
        /* 网络错误也不跳转 */
    });
}
```

**原理：** 前端 auth check 是防御性检查，非必要。真正的认证校验在 Django 中间件和 view 层面已经做了——未认证用户无法访问受保护页面。前端强行跳 `/login/` 是画蛇添足，反而制造了本不应发生的闪退。

---

## 五、验证方案

```
修复A 验证：
  → 打开 Chrome DevTools Network → 关闭缓存
  → 快速切换 CRM/采购/运营/系统页面
  → 观察 iframe 内容区是否还有 260px 的闪烁
  → 录制视频逐帧确认

修复B 验证：
  → 导航到 CRM → 点击某个客户的"跟进记录"或"合同详情"
  → 页面应正常渲染，无额外侧边栏

修复C 验证：
  → 断开网络 → 刷新页面
  → 不应再跳转到 /login/（之前会跳）
  → 恢复网络，页面应正常运行

综合验证：
  → 快速切换 CRM → 采购 → 运营 → 系统 → 控制台 → ... × 10次
  → 不应出现闪退到登录页
```

---

## 六、遗留问题

1. **session 写竞争：** `SESSION_SAVE_EVERY_REQUEST = True` 在高峰时可能产生 session 锁冲突。该配置已存在多年，未报告相关事故，可观察不改。
2. **gunicorn worker 健康：** 4 个 worker 在快速页面切换时可能不够用。如仍有闪退，可考虑增至 6-8 个 worker（需评估内存）。
3. **全页刷新 vs SPA：** 当前架构每次菜单切换都重新加载整个 HTML（包括侧边栏、CSS、JS）。若未来性能需求高，可考虑改为 SPA 架构。
