# 升级日志
**更新时间：** 2026-05-05

---

## 一、本次升级内容

### 1. 依赖版本升级

| 组件 | 升级前 | 升级后 | 说明 |
|------|--------|--------|------|
| gunicorn | 25.3.0 | 26.0.0 | 性能和稳定性改进 |
| Django | 生产环境 5.2.13（约束仅 <5.0） | 约束升级为 <6.0 | 解除版本约束不一致 |
| DRF | 3.17.1 | 3.17.1（已是最新） | requirements.txt 约束 >=3.14 兼容 |

### 2. Git 里程碑创建

| 标签 | 分支 | Commit | 说明 |
|------|------|--------|------|
| v2.1.0-commercial-ready | master | 72a41d4 | 商业化就绪版 |
| v2.0.0-standalone | standalone | 46c1392 | 独立用户版 |

### 3. 策略文档创建

- 新增 `docs/strategy/2026-05-05-knowledge-base-analysis.md` — 知识库分析与发展规划

---

## 二、43服务器验证结果

**验证时间：** 2026-05-05
**服务状态：** gunicorn 26.0.0 ✅ 正常运行
**验证方式：** 浏览器逐页验证（已登录 admin 账号）

### 页面验证清单

| # | 页面 | URL | 状态 | 备注 |
|---|------|-----|------|------|
| 1 | 控制台/Dashboard | /dashboard/ | ✅ 正常 | 显示项目/任务/审批/工资统计 |
| 2 | 设备管理 | /equipment/ | ✅ 正常 | 7台设备，分类筛选正常 |
| 3 | 设备BOM | /equipment/bom/ | ✅ 正常 | 设备配件管理页面加载 |
| 4 | 物料管理 | /materials/ | ✅ 正常 | 9种物料，库存/预警正常 |
| 5 | 审批管理 | /approvals/ | ✅ 正常 | 5条审批记录，显示待我审批4条 |
| 6 | 工资管理 | /finance/wages/ | ✅ 正常 | 显示刘柏春工资记录，筛选正常 |
| 7 | 合同管理 | /crm/contracts/ | ✅ 正常 | 12条合同，客户/供应商列表正常 |
| 8 | 用户管理 | /system/users/ | ✅ 正常 | 15个用户，含待审批5人 |
| 9 | 系统参数 | /system/settings/ | ✅ 正常 | Tab切换（系统参数/公司信息） |
| 10 | 预警中心 | /warnings/ | ✅ 正常 | 显示8条未读预警 |
| 11 | 通知消息 | /notifications/ | ✅ 正常 | 全部已读状态 |
| 12 | API文档 | /api/docs/ | ⚠️ 加载慢 | 页面可访问，完整度待查 |
| 13 | 合同管理（旧路径） | /finance/contracts/ | ❌ 404 | 正确路径为 /crm/contracts/ |
| 14 | 用户管理（旧路径） | /core/users/ | ❌ 404 | 正确路径为 /system/users/ |
| 15 | 用户管理（旧路径） | /users/ | ❌ 404 | 正确路径为 /system/users/ |
| 16 | 设备BOM（错误路径） | /equipment/boms/ | ❌ 404 | 正确路径为 /equipment/bom/ |
| 17 | 设备BOM（错误路径） | /projects/equipment-boms/ | ❌ 404 | 正确路径为 /equipment/bom/ |
| 18 | 通知渠道（旧路径） | /notifications/channels/ | ❌ 404 | 正确路径为 /system/notification-channels/ |
| 19 | 通知渠道（旧路径） | /channels/ | ❌ 404 | 正确路径为 /system/notification-channels/ |

### 遗留问题

| 问题 | 路径 | 说明 |
|------|------|------|
| 通知渠道404 | /notifications/channels/ | nav导航栏有入口但返回404，需修复URL |
| 通知渠道404 | /channels/ | 同上，路径错误 |
| 旧路径残留 | /finance/contracts/ | 历史URL，与当前路由不一致 |
| 旧路径残留 | /core/users/ | 历史URL，与当前路由不一致 |

---

## 三、124服务器待同步项

| 项目 | 状态 | 说明 |
|------|------|------|
| standalone分支落后 | master ahead 2 commits | 需合并 6123434 / e172ec0 |
| 迁移冲突 | makemigrations --merge 待执行 | notifications 迁移图谱冲突 |
| gunicorn升级 | 待升级到26.0.0 | 需在124执行pip upgrade |
| 部署包 | 待更新 | v2.0.0-standalone 打包 |

---

## 四、升级注意事项

1. **Django 版本约束**：生产环境已运行 Django 5.2.13，requirements.txt 约束已更新为 <6.0
2. **gunicorn 26.0.0** 需要 systemd restart 才生效（已在43服务器执行）
3. **通知渠道页面**导航链接指向404，需要在代码中找到正确的路由并修复
4. **历史URL残留**不影响功能，但建议在后续清理中做重定向

---

*本文件记录每次升级的完整信息，便于追溯和问题回滚。*
