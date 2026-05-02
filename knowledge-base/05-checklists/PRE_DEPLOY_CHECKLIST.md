# 部署前检查清单

> 每次部署前必须逐项检查，通过后方可部署。

## 一、代码质量检查

- [ ] **无未提交的敏感信息**：`.env` / `*.pem` / `*.key` 未进入 git
- [ ] **settings.py DEBUG=False**：生产环境必须关闭调试模式
- [ ] **ALLOWED_HOSTS 已配置**：填写实际域名或 IP
- [ ] **SECRET_KEY 已修改**：非默认值，随机生成
- [ ] **数据库密码已修改**：非默认值
- [ ] **CORS 配置正确**：`ALLOWED_HOSTS` 填写正确

## 二、数据库检查

- [ ] **数据库已备份**：`pg_dump` 备份最新数据
- [ ] **migration 已生成**：`python manage.py makemigrations` 无新增变更
- [ ] **migration 已执行**：`python manage.py migrate` 无报错
- [ ] **静态文件已收集**：`python manage.py collectstatic --noinput`
- [ ] **外键约束正常**：无悬空外键

## 三、服务检查

- [ ] **gunicorn 进程**：重启前 `pkill -9 -f "gunicorn.*engineering"` 完全清理
- [ ] **端口未占用**：`fuser 8001/tcp` 确认端口已释放
- [ ] **systemd service 状态**：`systemctl status engineering-gunicorn`
- [ ] **日志正常**：`logs/error.log` 无 ERROR/CRITICAL
- [ ] **进程数正确**：master + workers 数量正确

## 四、功能验证

- [ ] **登录页面**：`/login/` 可访问
- [ ] **API 文档**：`/api/docs/` 可访问
- [ ] **核心 CRUD**：项目/任务/审批/财务 各操作一次
- [ ] **文件上传**：测试上传一个小文件
- [ ] **健康检查**：`curl http://127.0.0.1:8001/api/core/auth/login/`

## 五、Docker 部署额外检查

- [ ] **.env 文件存在**：`delivery/.env` 已配置
- [ ] **SECRET_KEY 非空**：已修改默认值
- [ ] **docker-compose 可用**：`docker compose version`
- [ ] **healthcheck 通过**：`docker compose ps` 所有服务 Up
- [ ] **nginx profile**：使用 `--profile with_nginx` 时配置正确

## 六、通知系统检查（如已集成）

- [ ] **飞书 App ID/Secret**：已在 .env 或 SystemSetting 配置
- [ ] **企业微信 Corp ID/Secret**：已配置
- [ ] **SMTP 邮件配置**：EMAIL_HOST/EMAIL_PORT/EMAIL_HOST_USER/EMAIL_HOST_PASSWORD
- [ ] **通知渠道测试**：发送测试消息验证各渠道连通

## 七、文档检查

- [ ] **CHANGELOG.md 已更新**：记录本次变更
- [ ] **交付包完整**：`delivery/` 目录无遗漏文件
- [ ] **用户手册同步**：如有重大功能变更需更新文档

## 八、回滚方案

- [ ] **数据库备份可用**：可恢复至部署前状态
- [ ] **旧代码可回退**：git revert 可用
- [ ] **回滚步骤已确认**：如部署失败，知道如何回退

---

**检查人**：_____________**检查日期**：_____________**通过**：⬜ 是 / ⬜ 否
