# 多租户SaaS平台设计规范 v1.0

> 文档日期：2026-05-29
> 状态：初稿
> 适用对象：GREEN ERP SaaS平台架构设计与开发

---

## 1. 设计理念

### 1.1 平台化思维

GREEN ERP 将从"为几个公司服务的单租户系统"演进为"可承载数百个企业客户的SaaS平台"。这不是简单的功能叠加，而是**架构范式的转换**：

| 维度 | 单租户思维 | 平台化思维 |
|------|-----------|-----------|
| 用户 | 公司内的员工 | 平台上的租户管理员+租户用户 |
| 数据 | 所有数据属于一个逻辑实体 | 数据按租户严格隔离 |
| 运营 | 运维人员直接操作 | 平台管理端+租户自助 |
| 扩容 | 堆硬件 | 水平扩缩+资源池化 |
| 发布 | 全量发布 | 灰度+按租户分批 |
| 计费 | 无 | 套餐+用量计费 |

### 1.2 五大核心原则

1. **隔离性**——租户数据互不可见，性能互不影响
2. **弹性**——从10个租户到10万个租户，架构无需重写
3. **可维护性**——平台运维不因租户数量增加而线性增长
4. **安全性**——防跨租户攻击是最高优先级
5. **用户体验**——每个租户感觉自己是"独立用户"

### 1.3 我们的方案：Hybrid混合隔离

业界三种主流方案对比后，我们选择**混合策略**：

| 方案 | 优点 | 缺点 | 适用场景 |
|------|------|------|---------|
| 共享DB+字段隔离 | 成本低、维护简单 | 大租户影响小租户、备份粒度粗 | Free/试用租户 |
| 共享DB+Schema隔离 | 隔离性好、数据独立备份 | 连接数管理复杂 | Pro/标准租户 |
| 独立数据库 | 完全隔离、性能独享 | 成本高、维护复杂 | Enterprise/关键租户 |

**我们的方案：**

```
租户注册 → 等级评估
     ↓
┌─────────────────────────────────────────┐
│       租户等级×数据隔离策略                │
├──────────┬──────────┬───────────────────┤
│ Free     │ Pro      │ Enterprise        │
│ 共享DB   │ 独享     │ 独享DB+独享资源    │
│ +tenant_id│ Schema   │ +只读副本         │
├──────────┼──────────┼───────────────────┤
│ 支持     │ 支持     │ 独立实例           │
│ 升级迁移 │ 升级迁移  │ SLA 99.99%        │
└──────────┴──────────┴───────────────────┘
```

**关键设计：租户等级是可迁移的。** 一个Free租户随着数据量增长，可以在线迁移到独立Schema，再到独立数据库，业务不中断。

---

## 2. 租户隔离架构

### 2.1 分层隔离模型

```
┌─────────────────────────────────────────────────────────┐
│                    平台层（Platform）                      │
│  ┌──────────────────────────────────────────────────┐   │
│  │              路由层（Router）                      │   │
│  │  租户路由表 → 解析请求 → 分配目标的租户              │   │
│  └──────────────────────────────────────────────────┘   │
│         ↓                    ↓                    ↓       │
│  ┌──────────┐       ┌──────────┐       ┌──────────┐   │
│  │  DB Pool 1│       │  DB Pool 2│       │  DB Pool N│   │
│  │ (共享)    │       │ (Schema)  │       │ (独立DB)  │   │
│  │ Free租户  │       │ Pro租户   │       │ Enterprise│   │
│  └──────────┘       └──────────┘       └──────────┘   │
└─────────────────────────────────────────────────────────┘
```

### 2.2 共享DB模式（Free/试用租户）

采用 **tenant_id 字段隔离**，所有表都必须包含 tenant_id：

```python
class TenantAwareMixin(models.Model):
    """多租户混入模型——所有租户表必须继承"""
    tenant_id = models.IntegerField(
        verbose_name='租户ID',
        db_index=True,
        null=False,
        default=0,
        help_text='平台分配的租户ID，0=平台公共数据'
    )

    class Meta:
        abstract = True
```

**Django中间件自动过滤：**

```python
class TenantMiddleware:
    """多租户中间件——自动为所有查询注入 tenant_id 过滤"""

    def resolve_tenant(self, request):
        """从请求中解析租户ID（优先级：JWT → 子域名 → Session → Header）"""
        # 1. 优先从JWT中取（不暴露在payload，从签名中提取）
        # 2. 其次从子域名查路由表
        # 3. 最后从请求 Header: X-Tenant-Id

    def process_queryset(self, queryset, request):
        """自动注入租户过滤"""
        tenant_id = self.resolve_tenant(request)
        model = queryset.model
        if hasattr(model, 'tenant_id'):
            return queryset.filter(tenant_id=tenant_id)
        return queryset
```

### 2.3 独立Schema模式（Pro租户）

```
PostgreSQL 实例
├── public Schema（路由表、平台数据）
├── tenant_2 Schema（恒鑫兴·Pro）
│   └── 所有表都在此 Schema 下
├── tenant_3 Schema（百川·Pro）
└── tenant_4 Schema（绿聚能·Pro）
```

优势：**同一个DB实例，不同的Schema**，天然隔离。备份时 `pg_dump -n tenant_2` 即可导出单个租户。

### 2.4 独立数据库模式（Enterprise租户）

```yaml
# tenant_db_routing.yaml
tenants:
  enterprise_001:
    db: green_erp_enterprise_001
    host: db-ep-001.internal
    pool_size: 20
    replica: db-ep-001-ro.internal  # 只读副本
  enterprise_002:
    db: green_erp_enterprise_002
    host: db-ep-002.internal
    pool_size: 30
    replica: db-ep-002-ro.internal
```

### 2.5 数据迁移路径

```
Free(共享) ──→ Pro(Schema) ──→ Enterprise(独立DB)
     │              │                  │
     │ 不停机导出    │ 在线Schema迁移    │ DB复制+切换
     ↓              ↓                  ↓
  新建DB实例      新建Schema           目标DB就绪
     │              │                  │
     └──── 所有模式支持回滚 ────────────┘
```

迁移工具核心流程：

```
1. 目标端创建空Schema/DB
2. 源端加读锁（防止迁移中数据变更）
3. 流式复制数据（分批迁移，每批1000条）
4. 校验数据完整性（COUNT、SUM校验）
5. 更新路由表（租户ID → 新目标）
6. 释放读锁
7. 源端数据保留30天（回滚窗口）
```

---

## 3. 租户路由与域名系统

### 3.1 通配符域名方案

```
*.green-erp.com → Nginx → 应用路由 → 路由表
     ↓
hxx.green-erp.com      → 恒鑫兴租户
bc.green-erp.com       → 百川租户
ljn.green-erp.com      → 绿聚能租户
open.green-erp.com     → 开放平台/登录页
```

**Nginx配置：**

```nginx
server {
    listen 443 ssl;
    server_name *.green-erp.com;
    ssl_certificate /etc/letsencrypt/live/green-erp.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/green-erp.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Tenant-Host $host;  # 传递子域名
    }
}
```

### 3.2 路由表设计

```sql
CREATE TABLE platform_tenant_route (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL UNIQUE,
    tenant_code VARCHAR(50) NOT NULL UNIQUE,     -- 如 'hxx'
    domain VARCHAR(255),                           -- 子域名 'hxx.green-erp.com'
    custom_domain VARCHAR(255),                    -- 自定义域名 'erp.hengxinxing.com'
    db_mode VARCHAR(20) DEFAULT 'shared',          -- shared | schema | standalone
    db_config JSONB,                               -- {host, port, dbname, schema, user, password}
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_tenant_route_domain ON platform_tenant_route(domain);
CREATE INDEX idx_tenant_route_custom ON platform_tenant_route(custom_domain);
```

