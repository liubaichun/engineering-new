# Gunicorn OOM 故障防护手册

## 故障现象
- `systemctl restart engineering-gunicorn` 后进程卡在 "deactivating"
- `ps aux` 看到多个 gunicorn master 进程
- journalctl/syslog 出现 "code=killed, status=9/KILL"
- 浏览器访问变慢或超时

## 根因分析
OOM Killer 用 SIGKILL 杀 gunicorn master → KillMode=mixed 只杀 master 不杀 workers → 
workers 变成孤儿继续占用 8001 端口 → systemd Restart=always 重启 → 抢不到端口 → 反复失败

## 预防措施（三道防线）

### 第一道：systemd 服务配置（核心）
`deploy/engineering-gunicorn.service` 已包含以下关键配置：
```ini
ExecStartPre=/bin/sh -c 'pkill -9 gunicorn 2>/dev/null; sleep 1'
KillMode=process
Restart=always
RestartSec=5
```
- `ExecStartPre`: 启动前彻底清理残留进程，防止端口冲突
- `KillMode=process`: 只杀 master，不杀 workers，避免孤儿进程

### 第二道：部署脚本（deploy.sh）
每次部署自动：
- 安装/更新 systemd 服务文件
- 清理残留的 engineering.service / gunicorn.service / engineering-new.service
- 通过 systemd 管理而非 nohup+daemon

### 第三道：监控告警
OOM 发生时需要感知：
```bash
# 检查是否被 OOM Kill
journalctl -k | grep -i "oom\|killed"
# 检查是否有孤儿进程
ps aux | grep gunicorn | grep -v grep | awk '{print $1, $2}' | sort -u
```

## 手动恢复步骤
```bash
# 方案A：systemd 方式（推荐）
systemctl stop engineering-gunicorn
pkill -9 gunicorn
sleep 1
systemctl start engineering-gunicorn

# 方案B：验证端口干净
ss -tlnp | grep 8001  # 应该为空
# 然后
systemctl start engineering-gunicorn
```

## 新服务器部署检查清单
- [ ] systemd 服务文件使用 deploy/engineering-gunicorn.service
- [ ] deploy.sh 第5/6步改用 systemctl 管理
- [ ] 确认 /etc/systemd/system/ 下无残留服务文件
- [ ] 部署后验证：`ps aux | grep gunicorn` 只有一组 master+4 workers
