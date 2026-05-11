# GREEN ERP v2.2.0 — Docker 买断版部署指南

## 系统要求

- Docker 20.10+
- Docker Compose 2.0+
- 服务器最低配置：2核CPU / 4GB内存 / 40GB磁盘

## 快速启动

### 1. 下载代码

```bash
git clone -b v2.2.0 https://github.com/liubaichun/engineering-new.git
cd engineering-new
```

### 2. 配置环境

```bash
cp .env.standalone.template .env
# 编辑 .env，修改以下必填项：
#   SECRET_KEY        — 填入随机密钥（至少50字符）
#   ALLOWED_HOSTS     — 填入服务器IP或域名
#   PG_PASSWORD       — 设置PostgreSQL密码
#   REDIS_PASSWORD    — 设置Redis密码
```

### 3. 启动服务

```bash
docker-compose -f docker-compose.standalone.yml up -d
```

### 4. 初始化超级管理员

```bash
docker exec -it green_web python manage.py createsuperuser
# 或直接访问 http://服务器IP:8001/admin/ 注册第一个管理员
```

### 5. 验证

```bash
curl -sf http://localhost/api/core/health/ || echo "Health check failed"
docker-compose -f docker-compose.standalone.yml ps
```

---

## 目录结构

```
engineering-new/
├── docker-compose.standalone.yml   # 容器编排（买断版）
├── Dockerfile.standalone            # Web应用镜像构建文件
├── entrypoint.sh                    # 容器启动脚本
├── nginx.standalone.conf            # Nginx 生产配置
├── .env.standalone.template         # 环境变量模板
├── requirements.txt                 # Python 依赖
└── apps/                            # 业务应用代码
```

---

## 常用运维命令

### 查看日志

```bash
# 所有服务日志
docker-compose -f docker-compose.standalone.yml logs -f

# 只看 Web 服务
docker-compose -f docker-compose.standalone.yml logs -f web

# 只看 Nginx
docker-compose -f docker-compose.standalone.yml logs -f nginx
```

### 重启服务

```bash
docker-compose -f docker-compose.standalone.yml restart web
```

### 升级版本

```bash
git pull origin master
docker-compose -f docker-compose.standalone.yml build web
docker-compose -f docker-compose.standalone.yml up -d
```

### 数据库备份

```bash
# 导出
docker exec green_db pg_dump -U engineering engineering > backup_$(date +%Y%m%d).sql

# 导入
cat backup_20260511.sql | docker exec -i green_db psql -U engineering engineering
```

### 进入容器调试

```bash
docker exec -it green_web /bin/bash
docker exec -it green_db psql -U engineering -d engineering
```

---

## 端口说明

| 端口 | 服务 | 说明 |
|------|------|------|
| 80   | Nginx | HTTP入口 |
| 443  | Nginx | HTTPS入口（需自行配置SSL证书） |
| 8001 | Gunicorn | Django应用（仅本地访问） |
| 5432 | PostgreSQL | 数据库（容器内部） |
| 6379 | Redis | 缓存（容器内部） |

---

## 数据持久化

以下数据通过 Docker volume 持久化，不会因容器重建而丢失：

- `postgres_data` — PostgreSQL 数据文件
- `redis_data` — Redis 持久化文件
- `static_files` — Django 收集的静态文件（CSS/JS等）
- `media_files` — 用户上传的媒体文件

---

## 首次部署检查清单

- [ ] `.env` 文件已创建且 `SECRET_KEY` 已修改
- [ ] `ALLOWED_HOSTS` 包含服务器公网IP或域名
- [ ] `PG_PASSWORD` 和 `REDIS_PASSWORD` 已设置强密码
- [ ] 防火墙/安全组已开放 80 和 443 端口
- [ ] 超级管理员账号已创建
- [ ] 登录 http://服务器IP/ 验证页面可访问
- [ ] Docker volume 数据已确认持久化

---

## HTTPS 配置（可选）

使用 Let's Encrypt 免费证书：

```bash
# 安装 certbot
apt install certbot python3-certbot-nginx

# 申请证书（需域名解析已生效）
certbot --nginx -d your-domain.com

# certbot 自动修改 nginx.standalone.conf 配置证书路径
```