### 3.3 路由缓存策略

```
请求到达 → 查Redis缓存(tenant_routes:{域名})
     ↓ 缓存命中 → 返回租户信息
     ↓ 缓存未命中 → 查数据库路由表 → 写入Redis(TTL=3600s)
     ↓ 路由不存在 → 返回404/跳转注册页
```

Redis数据结构：

```python
# 缓存键: tenant_routes:{domain}
# 缓存值: JSON
{
    "tenant_id": 2,
    "tenant_code": "hxx",
    "db_mode": "schema",
    "db_name": "green_erp",
    "schema": "tenant_2",
    "company_name": "恒鑫兴",
    "logo": "/static/tenants/hxx/logo.png"
}
```

### 3.4 自定义域名支持

```
企业客户可绑定自己的域名：
erp.hengxinxing.com → CNAME → green-erp.com
                     ↓
Nginx通配符不匹配 → 查路由表custom_domain字段
                     ↓
匹配到租户 → 正常路由
```

验证流程：
1. 租户在平台管理端输入自定义域名
2. 系统生成DNS验证Token（TXT记录）
3. 租户在自己的DNS管理添加TXT记录
4. 系统验证通过后，更新路由表
5. 自动申请Let's Encrypt SSL证书
6. 域名生效

### 3.5 SSL证书管理

```bash
# 通配符证书（平台主域名）
certbot certonly --dns-cloudflare -d *.green-erp.com

# 自定义域名证书（自动申请）
certbot certonly --webroot -w /var/www/html \\
    -d erp.hengxinxing.com --non-interactive

# 自动续期（所有证书）
certbot renew --post-hook "systemctl reload nginx"
```

---

## 4. 身份认证与授权体系

### 4.1 对比：我们 vs 传统方案

| 特性 | 恒鑫兴方案 | 我们的方案 | 优势 |
|------|-----------|-----------|------|
| Tenant ID | 明文在JWT Payload | 服务端Session绑定+JWT签名中加密 | 防篡改 |
| SSO | 不支持 | 支持OAuth2/SAML/CAS | 企业客户需要 |
| API鉴权 | Cookie+JWT | JWT + API Token(机器对机器) | 灵活 |
| 跨租户 | 不支持 | 显式授权(同一个用户在多个租户间切换) | 集团客户 |

### 4.2 登录认证流程

```
用户访问 hxx.green-erp.com
    ↓
DNS → Nginx → 应用
    ↓
路由中间件: 根据域名查路由表 → tenant_id=2
    ↓
返回登录页（显示租户的Logo和名称）
    ↓
用户输入账号密码
    ↓ ──────── 可选：OAuth2 SSO ────────→
    ↓                                    如果企业配置了SSO
服务端校验密码                            跳转到企业IdP认证
    ↓ ←─────────────────────────────────
校验用户是否属于tenant_id=2
    ↓
生成JWT Token（Session ID，不含tenant_id）
    ↓
服务端Session存储: {session_id → {user_id, tenant_id, expires_at}}
    ↓
返回Token → 前端存储
    ↓
后续所有请求携带Token
    ↓
中间件: 从Session中提取tenant_id → 校验是否匹配当前域名
    ↓
添加到请求上下文 → 数据库查询自动注入tenant_id
```

### 4.3 JWT与Session双重校验

```python
class AuthMiddleware:
    """认证中间件——JWT + 服务端Session双重校验"""

    TOKEN_HEADER = 'Authorization'
    SESSION_PREFIX = 'user_session:'

    def authenticate(self, request):
        # Step 1: 从请求头提取JWT
        token = request.headers.get(self.TOKEN_HEADER, '').replace('Bearer ', '')

        # Step 2: 验证JWT签名
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            session_id = payload['sid']  # Session ID
        except:
            raise AuthenticationFailed('Token无效')

        # Step 3: 查服务端Session
        session_data = redis.get(f'{SESSION_PREFIX}{session_id}')
        if not session_data:
            raise AuthenticationFailed('Session过期')

        # Step 4: 校验tenant_id与请求域名匹配
        tenant_id_from_session = session_data['tenant_id']
        tenant_id_from_route = resolve_tenant_from_domain(request)

        if tenant_id_from_session != tenant_id_from_route:
            raise AuthenticationFailed('租户不匹配')

        # Step 5: 返回认证用户（含租户信息）
        return AuthUser(
            user_id=session_data['user_id'],
            tenant_id=tenant_id_from_session,
            roles=session_data['roles']
        )
```

### 4.4 多租户用户管理

**全局用户ID + 租户绑定：**

```python
# 用户注册在平台层面（全局唯一）
class PlatformUser(models.Model):
    """平台用户（全局唯一）"""
    email = models.EmailField(unique=True)
    password_hash = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'platform_user'

# 租户内用户（关联平台用户 + 租户角色）
class TenantUser(models.Model):
    """租户用户（关联到平台用户）"""
    platform_user = models.ForeignKey(PlatformUser, on_delete=models.CASCADE)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    display_name = models.CharField(max_length=100)  # 在租户内的显示名
    role = models.CharField(max_length=50, choices=ROLE_CHOICES)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'tenant_user'
        unique_together = [('platform_user', 'tenant')]
```

**跨租户切换（集团用户）：**

```
用户在同属的多个租户间切换：
1. 登录时获取用户所属的所有租户列表
2. 前端显示"切换租户"下拉菜单
3. 切换后重新签发Session（新的tenant_id）
4. 保留原Session一段时间（可快速切回）
```

### 4.5 API Token（机器对机器）

```python
class ApiToken(models.Model):
    """API访问令牌——用于第三方集成"""
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    token = models.CharField(max_length=64, unique=True, editable=False)
    name = models.CharField(max_length=100)  # 如 "工行直连"
    permissions = models.JSONField(default=list)  # 允许的API范围
    expires_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'platform_api_token'
```

---

## 5. 数据隔离层（Django中间件）

### 5.1 TenantAwareModel基类

```python
class TenantAwareModel(models.Model):
    """所有多租户数据模型的基类"""
    tenant = models.ForeignKey(
        'platform.Tenant',
        on_delete=models.CASCADE,
        db_index=True,
        verbose_name='所属租户'
    )

    class Meta:
        abstract = True

    @classmethod
    def get_tenant_queryset(cls, tenant_id):
        """获取特定租户的查询集"""
        return cls.objects.filter(tenant_id=tenant_id)

class TenantAwareManager(models.Manager):
    """自动过滤租户的管理器"""

    def get_queryset(self):
        qs = super().get_queryset()
        tenant_id = get_current_tenant_id()
        if tenant_id:
            return qs.filter(tenant_id=tenant_id)
        return qs
```

### 5.2 中间件自动注入

```python
class TenantIsolationMiddleware:
    """租户隔离中间件"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 解析当前租户
        tenant = self.resolve_tenant(request)
        if tenant:
            request.tenant = tenant
            request.tenant_id = tenant.id
            # 设置线程局部变量（供TenantAwareManager使用）
            set_current_tenant_id(tenant.id)
        else:
            request.tenant = None
            request.tenant_id = None

        response = self.get_response(request)

        # 清理线程局部变量
        clear_current_tenant_id()
        return response
```

### 5.3 跨租户查询（平台审计用）

```python
# 显式声明跨租户查询
with platform_context():
    all_tenants_data = SocialRecord.objects.all()

# 或使用 .bypass_tenant() 方法
stats = SocialRecord.objects.bypass_tenant().filter(
    year_month='2026-05'
).values('tenant_id').annotate(
    total=Sum('total')
)
```

### 5.4 租户级数据备份

