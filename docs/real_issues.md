# 真实问题重排（基于手动验证）

发现自动化扫描有误报：
- ✅ 所有 `get()` 调用已正确包含 try/except（46处扫描结果均为误报）
- ✅ 大部分 `save()` 调用正确使用了 DRF 的 `get_object()` + 框架级异常处理
- ⏸️ CSRF中间件：故意禁用的（内部系统+Token认证），不是Bug

## 真实需要修复的问题（按优先级）

### 🔴 实际发现的P0问题

| # | 问题 | 严重度 | 说明 |
|---|------|--------|------|
| 1 | **关键业务模型CASCADE删除风险** | 🔴 P0 | 删除Employee→连带删WageRecord、SocialRecord。见`finance/models.py` |
| 2 | **`extra()` raw SQL参数化** | 🟠 P1 | 3处在`permissions.py`，参数来自本地常量但应使用ORM |
| 3 | **安全HTTP头缺失** | 🟠 P1 | HSTS/SSL/Secure Cookie/X-Frame |
| 4 | **`print()`替代logging** | 🟠 P1 | `import_social_records.py` |
| 5 | **`.all()` 无公司过滤** | 🟡 P2 | 多租户场景下的数据泄漏风险 |
| 6 | **CASCADE→PROTECT** | 🟡 P2 | 业务数据应使用PROTECT防止误删 |

先修1-4，5-6内部署时一并处理。
