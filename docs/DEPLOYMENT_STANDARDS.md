# 企业信息化管理系统 GREEN — 部署标准规范

> 版本：2026-05-02
> 基于124服务器部署踩坑经验总结

---

## 一、核心原则：1:1还原

**任何服务器通过 `git clone/pull + migrate` 必须能完整还原。**

违反这个原则，说明部署规范或代码有问题，必须修复规范，而不是绕过问题。

---

## 二、新服务器首次部署标准流程

```bash
# 1. 环境准备
apt update && apt install -y python3 python3-pip python3-venv git nginx postgresql
pip install virtualenv
mkdir -p /root/engineering-new && cd /root/engineering-new

# 2. 代码克隆
git clone https://github.com/liubaichun/engineering-new.git .
git checkout standalone   # 买断版用standalone分支

# 3. 依赖安装
pip install -r requirements.txt

# 4. 环境配置
cp .env.standalone.template .env
# 编辑.env：DATABASE_URL, SECRET_KEY, ALLOWED_HOSTS

# 5. 数据库创建
sudo -u postgres psql -c "CREATE DATABASE engineering_new;"
sudo -u postgres psql -c "CREATE USER engineering_user WITH PASSWORD 'your_password';"
sudo -u postgres psql -c "ALTER ROLE engineering_user SET client_encoding TO 'utf8';"
sudo -u postgres psql -c "ALTER ROLE engineering_user SET timezone TO 'Asia/Shanghai';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE engineering_new TO engineering_user;"

# 6. 数据库迁移（关键！）
# 先fake initial，让Django跳过创建已有表
python manage.py migrate --fake-initial

# 7. 创建超级用户
python manage.py createsuperuser

# 8. Nginx配置
sudo cp deploy/nginxstandalone.conf /etc/nginx/sites-available/engineering
sudo ln -s /etc/nginx/sites-available/engineering /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# 9. Gunicorn启动
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2 --daemon

# 10. 冒烟测试
curl -s http://localhost:8001/api/core/users/ | head -c 200
curl -s http://localhost:8001/api/crm/clients/ | head -c 200
curl -s http://localhost:8001/api/tasks/projects/ | head -c 200
```

---

## 三、已有服务器代码更新流程

```bash
# ★ 必须先检查网络和依赖链
git fetch origin

# 当前分支状态
git status
git log --oneline -3

# ★ 第一步：showmigrations --plan
python manage.py showmigrations --plan
# 输出示例：
# [ ] approvals.0001_initial
# [ ] approvals.0001_add_approval_flow
# [ ] approvals.0002_add_template
# ...
# 如果有循环依赖标记：[!] 或红色，STOP不要继续

# ★ 第二步：check --deploy
python manage.py check --deploy
# 必须输出：System check identified no issues (0 silenced).
# 如果有WARNINGS，评估是否阻塞

# ★ 第三步：migrate
python manage.py migrate
# 如果报错，立即停止，分析依赖链

# ★ 第四步：重启gunicorn
systemctl restart engineering-gunicorn
# 或
pkill -HUP gunicorn

# ★ 第五步：冒烟测试
for path in /api/core/users/ /api/crm/clients/ /api/crm/contracts/ /api/tasks/projects/ /api/finance/companies/; do
  code=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8001${path})
  echo "$code $path"
done
```

---

## 四、Migration依赖链分析流程

**当 migrate 报错 `Migrations are in an inconsistent state` 时：**

### 4.1 分析工具
```bash
# 查看迁移执行计划（不实际执行）
python manage.py showmigrations --plan

# 查看DB实际记录
psql -U engineering_user -d engineering_new -c "
SELECT id, app, name, applied
FROM django_migrations
WHERE app='notifications'
ORDER BY id;"

# 查看某个migration文件的依赖声明
grep -A5 "dependencies" apps/notifications/migrations/0003*.py
```

### 4.2 不一致类型及处理

**类型A：DB缺少某个migration，但代码依赖它**
- 现象：代码有0003.py，DB里只有0001
- 原因：之前用--fake跳过了0002
- 处理：
  ```python
  # 方案1（推荐）：fake掉中间状态，然后正常执行
  python manage.py migrate notifications 0002_add_notification_channel --fake
  python manage.py migrate notifications 0003_add_notify_binding_fields

  # 方案2：直接插入applied记录
  # 在Django shell中执行SQL
  ```

**类型B：DB有某个migration，但代码没有**
- 现象：DB有0002，但代码里0002.py不存在
- 原因：代码回退了，但DB没有回退
- 处理：`python manage.py migrate notifications 0002 --fake`（fake掉）

**类型C：migration存在但dependencies声明错误**
- 现象：0003声明依赖0002_initial，但DB里0002的name是`0002_add_notification_channel`
- 处理：修改代码中0003.py的dependencies为正确的迁移名，然后commit+push
- 示例（124服务器）：
  ```bash
  # sed远程修改
  ssh root@124.222.227.28 "sed -i 's/0002_initial/0002_add_notification_channel/g' /root/engineering-new/apps/notifications/migrations/0003*.py"
  ```