```bash
#!/bin/bash
# backup_tenant.sh — 按租户备份数据

TENANT_ID=$1
TENANT_CODE=$2
BACKUP_DIR="/data/backups/tenants/$TENANT_CODE"
DATE=$(date +%Y%m%d)

mkdir -p "$BACKUP_DIR"

case $DB_MODE in
    "shared")
        pg_dump -h $DB_HOST -U $DB_USER -d green_erp \
            --data-only \
            --schema=public \
            --table="*" \
            --where="tenant_id=$TENANT_ID" \
            -f "$BACKUP_DIR/tenant_${TENANT_ID}_${DATE}.sql"
        ;;
    "schema")
        pg_dump -h $DB_HOST -U $DB_USER -d green_erp \
            -n "tenant_${TENANT_ID}" \
            -f "$BACKUP_DIR/tenant_${TENANT_ID}_${DATE}.sql"
        ;;
    "standalone")
        pg_dump -h $STANDALONE_HOST -U $DB_USER -d green_erp \
            -f "$BACKUP_DIR/tenant_${TENANT_ID}_${DATE}.sql"
        ;;
esac

# 加密压缩
gzip "$BACKUP_DIR/tenant_${TENANT_ID}_${DATE}.sql"
openssl enc -aes-256-cbc -salt \
    -in "$BACKUP_DIR/tenant_${TENANT_ID}_${DATE}.sql.gz" \
    -out "$BACKUP_DIR/tenant_${TENANT_ID}_${DATE}.sql.gz.enc"
```

---

## 6. 平台管理端（超管后台）

> **这是恒鑫兴系统完全没有的模块**——他们只有一个租户内管理，没有平台级管理界面。

### 6.1 功能界面设计

```
平台管理端 (admin.green-erp.com)
│
├── 📊 控制台
│   ├── 平台总览（租户数/用户数/存储量/API调用量）
│   ├── 活跃租户排行
│   ├── 资源使用趋势图
│   └── 系统健康状态（数据库/缓存/队列）
│
├── 🏢 租户管理
│   ├── 租户列表（搜索/筛选/排序）
│   ├── 租户详情（基本信息/套餐/用量/操作日志）
│   ├── 创建租户（手动创建）
│   ├── 租户停用/启用
│   ├── 租户套餐变更
│   └── 租户数据清理（30天保留期）
│
├── 📦 套餐管理
│   ├── 套餐定义（Free/Pro/Enterprise）
│   ├── 功能权限（按模块开启/关闭）
│   ├── 用量配额（存储/用户数/API次数）
│   └── 价格管理
│
├── 🔍 监控
│   ├── 实时监控（CPU/内存/DB连接数）
│   ├── 慢查询分析
│   ├── API错误率
│   └── 警报规则配置
│
├── 📝 审计日志
│   ├── 所有租户的操作记录
│   ├── 跨租户查询记录
│   ├── 敏感操作记录
│   └── 导出功能
│
└── ⚙️ 平台设置
    ├── 系统全局参数
    ├── 邮件服务配置
    ├── 支付网关配置
    └── 通知模板
```

### 6.2 租户创建流程

```
管理员点击"创建租户"
    ↓
填写租户信息：公司名、联系人、邮箱、套餐
    ↓
系统自动：
  1. 生成 tenant_id
  2. 生成租户代码（如 bch）
  3. 创建数据库/Schema（根据套餐等级）
  4. 初始化默认角色（管理员/财务/普通员工）
  5. 创建默认管理员账户
  6. 初始化系统参数（Logo/名称/编码规则）
  7. 创建默认菜单配置
    ↓
返回租户信息：管理地址、管理员账号密码
    ↓
（可选：发送邮件通知）
```

### 6.3 租户用量监控

```python
# 每个租户的关键指标
class TenantMetrics(models.Model):
    """租户用量指标（实时更新）"""
    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE)
    storage_mb = models.IntegerField(default=0)      # 数据存储(MB)
    file_storage_mb = models.IntegerField(default=0) # 文件存储(MB)
    user_count = models.IntegerField(default=0)       # 用户数
    api_calls_24h = models.IntegerField(default=0)    # 24小时API调用
    last_active_at = models.DateTimeField(null=True)  # 最后活跃时间
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

### 6.4 平台安全管控

| 管控项 | 实现方式 |
|--------|---------|
| 平台管理员MFA | 强制Google Authenticator/TOTP |
| 操作审计 | 所有平台操作写入 audit_log 表 |
| IP白名单 | 平台管理端仅允许指定IP访问 |
| 会话超时 | 15分钟无操作自动登出 |
| 审批流程 | 高危操作（删除租户/数据导出）需二次审批 |

---

## 7. 租户自助注册与初始化

### 7.1 注册流程

```
用户访问 green-erp.com
    ↓
选择"注册试用"
    ↓
填写注册信息：
  · 公司名称
  · 管理员邮箱
  · 管理员手机
  · 密码
  · 验证码
    ↓
邮箱验证（发送验证链接）
    ↓
验证通过 → 自动创建租户
    ↓ ────────────────────────────────┐
    ↓                                  │
并行执行：                              │
  ├─ 创建租户记录                     │
  ├─ 创建数据库隔离层                  │
  ├─ 初始化默认数据                    监控进度
  │   ├─ 角色：管理员/财务/普通员工     │
  │   ├─ 管理员账户                     │
  │   ├─ 系统参数                       ← 全部完成
  │   ├─ 菜单配置                      │
  │   └─ 编码规则（默认）              │
  └─ 发送欢迎邮件                      │
    ↓ ←────────────────────────────────┘
跳转到租户管理页
显示"14天免费试用"提示
```

### 7.2 初始化数据清单

每个新租户自动创建：

```json
{
  "roles": [
    {"code": "admin", "name": "管理员", "permissions": "all"},
    {"code": "finance", "name": "财务", "permissions": ["finance:*", "crm:read"]},
    {"code": "staff", "name": "普通员工", "permissions": ["tasks:*", "crm:read"]}
  ],
  "default_admin": {
    "username": "admin",
    "display_name": "系统管理员",
    "role": "admin"
  },
  "system_params": {
    "logo": "/static/tenants/default/logo.png",
    "company_name": "（注册时输入的公司名）",
    "code_rules": {
      "employee": "{T:YG}{D:YYYYMM}{SEQ:4}",
      "client": "{T:KH}{D:YYYYMM}{SEQ:4}",
      "contract": "{T:HT}{D:YYYY}{SEQ:4}",
      "project": "{T:XM}{D:YYYY}{SEQ:4}",
      "material": "{T:WL}{SEQ:5}"
    },
    "decimal_places": 2,
    "date_format": "YYYY-MM-DD",
    "timezone": "Asia/Shanghai"
  },
  "default_modules": [
    "dashboard", "crm", "finance", "tasks", "approvals", "system"
  ]
}
```

### 7.3 试用期管理

```
注册 → 14天免费试用
          │
    第10天：发送"即将到期"邮件
          │
    第14天：租户到期
          │
    ├─ 用户已付费 → 正常使用
    └─ 用户未付费 → 进入"冻结"状态
          │
    冻结状态（30天保留期）：
    · 租户不可登录
    · 数据保留，不可写入
    · 管理员可登录查看冻结提示
          │
    ├─ 30天内付费 → 解冻，数据完整
    └─ 30天后未付费 → 数据归档删除
          │
    数据删除前14天/7天/1天 发送通知
```

---

## 8. 计费与订阅体系

> 计费是SaaS平台的命脉。没有清晰的计费体系，就无法规模化获客。

### 8.1 定价模型

采用 **套餐月费 + 用量超额** 混合模式：

```yaml
套餐定义:
  Free:
    月费: ¥0
    用户数上限: 5
    存储空间: 100MB
    API次数: 1000/月
    功能: 核心平台（不含行业包）

  Pro:
    月费: ¥299/月
    用户数上限: 20
    存储空间: 1GB
    API次数: 50000/月
    功能: 核心平台 + 1个行业包

  Enterprise:
    月费: ¥999/月
    用户数上限: 100
    存储空间: 10GB
    API次数: 不限
    功能: 全部功能 + 独立Schema + 自定义域名

