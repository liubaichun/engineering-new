# 代码审查清单

> 每次提交代码前必须逐项检查。

## 一、通用规范

- [ ] **无硬编码配置**：密码/密钥/API地址等必须通过环境变量或 settings
- [ ] **无调试代码残留**：`print()` / `breakpoint()` / `import pdb` 已清除
- [ ] **无敏感信息**：`password` / `secret` / `token` 等字段已脱敏或使用环境变量
- [ ] **异常处理完整**：关键操作有 `try-except`，异常有日志
- [ ] **日志记录**：关键操作有 `logger.info/error` 记录
- [ ] **类型提示**：函数参数/返回值有类型注解（鼓励，非强制）

## 二、Django 规范

- [ ] **Model 字段规范**：
  - CharField 必须有 max_length
  - DecimalField 必须有 max_digits 和 decimal_places
  - DateField/DateTimeField 区分清楚
  - 外键有 `on_delete` 策略
- [ ] **Migration 规范**：
  - `makemigrations` 后检查生成的 SQL 是否正确
  - 不直接操作已有字段（先加再删，或用数据迁移）
  - 字段删除前确认无引用
- [ ] **QuerySet**：
  - 所有查询考虑 company_id 隔离（多租户模式）
  - 无 N+1 查询问题（使用 `select_related` / `prefetch_related`）
  - 无 `*_id` 裸 ID 查询（使用 FK 对象）
- [ ] **序列化器**：
  - 敏感字段（password、secret）不暴露在 Serializer 中
  - `write_only` / `read_only` 正确设置
  - 验证逻辑在 `validate()` 方法中
- [ ] **视图**：
  - `get_queryset()` 正确过滤 company_id
  - `perform_create/update/destroy` 钩子正确使用
  - 权限检查完整（owner/company/superuser 多层）

## 三、业务逻辑规范

- [ ] **审批流**：提交/批准/驳回后状态正确推进
- [ ] **金额计算**：精度使用 Decimal，不丢失小数
- [ ] **日期时间**：使用 Django timezone，不使用 naive datetime
- [ ] **状态机**：状态流转有前置条件检查

## 四、前端规范

- [ ] **模板继承**：子模板正确继承 base.html
- [ ] **CSRF**：表单有 `{% csrf_token %}`
- [ ] **静态文件**：CSS/JS 引用 `{% static '' %}`
- [ ] **Bootstrap 版本**：与 base.html 一致（v5.x）

## 五、测试覆盖

- [ ] **新增功能有测试**：至少一个测试用例
- [ ] **边界条件**：空值/0/负数/最大值有考虑
- [ ] **权限测试**：不同角色访问权限正确

## 六、安全检查

- [ ] **SQL 注入**：无原始 SQL 拼接，全部用 ORM
- [ ] **XSS**：用户输入内容在页面显示时转义
- [ ] **CSRF**：状态变更操作（POST/PUT/DELETE）有 CSRF token
- [ ] **权限绕过**：非 superuser 不能访问 admin 页面
- [ ] **API 限流**：如有必要，有 rate limit

## 七、提交规范

- [ ] **Commit Message 规范**：
  ```
  <type>(<scope>): <subject>

  type: feat | fix | docs | style | refactor | test | chore
  scope: 模块名，如 finance | crm | approval | notification
  subject: 简短描述，不超过50字
  ```
- [ ] **一个提交一件事**：不混多个修改
- [ ] **代码格式化**：无多余空行/缩进不一致

---

**审查人**：_____________**日期**：_____________**通过**：⬜ 是 / ⬜ 否
