# 事故报告：2026-04-28 工程管理系统 504/ERR_CONNECTION_RESET 故障

## 事故概述
- **时间**: 2026-04-28 凌晨 01:00 - 01:30
- **现象**: 系统间歇性出现 504 Gateway Timeout 和 ERR_CONNECTION_RESET，页面切换卡死 1-2 分钟
- **影响范围**: 全系统所有页面，尤其中央仪表盘、数据统计、任务看板页面
- **持续时间**: 约 30 分钟

## 根因分析（真实根因）

### 直接原因
**gunicorn workers 全部阻塞**，服务器无法响应新请求。

当所有 4 个 worker 都 hang 在处理请求时：
- nginx 等待 60 秒后返回 504
- 客户端浏览器等待超时后返回 ERR_CONNECTION_RESET
- 系统完全无响应

### 根本原因
**前端页面串行/无节制地请求大量数据，同步阻塞了所有 gunicorn worker。**

具体触发点：

1. **数据统计页面 (stats.html) 的 DOMContentLoaded**
   - 串行发起 10 个 fetch 请求（companies, projects, tasks, wages, incomes, expenses, contracts, equipment, approvals/flows）
   - 其中 `/api/approvals/flows/?status=pending` 返回大量数据

2. **中央仪表盘 (dashboard.html) 的 `loadApprovalStats()`**
   - 调用 `/api/approvals/flows/` 获取所有审批流记录
   - 审批流 API 没有分页，`queryset = ApprovalFlow.objects.all()`
   - 当审批流记录多时，此 API 会长时间占用 worker

3. **任务看板 (flow_board.html) 的 `loadTasks()`**
   - 访问 `/api/tasks/tasks/?page_size=100`
   - TaskSerializer 中 `get_flow_instance()` 对每条 task 执行数据库查询
   - 虽然 `get_queryset()` 有 `prefetch_related`，但 `flow_instance` 的 `current_node` 访问仍可能触发额外查询
   - 39 个 task 在前端的串行渲染也耗时

4. **员工详情页面** (wage_list.html 弹窗)
   - 选李四时触发 `onEmployeeSelect` → `autoFillSocialInsurance` → 查社保配置
   - 正常情况下很快，但和上面几个问题叠加后雪上加霜

### 加重因素
- nginx upstream 配置错误：端口 80 的 blue-backend 指向了 8000（无服务），而不是实际的 8001
- 这导致 port 80 的请求本来就无法正常路由
- gunicorn `--workers 4 --timeout 300`：300 秒超时让僵尸 worker 长时间占用

## 修复措施

### 已实施（临时）
1. `pkill -9 gunicorn` 清除所有僵尸 worker
2. 重启 gunicorn：`--workers 4 --timeout 300 --keep-alive 10`
3. nginx upstream 从 8000 修正为 8001

### 待实施（根本解决）
1. **审批流 API 分页**：`ApprovalFlowViewSet` 添加分页，限制默认 page_size
2. **Dashboard/Stats 页面去串行化**：将 10 个 fetch 改为 Promise.all 并行，并加超时
3. **TaskStageInstance N+1 检查**：`get_flow_instance()` 方法中 `TaskStageInstance.objects.filter()` 需要加索引或缓存
4. **任务看板渲染优化**：39 个 task 卡片的前端渲染本身不慢，但如果有更多 task 需要考虑虚拟列表
5. **gunicorn 考虑换用 gthread 或 eventlet workers**：提高并发能力

## 经验教训

1. **永远不要在前端 DOMContentLoaded 中串行发多个 fetch**
   - 正确做法：Promise.all 并行 + timeout
   - 每个 fetch 都可能 hang 住一个 worker

2. **Django ViewSet 的 queryset 务必加 select_related/prefetch_related**
   - N+1 查询是性能杀手
   - Serializer 中的每个 `source='xxx.yyy'` 字段都可能触发 N+1

3. **没有分页的 list API 是危险的**
   - ApprovalFlow.objects.all() 在记录多时会把 worker 堵死
   - 所有 list API 必须有分页

4. **nginx upstream 配置变更后必须验证**
   - 8000 → 8001 这个错误配置不知道存在了多久
   - 配置变更后立即 curl 测试

5. **ERR_CONNECTION_RESET 不是网络问题**
   - 客户端和服务器之间的连接被重置
   - 常见原因：服务器进程崩溃、worker 全阻塞、防火墙

## 数据清理建议
- 36 条垃圾 expense 记录（amount=999,999,999.99）
- 考虑清理或归档旧的 ApprovalFlow 记录

## 时间线
- 01:00 左右 - 系统开始出现 504
- 01:16 - 发现 nginx 8000 问题，修正为 8001
- 01:26 - gunicorn workers 再次全部阻塞
- 01:29 - pkill -9 + 重启 gunicorn
- 01:30+ - 系统恢复正常