超额计费（超出配额部分）:
  额外用户: ¥20/用户/月
  额外存储: ¥10/GB/月
  额外API: ¥0.01/千次
```

### 8.2 计费周期与按比例计算

```python
class Subscription(models.Model):
    """租户订阅"""
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    plan = models.CharField('套餐', max_length=20, choices=[
        ('free', 'Free'), ('pro', 'Pro'), ('enterprise', 'Enterprise')
    ])
    status = models.CharField('状态', max_length=20, choices=[
        ('active', '生效中'),
        ('cancelled', '已取消'),
        ('past_due', '逾期'),
    ], default='active')
    started_at = models.DateTimeField('开始时间')
    ended_at = models.DateTimeField('结束时间', null=True, blank=True)
    # 按比例计算（月中升级）
    next_billing_date = models.DateField('下次扣费日')

    def pro_rate_upgrade(self, new_plan, upgrade_date):
        """月中升级按比例计算差价"""
        days_in_month = days_in_month(upgrade_date)
        remaining_days = days_in_month - upgrade_date.day + 1
        old_daily = self.plan_price(self.plan) / days_in_month
        new_daily = self.plan_price(new_plan) / days_in_month
        extra_charge = (new_daily - old_daily) * remaining_days
        return round(extra_charge, 2)

class UsageRecord(models.Model):
    """用量记录——用于超额计费"""
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    billing_month = models.CharField('计费月份', max_length=7)  # 2026-06
    metric = models.CharField('指标', max_length=50)  # api_calls, storage_mb, users
    usage = models.IntegerField('用量', default=0)
    quota = models.IntegerField('配额', default=0)
    overage = models.IntegerField('超额', default=0)
    overage_charge = models.DecimalField('超额费用', max_digits=10, decimal_places=2, default=0)
```

### 8.3 扣费流程

```
每月1日 00:00
    ↓
遍历所有活跃订阅
    ↓
计算上月用量（免费配额内不收费）
    ↓
计算超额费用
    ↓
├─ 余额足够 → 扣费 → 发送账单通知
└─ 余额不足 → 标记逾期(past_due)
       ↓
    逾期第3天：发送催缴通知
    逾期第7天：限制功能（只读模式）
    逾期第14天：冻结租户（不可登录）
    逾期第30天：数据归档删除
       ↓
    任何时候补费 → 解冻，恢复正常
```

### 8.4 支付网关接入

```python
class PaymentGateway(models.Model):
    """支付网关配置"""
    GATEWAY_CHOICES = [
        ('alipay', '支付宝'),
        ('wechat', '微信支付'),
        ('stripe', 'Stripe（国际）'),
    ]
    gateway = models.CharField('网关', max_length=20, choices=GATEWAY_CHOICES)
    config = models.JSONField('配置', default=dict)
    # app_id, private_key, public_key 等
    is_active = models.BooleanField('启用', default=True)

class PaymentTransaction(models.Model):
    """支付交易记录"""
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    type = models.CharField('类型', max_length=20, choices=[
        ('subscription', '订阅费'),
        ('overage', '超额费'),
        ('refund', '退款'),
    ])
    amount = models.DecimalField('金额', max_digits=10, decimal_places=2)
    gateway = models.CharField('支付网关', max_length=20)
    gateway_trade_no = models.CharField('网关交易号', max_length=100)
    status = models.CharField('状态', max_length=20, default='pending')
    paid_at = models.DateTimeField('支付时间', null=True, blank=True)
```

### 8.5 给租户开票

```
平台自动为每笔支付生成发票（电子发票）：
  1. 支付成功后 → 自动生成发票记录
  2. 租户可在平台管理端下载（PDF）
  3. 发票抬头 = 租户配置的公司名称+税号
  4. 支持增值税普通发票/专用发票