### 4.3 Reconcile脚本模板
```python
# /tmp/reconcile_migrations.py
import os, sys, datetime as dt
sys.path.insert(0, '/root/engineering-new')
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings_pg'
import django; django.setup()
from django.db import connection

app = 'notifications'  # 修改为实际app
to_insert = [
    ('0003_add_notify_binding_fields', ...),
    ('0004_alter_notifybinding_options_and_more', ...),
]

now = dt.datetime.now(dt.timezone.utc)
with connection.cursor() as c:
    # 删除乱序记录
    names = tuple(n for n,_ in to_insert)
    c.execute(f"DELETE FROM django_migrations WHERE app='{app}' AND name IN {names}")
    # 插入正确记录
    for name, deps in to_insert:
        c.execute(
            f"INSERT INTO django_migrations (app, name, applied) VALUES ('{app}', %s, %s)",
            [name, now]
        )
    print('Reconciled:', app)
```

---

## 五、代码同步规范（43开发机 → GitHub → 124服务器）

### 5.1 开发流程
```
43开发机: 代码修改 → makemigrations → commit → push GitHub
124服务器: git pull → migrate → restart
```

### 5.2 Multi-tenant (master) vs Standalone 分支规范
- **master**: 多租户版，company_id隔离，UserCompanyRole关联
- **standalone**: 独立版，无租户隔离，Channels保留
- 新功能必须**同时**同步到两个分支
  ```bash
  # 在43开发机
  git checkout master
  # 修改代码
  git commit -m "fix: ..."
  git push origin master

  # Cherry-pick到standalone
  git checkout standalone
  git cherry-pick <master-commit-hash>
  git push origin standalone
  ```

### 5.3 新增Model必须立即makemigrations
- 禁止在本地做完model改动但不执行makemigrations
- 禁止commit时只有代码没有新的migration文件
- 如果忘记makemigrations就push了，回退代码，补上makemigrations，再重新push

---

## 六、Gunicorn管理规范

```bash
# 查看状态
systemctl status engineering-gunicorn

# 重启（代码修改后必须）
systemctl restart engineering-gunicorn

# 查看日志
journalctl -u engineering-gunicorn -n 50 --no-pager

# 如果systemd不可用，手动管理
pkill gunicorn
sleep 2
cd /root/engineering-new
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2 --daemon
ps aux | grep gunicorn
```

---

## 七、124服务器特殊说明

### 7.1 当前状态（2026-05-02）
- 分支：standalone
- DB：PostgreSQL，settings_pg.py
- 已知问题：
  - equipment/material表不存在（从未执行migrate）
  - notifications迁移历史与代码不一致
  - GitHub访问不稳定（需要重试）

### 7.2 124修复步骤
```bash
# 步骤1: 执行迁移修复脚本
ssh root@124.222.227.28 "/usr/bin/python3 /tmp/fix_notify_final.py"

# 步骤2: 验证migrate
ssh root@124.222.227.28 "cd /root/engineering-new && DJANGO_SETTINGS_MODULE=config.settings_pg /usr/bin/python3 manage.py migrate"

# 步骤3: 重启
ssh root@124.222.227.28 "systemctl restart engineering-gunicorn"

# 步骤4: 冒烟测试
for path in /api/core/users/ /api/crm/clients/ /api/crm/contracts/ /api/crm/sources/ /api/tasks/projects/ /api/finance/companies/ /api/approvals/flows/; do
  ssh root@124.222.227.28 "curl -s -o /dev/null -w '%{http_code} ${path}\n' http://localhost:8001${path}"
done

# 步骤5: 验证equipment（如果需要）
ssh root@124.222.227.28 "cd /root/engineering-new && DJANGO_SETTINGS_MODULE=config.settings_pg /usr/bin/python3 manage.py migrate equipment --fake 0001_initial"
ssh root@124.222.227.28 "cd /root/engineering-new && DJANGO_SETTINGS_MODULE=config.settings_pg /usr/bin/python3 manage.py migrate equipment"
```

---

## 八、禁止事项（血泪教训）

| 禁止行为 | 后果 |
|---------|------|
| `migrate --fake app zero` | 迁移图出现"洞"，永远无法正确应用后续迁移 |
| 在生产环境执行 `makemigrations` | 可能生成不一致的迁移，与开发机冲突 |
| cherry-pick只pick代码，不包含migrations | 新表在目标服务器不存在，500错误 |
| 跳过 `showmigrations --plan` 直接migrate | 遇到循环依赖时破坏迁移历史 |
| 多租户代码（company_id隔离）部署到standalone | 500错误（company_id列不存在） |
| `--fake-initial` 用于已有表结构的DB | 会清空已有数据（如果Django误判） |

---

## 九、部署checklist（每次必须执行）

```markdown
## 部署前检查
- [ ] git pull 成功，网络通畅
- [ ] showmigrations --plan 无循环依赖
- [ ] check --deploy 通过
- [ ] 有新migration吗？如果有，确认依赖链正确

## 部署执行
- [ ] migrate 无报错
- [ ] 重启gunicorn成功
- [ ] systemctl status gunicorn 正常运行

## 部署后验证（必须全部200）
- [ ] /api/core/users/ → 200
- [ ] /api/crm/clients/ → 200
- [ ] /api/crm/contracts/ → 200
- [ ] /api/crm/sources/ → 200
- [ ] /api/tasks/projects/ → 200
- [ ] /api/finance/companies/ → 200
- [ ] /api/finance/wages/ → 200
- [ ] /api/approvals/flows/ → 200
- [ ] /api/files/company-files/ → 200
- [ ] /api/notifications/channels/ → 200
```