```

---

## 9. 租户数据导出与退租流程

> 这是恒鑫兴没有、但成熟SaaS平台必须具备的能力。企业对数据主权越来越重视。

### 9.1 数据导出（租户自助）

```python
class TenantDataExport(models.Model):
    """租户数据导出请求"""
    STATUS_CHOICES = [
        ('pending', '待处理'),
        ('processing', '导出中'),
        ('completed', '已完成'),
        ('failed', '导出失败'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    requester = models.ForeignKey(TenantUser, on_delete=models.CASCADE)
    export_format = models.CharField('导出格式', max_length=10, choices=[
        ('json', 'JSON（通用格式）'),
        ('csv', 'CSV（Excel可打开）'),
        ('xlsx', 'Excel'),
        ('db_dump', 'SQL（完整数据库）'),
    ], default='json')
    include_files = models.BooleanField('包含附件', default=True)
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='pending')
    download_url = models.CharField('下载地址', max_length=500, blank=True)
    expires_at = models.DateTimeField('下载链接过期时间')
    created_at = models.DateTimeField(auto_now_add=True)
```

**导出内容清单：**

```
租户数据导出包（ZIP格式）:
  ├── data/
  │   ├── finance_income.json        # 收入数据
  │   ├── finance_expense.json        # 支出数据
  │   ├── finance_wage_record.json    # 工资数据
  │   ├── finance_invoice.json        # 发票数据
  │   ├── crm_client.json             # 客户数据
  │   ├── crm_contract.json           # 合同数据
  │   ├── material_material.json      # 物料数据
  │   ├── purchasing_order.json       # 采购数据
  │   ├── tasks_project.json          # 项目数据
  │   └── ...                         # 所有业务表
  ├── files/                          # 附件文件
  │   ├── contracts/                  # 合同附件
  │   ├── invoices/                   # 发票附件
  │   ├── certs/                      # 证书附件
  │   └── ...                         # 按模块归类
  └── export_manifest.json            # 导出清单（含数据量、时间戳、校验码）
```

### 9.2 退租流程

```
租户发起退租申请
    ↓ ──────────────────────────────────────────┐
    ↓                                             │
  1. 核对未结清费用                               │
    ├─ 有欠款 → 提示先结清                         │
    └─ 无欠款 → 继续                              │
    ↓                                             │
  2. 引导数据导出（自助导出工具）                    │
    ↓             退租过程有7天反悔期                │
  3. 确认退租 → 进入7天冷静期                       │
    ↓                                             │
  4. 冷静期内 → 租户可随时取消退租                   │
    ↓                                             │
  5. 冷静期结束                                   │
    ├─ 租户取消退租 → 恢复正常                     │
    └─ 确认退租 → 执行数据保留策略                   │
          ↓                                       │
      数据保留期（30天）：                           │
      · 租户不可登录                                │
      · 数据完整保留（只读锁定）                      │
      · 管理员可登录下载数据                          │
          ↓                                       │
      30天后 → 数据彻底删除                         │
      · 所有业务数据 DELETE                         │
      · 附件文件 RM -RF                            │
      · 租户记录保留（仅租户名/退租时间/金额统计）     │
      · 发送"数据已清理"通知                         │
```                                                  │

### 9.3 合规要求

```yaml
# 不同地区的数据保留要求
regions:
  CN:
    - 电子商务法: 交易记录保留不少于3年
    - 会计法: 财务凭证保留不少于10年
    - 处理: 退租后业务数据删除，但财务记录匿名化保留

  EU (GDPR):
    - 用户有权要求删除所有数据（被遗忘权）
    - 处理时限: 30天内完成
    - 处理: 收到删除请求后全量清理，出具删除证明

  US:
    - 各州法规不同
    - 处理: 默认保留90天，按需协商

# 我们的策略（默认）
default_policy:
  - 退租后业务数据保留30天（供下载）
  - 30天后删除业务数据
  - 财务记录匿名化保留（仅保留金额/日期/科目，删除客户名/员工名）
  - 平台统计保留（如"该租户曾使用100次API"用于平台统计）
```

### 9.4 租户从Free升级到Pro的数据迁移

> 这点对应我们文档中的升级迁移（共享→Schema），但补充了用户视角的体验流程：

```
用户在平台管理端点击"升级套餐"
    ↓
选择Pro套餐 → 确认支付
    ↓
支付成功
    ↓
系统自动执行：
  ├─ 创建独立Schema
  ├─ 全量复制数据（带进度条，预计耗时：100M数据约5分钟）
  ├─ 数据校验（COUNT+SUM双校验）
  ├─ 切换路由表（更新db_mode为schema）
  └─ 发送"升级成功"通知
    ↓
用户无感——全程不需要退出登录
```

---

## 10. 灾备与恢复计划

> 客户问"你们数据安全吗"的时候，你得拿得出具体数字和方案，而不是说"我们很安全"。

### 10.1 RPO/RTO 定义

| 租户等级 | RPO（最大数据丢失） | RTO（最大恢复时间） | 备份频率 |
|---------|------------------|------------------|---------|
| Free | 24小时 | 48小时 | 每天全量备份 |
| Pro | 1小时 | 4小时 | 每1小时WAL归档 + 每天全量 |
| Enterprise | 5分钟 | 30分钟 | 实时流复制 + 每5分钟WAL归档 |

### 10.2 备份策略

```yaml
# backup_strategy.yaml
backup:
  free:
    type: full
    schedule: "0 2 * * *"    # 每天凌晨2点
    retention: 7天
    storage: 对象存储(OSS/S3)

  pro:
    type: full + WAL
    schedule: "0 2 * * *"    # 全量每天
    wal_interval: 1小时
    retention: 30天
    storage: 对象存储 + 异地副本

  enterprise:
    type: streaming + WAL
    replica: 只读副本(实时同步)
    wal_interval: 5分钟
    retention: 90天
    storage: 对象存储 + 异地副本 + 磁带归档(季度)
```

### 10.3 灾难恢复演练

```yaml
# dr_drill.yaml
演练计划:
  季度演练（Q1/Q2/Q3/Q4）:
    场景:
      - 模拟单DB实例故障 → 从备份恢复
      - 模拟服务器宕机 → 切换到备用服务器
      - 模拟数据损坏 → 时间点恢复(PITR)

    验证指标:
      - Free: RTO < 48h, RPO < 24h
      - Pro: RTO < 4h, RPO < 1h
      - Enterprise: RTO < 30min, RPO < 5min

    演练记录:
      - 演练日期
      - 实际RTO/RPO
      - 发现的问题
      - 改进措施

  年度演练（Q4）:
    场景: 模拟全站灾难（双机房同时故障）
    目标: 从异地冷备重建全平台
    RTO: < 72小时
```

### 10.4 多区域部署（未来规划）

```
┌─ 华南区（深圳） ─┐     ┌─ 华东区（上海） ─┐
│  主集群           │     │  灾备集群         │
│  · 读写            │ ←─→│  · 只读           │
│  · 实时数据        │  WAN│  · 异步复制       │
└──────────────────┘     └──────────────────┘
         │                        │
         ↓                        ↓
┌─────────────────────────────────────────────┐
│             对象存储（OSS/S3）                  │
│          所有备份集中存储                       │
│          多地冗余（至少3副本）                    │
└─────────────────────────────────────────────┘
```

---

## 11. Webhook/事件通知系统

> SaaS平台的价值不仅在于自身功能，更在于能与其他系统集成。**Webhook是SaaS平台的"API中的API"。**

### 11.1 事件清单

```python
class WebhookEvent:
    """平台事件类型"""

    # 财务事件
    INCOME_CREATED = 'finance.income.created'           # 收入创建
    EXPENSE_CREATED = 'finance.expense.created'         # 支出创建
    INVOICE_ISSUED = 'finance.invoice.issued'           # 发票开出
    PAYMENT_RECEIVED = 'finance.payment.received'       # 收款到账
    PAYMENT_SENT = 'finance.payment.sent'               # 付款成功

    # 业务事件
    ORDER_CREATED = 'sales.order.created'               # 销售订单创建
    ORDER_SHIPPED = 'sales.order.shipped'               # 销售订单发货
    CONTRACT_SIGNED = 'crm.contract.signed'             # 合同签署
    PROJECT_COMPLETED = 'tasks.project.completed'       # 项目完成

    # 预警事件
    STOCK_LOW = 'inventory.stock.low'                   # 库存预警
    RECEIVABLE_OVERDUE = 'finance.receivable.overdue'   # 应收逾期
    CONTRACT_EXPIRING = 'crm.contract.expiring'         # 合同即将到期

    # 系统事件
    USER_CREATED = 'system.user.created'                # 用户创建
    TENANT_USAGE_EXCEEDED = 'system.tenant.usage.exceeded'  # 用量超限
```

### 11.2 Webhook配置

```python
class WebhookEndpoint(models.Model):
    """Webhook端点配置"""
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    url = models.URLField('回调地址')
    secret = models.CharField('签名密钥', max_length=64)
    events = models.JSONField('订阅事件', default=list)
    # 如: ["finance.income.created", "finance.payment.received"]

    is_active = models.BooleanField('启用', default=True)
    retry_count = models.IntegerField('重试次数', default=3)
    timeout_seconds = models.IntegerField('超时秒数', default=10)
    last_sent_at = models.DateTimeField('最后发送时间', null=True)
    last_error = models.TextField('最后错误', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class WebhookDeliveryLog(models.Model):
    """Webhook投递日志"""
    endpoint = models.ForeignKey(WebhookEndpoint, on_delete=models.CASCADE)
    event_type = models.CharField('事件类型', max_length=100)
    payload = models.JSONField('事件数据')
    status = models.CharField('状态', max_length=20, choices=[
        ('success', '成功'),
        ('failed', '失败'),
        ('retrying', '重试中'),
    ])
    response_code = models.IntegerField('响应状态码', null=True)
    response_body = models.TextField('响应内容', blank=True)
    attempt = models.IntegerField('尝试次数', default=1)
    duration_ms = models.IntegerField('耗时(ms)', default=0)
    created_at = models.DateTimeField(auto_now_add=True)
```

### 11.3 投递保障

```python
# 投递机制
delivery_guarantee:
  - at_least_once: 至少投递一次（可能重复，消费端需幂等）
  - 重试策略: 指数退避（1s → 3s → 9s → 27s → 81s），最多5次
  - 死信队列: 5次重试失败后进入死信队列，人工干预
  - 超时处理: 10秒无响应视为失败

# 签名验证
signing:
  algorithm: HMAC-SHA256
  header: X-Webhook-Signature
  format: "sha256=#{hexdigest}"
  payload: "#{timestamp}.#{body}"

# 幂等性
idempotency:
  header: X-Webhook-Id
  说明: 每个事件有唯一ID，消费端可据此去重
```

### 11.4 应用场景

```
1. 与银行系统集成
   租户有收款到账 → Webhook推送给银行 → 自动对账

2. 与WMS/仓储系统集成
   销售订单发货 → Webhook推送给WMS → 仓库人员拣货

3. 与电子发票平台集成
   发票开出 → Webhook推送给税控平台 → 自动上传税局

4. 与钉钉/企微集成（已有通知渠道外的补充）
   审批超时 → Webhook推送给自有系统 → 自定义处理
```

---

## 12. 租户级功能开关（Feature Flags）

> 没有Feature Flags的SaaS平台，每次上线都是赌博。有了flags，你可以在1%租户上试新功能，出问题只影响1%。

### 12.1 为什么需要

```
没有Feature Flags:
  开发完成 → 全量上线 → 出Bug → 影响所有租户 → 紧急回滚 → 用户骂街

有Feature Flags:
  开发完成 → 选5%租户开启 → 监控24h → 逐步扩到50% → 100% → 安全上线
```

### 12.2 功能开关模型

```python
class FeatureFlag(models.Model):
    """功能开关定义"""
    name = models.CharField('开关名称', max_length=100, unique=True)
    code = models.CharField('开关代码', max_length=50, unique=True)
    description = models.TextField('说明', blank=True)

    # 默认值（未配置时的行为）
    default_value = models.BooleanField('默认开启', default=False)

    # 开关层级
    scope = models.CharField('作用范围', max_length=20, choices=[
        ('global', '全局'),
        ('tenant', '按租户'),
        ('user', '按用户'),
    ], default='tenant')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class TenantFeatureFlag(models.Model):
    """租户级功能开关配置"""
    feature = models.ForeignKey(FeatureFlag, on_delete=models.CASCADE)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    is_enabled = models.BooleanField('启用', default=False)

    # 灰度比例（按租户ID哈希决定）
    rollout_percentage = models.IntegerField('灰度比例%', default=0,
        help_text='0=关闭，100=全部开启，50=50%租户开启')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('feature', 'tenant')]

class UserFeatureFlag(models.Model):
    """用户级功能开关"""
    feature = models.ForeignKey(FeatureFlag, on_delete=models.CASCADE)
    user = models.ForeignKey(TenantUser, on_delete=models.CASCADE)
    is_enabled = models.BooleanField('启用', default=False)
    expires_at = models.DateTimeField('过期时间', null=True, blank=True)
    # 用于临时给某个用户开启测试权限
```

### 12.3 灰度发布流程

```python
def is_feature_enabled(feature_code, user, tenant):
    """判断功能是否对当前用户开启"""
    flag = FeatureFlag.objects.filter(code=feature_code).first()
    if not flag:
        return False

    if flag.scope == 'global':
        return flag.default_value

    elif flag.scope == 'tenant':
        # 1. 检查是否有显式配置
        tf = TenantFeatureFlag.objects.filter(
            feature=flag, tenant=tenant
        ).first()
        if tf:
            return tf.is_enabled

        # 2. 按灰度比例（哈希一致性，同一租户结果稳定）
        hash_val = hash(f"{tenant.id}_{flag.id}") % 100
        return hash_val < flag.rollout_percentage

    elif flag.scope == 'user':
        uf = UserFeatureFlag.objects.filter(
            feature=flag, user=user
        ).first()
        if uf:
            return uf.is_enabled and (not uf.expires_at or uf.expires_at > now())
        return flag.default_value
```

### 12.4 典型场景

```yaml
场景1: 新UI灰度
  flag_code: ui_v2_dashboard
  scope: tenant
  rollout_percentage: 5
  验证: 5%租户看到新版仪表盘，95%不变
  发现Bug → 立即关闭（影响只限5%）
  确认稳定 → 逐步提升到100%

场景2: 新功能内测
  flag_code: beta_certification_module
  scope: user
  为选定的内测用户开启:
    UserFeatureFlag(user=张三, feature=beta_cert, expires_at=2026-07-01)
  到期自动关闭

场景3: 系统级切换
  flag_code: use_v2_engine
  scope: global
  default_value: false
  新引擎验证通过 → 改为true → 全量生效
  出问题 → 改回false → 瞬间回滚（无需部署）
```

### 12.5 管理界面

```
功能开关管理（在平台管理端内）:
  ┌─────────────────────────────────────────────┐
  │  Feature Flags                              │
  ├──────────────┬──────┬──────┬──────┬────────┤
  │ 开关          │ 全局  │ 灰度% │ 租户  │ 操作   │
  ├──────────────┼──────┼──────┼──────┼────────┤
  │ ui_v2_dash    │ OFF  │  5%  │  3   │ ⚙️     │
  │ beta_cert     │ OFF  │  --  │  1   │ ⚙️     │
  │ use_v2_engine │ ON   │ 100% │ 全部  │ ⚙️     │
  │ new_invoice   │ OFF  │  0%  │  0   │ ⚙️     │
  └──────────────┴──────┴──────┴──────┴────────┘
```

### 8.1 数据库层优化

| 策略 | 实现 | 预期效果 |
|------|------|---------|
| 读写分离 | 主库写入 + 从库查询（Enterprise） | 查询性能提升3-5x |
| 连接池 | PgBouncer/内置连接池 | 减少连接建立开销 |
| 慢查询告警 | >500ms 查询记录+通知 | 及时发现性能问题 |
| 查询缓存 | Redis缓存热门查询（按租户KV） | 重复查询提速100x |
| 索引优化 | 所有tenant_id+常用查询字段建复合索引 | 过滤速度提升10x+ |

**复合索引标准：**

```sql
-- 标准索引（所有业务表必须）
CREATE INDEX idx_{table}_tenant ON {table}(tenant_id);
CREATE INDEX idx_{table}_tenant_created ON {table}(tenant_id, created_at);
CREATE INDEX idx_{table}_tenant_status ON {table}(tenant_id, status);

-- 高频查询索引
CREATE INDEX idx_{table}_tenant_date ON {table}(tenant_id, date DESC);
CREATE INDEX idx_{table}_tenant_ref ON {table}(tenant_id, reference_id);
```

### 8.2 缓存策略

```
请求 → 检查Redis缓存
  ├─ 命中 → 返回
  └─ 未命中
       ├─ 查数据库
       └─ 写入Redis（按租户分区）
            Key格式: {tenant_id}:{module}:{object_type}:{id}
            TTL: 高频数据300s，低频数据3600s
```

| 缓存对象 | 缓存键 | TTL | 说明 |
|---------|--------|-----|------|
| 系统参数 | {tid}:sys:params | 3600s | 租户配置读取频繁 |
| 菜单列表 | {tid}:sys:menu | 1800s | 用户切换页面频繁 |
| 权限列表 | {tid}:user:{uid}:perms | 600s | 每次API调用检查 |
| 路由表 | tenant_route:{domain} | 3600s | 每个请求使用 |
| 字典数据 | {tid}:dict:{type} | 1800s | 下拉选项等 |
| 统计数据 | {tid}:stats:{type} | 300s | 仪表盘数据 |

### 8.3 限流策略

```python
# 按租户API限流
class TenantRateLimiter:
    """租户级限流——防止单个租户打满所有资源"""

    # Free租户
    FREE_LIMITS = {
        'rpm': 60,      # 每分钟请求数
        'rpd': 5000,    # 每天请求数
        'concurrent': 5 # 并发连接数
    }

    # Pro租户
    PRO_LIMITS = {
        'rpm': 300,
        'rpd': 50000,
        'concurrent': 20
    }

    # Enterprise租户
    ENTERPRISE_LIMITS = {
        'rpm': 1000,
        'rpd': 200000,
        'concurrent': 50
    }
```

### 8.4 冷热数据分离

```python
# 活跃租户 vs 不活跃租户
class TenantActivityClassifier:
    """租户活跃度分类器——决定资源分配优先级"""

    def classify(self, tenant_id):
        last_active = TenantMetrics.get_last_active(tenant_id)
        days_since_active = (now() - last_active).days

        if days_since_active <= 1:
            return 'hot'      # 活跃：全资源
        elif days_since_active <= 7:
            return 'warm'     # 周活跃：标准资源
        elif days_since_active <= 30:
            return 'cool'     # 月活跃：低资源
        else:
            return 'cold'     # 冷租户：最小资源+数据归档
```

---

## 13. 可维护性设计

### 9.1 在线数据迁移

```
┌────────────────────────────────────────────┐
│          在线租户数据迁移流程                  │
├────────────────────────────────────────────┤
│ 1. 创建目标Schema/DB                         │
│ 2. 双写（同时写入源+目标）（可选）              │
│ 3. 全量复制（分批流式）                        │
│ 4. 增量同步（追平差距）                        │
│ 5. 数据校验（行数+SUM校验）                    │
│ 6. 切换路由（更新路由表）                      │
│ 7. 验证（完整功能测试）                        │
│ 8. 清理源端（30天保留）                       │
└────────────────────────────────────────────┘
### 13.1 在线数据迁移

### 13.2 灰度发布

### 13.3 自动化运维脚本
# deploy/green_deploy.yaml
灰度发布策略:
  步骤1: 内部测试环境 → 验证通过
  步骤2: 金丝雀租户（选择5个试用租户）→ 监控24h
  步骤3: 10% Free租户 → 监控24h
  步骤4: 50% 租户 → 监控12h
  步骤5: 100% 全量发布
  步骤6: 回滚预案（如有异常，30分钟内回滚）

每批次验证指标:
  - API错误率 < 0.1%
  - 平均响应时间 < 200ms
  - 无5xx错误
  - 无tenant_id隔离破坏
```

### 9.3 自动化运维脚本

```bash
# check_tenant_health.sh — 租户健康巡检
#!/bin/bash

for tenant in $(psql -c "SELECT tenant_code FROM platform_tenant_route WHERE is_active=true" -t); do
    echo "=== 检查租户: $tenant ==="

    # 1. 可达性检测
    curl -s -o /dev/null -w "%{http_code}" "https://$tenant.green-erp.com/api/health"

    # 2. 数据库连接检测
    psql -c "SELECT 1 FROM tenant_${TENANT_ID}.finance_income LIMIT 1"

    # 3. 缓存检测
    redis-cli PING

    # 4. 磁盘使用率
    df -h | grep /data

    # 5. 告警（错误率 > 5%）
    if [ $ERROR_RATE -gt 5 ]; then
        send_alert "租户 $tenant 错误率超过5%"
    fi
done
```

---

## 14. 安全管理

### 14.1 防跨租户攻击（OTG-BUSLOGIC-001）

```python
class TenantSecurityMiddleware:
    """防跨租户攻击——每30秒可测试1次绕过漏洞"""

    TENANT_ENFORCED_MODELS = [
        'Income', 'Expense', 'WageRecord', 'Invoice',
        'SocialRecord', 'Client', 'Supplier', 'Contract',
        'Material', 'PurchaseOrder', 'Project', 'Task',
        'Notification', 'BankStatement', 'Budget'
    ]

    def validate_tenant_access(self, request, model_name, object_id):
        """每次数据访问校验tenant_id"""
        tenant_id = request.tenant_id

        # 从查询中解析实际数据
        obj = getattr(models, model_name).objects.get(id=object_id)

        # 校验
        if obj.tenant_id != tenant_id:
            # 记录安全事件
            SecurityAuditLog.objects.create(
                type='crosstenant_attack',
                severity='critical',
                detail=f"用户{request.user.id}尝试访问租户{obj.tenant_id}的数据"
            )
            raise PermissionDenied('跨租户访问被阻止')
```

### 14.2 数据加密

```python
# 敏感字段加密（AES-256-GCM）
class EncryptedField:
    """加密字段——自动加密写入，解密读取"""

    def encrypt(self, plaintext):
        if not plaintext:
            return None
        cipher = AES.new(MASTER_KEY, AES.MODE_GCM)
        ct, tag = cipher.encrypt_and_digest(plaintext.encode())
        return base64.b64encode(cipher.nonce + tag + ct)

    def decrypt(self, ciphertext):
        if not ciphertext:
            return ''
        data = base64.b64decode(ciphertext)
        nonce, tag, ct = data[:16], data[16:32], data[32:]
        cipher = AES.new(MASTER_KEY, AES.MODE_GCM, nonce=nonce)
        return cipher.decrypt_and_verify(ct, tag).decode()
```

加密字段清单：身份证号、银行卡号、银行账号、密码、API密钥

### 14.3 安全审计日志

```python
class SecurityAuditLog(models.Model):
    """安全审计日志——不可篡改（仅追加）"""
    SEVERITY_CHOICES = [
        ('info', '信息'),
        ('warning', '警告'),
        ('critical', '严重'),
    ]

    event_type = models.CharField(max_length=50)  # login_fail, crosstenant, api_abuse
    tenant_id = models.IntegerField(null=True)
    user_id = models.IntegerField(null=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    detail = models.JSONField(default=dict)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'platform_security_audit_log'
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['tenant_id', 'event_type']),
        ]

    @classmethod
    def log(cls, event_type, tenant_id, user_id, ip, detail, severity='info'):
        """追加日志（仅允许写入，不允许修改或删除）"""
        # 写入后同步到独立的安全日志库（不可变存储）
        record = cls.objects.create(
            event_type=event_type,
            tenant_id=tenant_id,
            user_id=user_id,
            ip_address=ip,
            detail=detail,
            severity=severity
        )
        # 同步到远程日志存储（防篡改）
        sync_to_immutable_storage(record)
```

---

## 15. 功能模块的多租户适配

### 11.1 所有模块必须遵守的规则

```python
# 规则1: 所有模型继承 TenantAwareModel
class MyModel(TenantAwareModel):
    ...

# 规则2: 所有序列化器自动注入tenant_id
class MySerializer(serializers.ModelSerializer):
    def create(self, validated_data):
        validated_data['tenant'] = self.context['request'].tenant
        return super().create(validated_data)

# 规则3: 所有视图集自动过滤
class MyViewSet(viewsets.ModelViewSet):
    queryset = MyModel.objects.all()

    def get_queryset(self):
        return self.queryset.filter(tenant=self.request.tenant)

# 规则4: 所有导出/导入带租户标识
class ExportMixin:
    def export_data(self, queryset):
        filename = f"export_{self.request.tenant.code}_{datetime.now():%Y%m%d}.xlsx"
### 15.1 所有模块必须遵守的规则

### 15.2 配置隔离

### 15.3 文件隔离
|--------|---------|------|
| 公司名称/Logo | 租户独立 | 登录页、页头、发票抬头 |
| 编码规则 | 租户独立 | 员工/客户/合同独立序列 |
| 精度设置 | 租户独立 | 金额小数位数 |
| 日期格式 | 租户独立 | YYYY-MM-DD 或 DD/MM/YYYY |
| 时区 | 租户独立 | 中国/美国/欧洲 |
| 邮件模板 | 租户独立 | 通知内容自定义 |
| 审批模板 | 租户独立 | 审批流配置 |
| 菜单配置 | 租户独立 | 按套餐开启/关闭模块 |
| 系统参数 | 全局+租户覆盖 | 全局默认值，租户可覆盖 |

### 11.3 文件隔离

```python
# 每个租户独立文件存储路径
STORAGE_PATH_TEMPLATE = "/data/tenants/{tenant_code}/{module}/{year}/{month}/{filename}"

# 示例
/data/tenants/hxx/finance/invoices/2026/05/FP20260501.pdf
/data/tenants/bc/crm/contracts/2026/03/HT20260315.pdf
/data/tenants/ljn/tasks/attachments/2026/04/附件.zip
```

---

## 16. 迁移路径（从单租户→多租户）

### 16.1 当前状态

```
当前：单服务器 + 单DB + 公司(Company)字段隔离 + SESSION切换
目标：多租户SaaS平台
差距：company_id 未覆盖所有表、无路由系统、无平台管理端
```

### 16.2 分阶段迁移

#### Phase 1：加固（2周）
```
目标：补全所有 model 的 company_id → 适配 tenant_id 规范
任务：
  □ 创建 Tenant 模型（替代或扩展 Company）
  □ 所有模型增加 tenant_id字段（Django migration）
  □ 补全缺失 company_id 的表（如 Material, Notification 已用 company_id）
  □ 创建 TenantAwareModel 基类
  □ 编写中间件（自动过滤 + Session绑定）
  □ 数据回填（现有数据的 company_id 对应到 tenant_id）
  □ 全量测试：所有模块 tenant_id 过滤有效
```

#### Phase 2：路由与域名（2周）
```
目标：支持子域名访问
任务：
  □ 通配符域名 → Nginx配置
  □ 路由表模型 + Redis缓存
  □ 域名解析 → 租户匹配
  □ 自定义域名支持
  □ SSL证书自动管理
  □ 测试：多个子域名同时访问
  □ 兼容旧 session 登录（平滑过渡）
```

#### Phase 3：平台管理端（3周）
```
目标：从命令行运维 → 图形化平台管理
任务：
  □ 平台管理员认证（MFA）
  □ 租户列表/详情/创建
  □ 租户停用/启用/删除
  □ 租户套餐管理
  □ 用量监控面板
  □ 平台审计日志
  □ 系统公告/通知
  □ 操作日志查询
```

#### Phase 4：自助注册与计费（3周）
```
目标：用户可自助注册、试用、付费
任务：
  □ 注册页面（邮箱/手机验证）
  □ 租户自动初始化（角色/参数/数据）
  □ 14天试用管理
  □ 套餐价格体系
  □ 支付网关接入（支付宝/微信）
  □ 发票/合同管理（租户合同）
  □ 升级/降级流程
  □ 数据迁移（共享→独立Schema）
```

#### Phase 5：性能与安全（持续）
```
目标：企业级性能和安全性
任务：
  □ 读写分离（Enterprise独享）
  □ Redis缓存策略优化
  □ 租户级限流
  □ 安全渗透测试
  □ 防跨租户攻击检测
  □ 数据加密（敏感字段）
  □ 冷热数据分离
  □ 自动化巡检脚本
```

---

## 17. 对比分析

### 17.1 我们 vs 恒鑫兴

| 维度 | 恒鑫兴(狞猫云) | GREEN ERP 多租户方案 | 更优点 |
|------|--------------|--------------------|--------|
| 租户路由 | 子域名硬编码在Nginx | 数据库路由表+Redis缓存 | 动态新增，无需运维操作 |
| 数据隔离 | 仅字段级(tenant_id) | 三级混合(字段/Schema/独立DB) | 按需选择，弹性扩展 |
| 租户安全 | tenant_id明文在JWT | 服务端Session绑定+双重校验 | 防篡改，更安全 |
| 平台管理 | 无 | 完整管理端(租户/套餐/监控/审计) | 大幅降低运维成本 |
| 自助注册 | 无 | 全流程自助(邮箱→初始→试用) | 获客成本接近0 |
| 自定义域名 | 不支持 | 支持(含自动SSL) | 企业客户刚需 |
| SSO | 不支持 | 支持OAuth2/SAML/CAS | 对接企业现有认证 |
| 性能隔离 | 无(共享DB) | 按等级分配资源+限流 | 大租户不拖慢小租户 |
| 冷热分离 | 无 | 活跃/非活跃租户资源差异化 | 资源利用率提升30%+ |
| 灰度发布 | 无 | 按租户分批灰度 | 降低发布风险 |

### 17.2 我们 vs 业界最佳实践

| 维度 | Salesforce | Shopify | GREEN ERP |
|------|-----------|---------|-----------|
| 租户模型 | 共享DB+Metadata | 独立DB(每租户) | Hybrid混合 |
| API版本 | REST+GraphQL | REST+GraphQL | REST |
| 平台扩展 | Apex/Flow | App Store | 审批流引擎 |
| 定价模式 | Per User/Per Month | 套餐月费 | 套餐+用量混合 |
| 数据导出 | 全量+增量 | CSV/Bulk API | 逐租户+全平台 |

我们的创新点：**Hybrid混合隔离**——根据租户等级智能选择隔离方案，既控制成本又保障性能，是SMB和中型企业市场的平衡方案。

---

## 18. 附录：标准与规范

### 18.1 数据模型规范

```yaml
# 所有租户表必须遵守
rules:
  - field: tenant_id
    type: IntegerField
    null: false
    default: 0
    index: true
    description: 所属租户ID

  - field: created_at
    type: DateTimeField
    auto_now_add: true
    description: 创建时间

  - field: updated_at
    type: DateTimeField
    auto_now: true
    description: 更新时间

  - condition: 所有ForeignKey引用必须跨租户安全
    action: 确保被引用的对象在同一租户下

# 禁止
forbidden:
  - 在业务代码中直接使用 .all() 而不带tenant_id过滤
  - 跨租户的ForeignKey引用
  - 在数据库级别直接执行不带tenant_id的SQL
```

### 18.2 API规范

```yaml
# 多租户API规范
headers:
  - name: X-Tenant-Id
    type: Integer
    optional: true
    description: 租户ID（JWT和Session失效时备用）

  - name: Authorization
    type: Bearer Token
    required: true
    description: JWT或API Token

# 响应格式
success:
  code: 0
  message: "success"
  data: { ... }

error:
  code: 1001   # 错误码
  message: "租户不存在"
  detail: "未找到对应租户ID的活跃记录"

# 错误码范围
error_codes:
  1000-1099: 认证授权错误
  1100-1199: 租户相关错误
  1200-1299: 隔离相关错误
  2000-2999: 业务逻辑错误
```

### 18.3 测试规范

```python
# 多租户测试模板
class TenantTestCase(TestCase):
    """多租户测试基类"""

    def setUp(self):
        self.tenant_a = Tenant.objects.create(name='公司A', code='comp_a')
        self.tenant_b = Tenant.objects.create(name='公司B', code='comp_b')

        self.user_a = self._create_user(self.tenant_a, 'admin_a')
        self.user_b = self._create_user(self.tenant_b, 'admin_b')

    def test_tenant_isolation(self):
        """测试：租户A的数据对租户B不可见"""
        # 租户A创建数据
        self._login_as(self.tenant_a, self.user_a)
        Income.objects.create(tenant=self.tenant_a, amount=100)

        # 租户B查询（应该看不到）
        self._login_as(self.tenant_b, self.user_b)
        qs = Income.objects.all()
        self.assertEqual(qs.count(), 0)

    def test_crosstenant_blocked(self):
        """测试：跨租户访问被阻止"""
        self._login_as(self.tenant_a, self.user_a)
        income = Income.objects.create(tenant=self.tenant_a, amount=100)

        # 尝试跨租户访问
        with self.assertRaises(PermissionDenied):
            self.client.get(f'/api/finance/income/{income.id}/',
                          HTTP_X_TENANT_ID=self.tenant_b.id)
```

### 18.4 部署规范

```yaml
# 生产环境部署清单
infrastructure:
  nginx:
    - 通配符证书配置
    - 自定义域名转发
    - 限流配置(按域名)

  database:
    - PostgreSQL 15+
    - 连接池(PgBouncer)
    - 读写分离配置
    - 备份策略(按租户)

  cache:
    - Redis 7+
    - 集群模式(3节点)
    - RDB+AOF持久化
    - 内存使用率监控

  application:
    - Gunicorn + Uvicorn
    - 水平扩展(3+实例)
    - 健康检查端点
    - 优雅关闭

  monitoring:
    - Prometheus + Grafana
    - 租户级指标
    - 告警规则
    - 日志聚合(ELK)
```

---

> 本文档为GREEN ERP SaaS平台多租户架构设计规范，所有开发、测试、运维工作必须以此文档为基准。与现有系统设计冲突时，以本文档为准进行升级改造。
