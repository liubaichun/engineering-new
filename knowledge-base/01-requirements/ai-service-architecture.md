# ERP AI 服务层架构设计

## 一、调研分析总结

### 1.1 本系统现状

**当前状态**：13个App，217个Python源文件，大量可接入AI的场景

| 维度 | 现状 |
|------|------|
| AI集成 | DeepSeek硬编码在 `crm/views.py` 一个action里 |
| API Key | 写在 `gunicorn.conf.py` 的 raw_env 中 |
| 错误处理 | 无，Key过期直接降级到正则回退 |
| 可用场景 | 34+个，跨所有模块 |

### 1.2 参考架构调研

#### Hermes Agent（本Agent运行平台）

**核心模式**：四层抽象 + 插件架构

```
ProviderProfile（声明式策略）
    ↓
Transport适配器（标准化转换）
    ↓
Runtime Provider解析（级联覆盖：job > env > config）
    ↓
核心循环（同步循环 + 预算控制）
```

关键设计：
- **ProviderProfile** dataclass：声明式描述认证/端点/行为特征
- **插件发现**：目录扫描 + 自注册 + 懒加载，第三方可drop-in
- **归一化响应**：所有Provider输出统一为 `NormalizedResponse`
- **级联覆盖**：cronjob > 环境变量 > config.yaml 三级优先级
- **Fallback链**：Credential Pool（同provider key轮转）→ Provider Fallback（跨provider切换）
- **Tool Registry**：自注册模式，工具自动发现

#### Clawith / OpenClaw（多Agent协作平台）

**核心模式**：统一客户端 + 数据库配置 + 自动故障转移

```
LLMModel（数据库配置表）
    ↓
create_llm_client()（工厂方法）
    ↓
LLMClient 抽象基类
    ├─ OpenAICompatibleClient（DeepSeek/Qwen/OpenRouter等~20个）
    ├─ AnthropicClient（Claude原生API）
    └─ GeminiClient（Google）
    ↓
call_llm() / call_llm_with_failover()（统一入口）
```

关键设计：
- **数据库存储模型配置**：`LLMModel` 表（provider, model, api_key_encrypted, base_url, enabled, supports_vision, max_tokens_per_day）
- **Provider注册表**：`PROVIDER_REGISTRY` 字典（20+内建provider），含 `ProviderSpec`(provider, display_name, protocol, default_base_url, default_max_tokens, model_max_tokens)
- **厂商别名系统**：`PROVIDER_ALIASES` 兼容不同写法
- **错误分类系统**：`FailoverErrorType`（RETRYABLE / NON_RETRYABLE）+ `classify_error()` 函数
- **Token配额管理**：基于数据库的每日/每月限额
- **FailoverGuard**：确保副作用操作后不自动切换模型

### 1.3 核心设计模式总结

| 模式 | 应用于 | 参考来源 |
|------|--------|---------|
| 适配器模式 | 模型厂商协议差异 → 统一客户端接口 | 两者 |
| 策略模式 | Provider注册 → 根据name路由到不同实现 | Clawith |
| 工厂方法 | create_llm_client() → 按provider创建客户端 | Clawith |
| 注册表模式 | PROVIDER_REGISTRY / Tool Registry | 两者 |
| 级联覆盖 | 模型配置优先级：页面 > DB > settings > 默认 | Hermes |
| Failover链 | 主模型失败 → fallback模型 | 两者 |
| 声明式配置 | Provider描述"是什么"而非"怎么做" | Hermes |
| 单例外观 | AIService统一入口，隐藏内部复杂性 | 两者 |

---

## 二、整体架构设计

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           系统级 AI 服务层                                │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────┐      │
│  │  AIService (单例外观)                                            │      │
│  │  app.services.ai_service                                       │      │
│  │                                                                │      │
│  │  ├─ chat(model, messages, **kwargs)           → 文本对话        │      │
│  │  ├─ extract(model, schema, text, **kwargs)    → 结构化提取      │      │
│  │  ├─ analyze(model, prompt, **kwargs)          → 分析结果        │      │
│  │  ├─ classify(model, categories, text)         → 智能分类        │      │
│  │  ├─ summarize(model, text, **kwargs)          → 文本摘要        │      │
│  │  ├─ vision(model, image, prompt)              → 图片分析        │      │
│  │  ├─ switch_model(name)                        → 运行时切换      │      │
│  │  ├─ get_available_models()                    → 列出可用模型    │      │
│  │  └─ get_current_model()                       → 当前活跃模型    │      │
│  └───────────────────────────────────────────────────────────────┘      │
│                     ▲                          ▲                        │
│                     │                          │                        │
│  ┌──────────────────┴──────────────┐  ┌────────┴──────────────────┐     │
│  │  模型工厂 (Provider Router)      │  │  配置/状态管理             │     │
│  │  ┌─ OpenAICompatibleClient     │  │  ┌─ SystemSetting (DB)    │     │
│  │  │  ├─ DeepSeek                │  │  │  → active_model        │     │
│  │  │  ├─ OpenAI (GPT-4o)         │  │  │  → model_configs (JSON)│     │
│  │  │  ├─ Qwen (通义千问)          │  │  │  → fallback_mode       │     │
│  │  │  ├─ OpenRouter              │  │  └────────────────────────│     │
│  │  │  └─ 其他OpenAI兼容厂商       │  │                             │     │
│  │  ├─ AnthropicClient (Claude)   │  │  ┌─ settings.py           │     │
│  │  └─ GeminiClient (Google)      │  │  │  → AI_SERVICE_MODELS   │     │
│  │  └ (扩展点：新厂商加子类即可)   │  │  │  → AI_SERVICE_DEFAULTS │     │
│  └────────────────────────────────┘  └────────────────────────────┘     │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────┐      │
│  │  公共能力层                                                      │      │
│  │  ├─ 重试机制（指数退避: 429/5xx重试, 401/403不重试）               │      │
│  │  ├─ Failover链（主→备→降级，Tool执行后禁止failover）              │      │
│  │  ├─ 超时控制（每个模型可配，默认120s）                             │      │
│  │  ├─ Token计数/配额（每日/每月限额）                               │      │
│  │  ├─ 结果缓存（相同输入同模型复用，TTL可配）                       │      │
│  │  ├─ 错误日志+审计（OperationAuditLog记录AI调用）                   │      │
│  │  └─ 日志/性能统计（调用次数、耗时、Token消耗）                      │      │
│  └───────────────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────────────┘
         ▲            ▲            ▲            ▲            ▲
         │            │            │            │            │
    ┌────┴───┐   ┌───┴────┐   ┌──┴────┐   ┌───┴────┐   ┌───┴────┐
    │  crm   │   │finance │   │tasks  │   │material│   │其他模块  │
    │合同提取 │   │银行匹配 │   │工时估算│   │物料分类 │   │...      │
    │商机预测 │   │异常检测 │   │排程优化│   │库存预警│   │         │
    │客户画像 │   │现金流  │   │延期预警│   │BOM推荐 │   │         │
    └────────┘   └────────┘   └───────┘   └───────┘   └────────┘
```

---

## 三、详细设计

### 3.1 模型配置体系

#### 配置层级（优先级从高到低）

```
① SystemSetting 表（页面运行时切换）
   → key='ai_active_model'  → {"provider": "deepseek", "model": "deepseek-chat"}
   → key='ai_model_configs' → {"deepseek-chat": {"provider":"deepseek","api_key":"sk-...","base_url":"..."}}

② settings.py 代码级默认配置
   AI_SERVICE_MODELS: dict 定义所有可用模型
   AI_SERVICE_DEFAULTS: {'active_model': 'deepseek-chat', 'fallback_model': None}

③ gunicorn.conf.py / 环境变量
   AI_DEEPSEEK_API_KEY=sk-xxx
   AI_OPENAI_API_KEY=sk-xxx
```

#### settings.py 配置定义

```python
# config/settings/base.py

AI_SERVICE = {
    # 默认活跃模型
    'active_model': 'deepseek-chat',
    # 默认fallback
    'fallback_model': None,  # None=不启用自动fallback
    # 请求超时（秒）
    'request_timeout': 120,
    # 最大重试次数
    'max_retries': 3,
    # 结果缓存TTL（秒，0=不缓存）
    'cache_ttl': 0,
    # 模型定义
    'models': {
        'deepseek-chat': {
            'provider': 'deepseek',
            'display_name': 'DeepSeek Chat',
            'model': 'deepseek-chat',
            'max_tokens': 8192,
            'supports_vision': False,
        },
        'gpt-4o': {
            'provider': 'openai',
            'display_name': 'GPT-4o',
            'model': 'gpt-4o',
            'max_tokens': 16384,
            'supports_vision': True,
        },
        'claude-sonnet': {
            'provider': 'anthropic',
            'display_name': 'Claude Sonnet',
            'model': 'claude-sonnet-4-20250514',
            'max_tokens': 8192,
            'supports_vision': True,
        },
        'qwen-plus': {
            'provider': 'qwen',
            'display_name': '通义千问 Plus',
            'model': 'qwen-plus',
            'max_tokens': 16384,
            'supports_vision': True,
        },
    },
    # API Key来源映射（优先从环境变量读取，未设置则从SystemSetting表读取）
    'api_key_sources': {
        'deepseek': 'AI_DEEPSEEK_API_KEY',
        'openai': 'AI_OPENAI_API_KEY',
        'anthropic': 'AI_ANTHROPIC_API_KEY',
        'qwen': 'AI_QWEN_API_KEY',
    },
}
```

### 3.2 Provider 注册表设计

借鉴Clawith的 `PROVIDER_REGISTRY` 模式：

```python
# ai_service/providers.py

from dataclasses import dataclass, field
from typing import Literal, Optional

@dataclass
class ProviderSpec:
    """Provider注册信息"""
    provider: str               # 标识名: deepseek, openai, anthropic
    display_name: str           # 显示名: DeepSeek, OpenAI, Anthropic
    protocol: Literal['openai', 'anthropic']  # 协议类型
    default_base_url: Optional[str]  # 默认API端点
    default_max_tokens: int = 4096
    supports_vision: bool = False
    supports_streaming: bool = True

# 内建Provider注册表
PROVIDER_REGISTRY = {
    'deepseek': ProviderSpec(
        provider='deepseek', display_name='DeepSeek',
        protocol='openai',
        default_base_url='https://api.deepseek.com/v1',
        default_max_tokens=8192,
    ),
    'openai': ProviderSpec(
        provider='openai', display_name='OpenAI',
        protocol='openai',
        default_base_url='https://api.openai.com/v1',
        default_max_tokens=16384,
        supports_vision=True,
    ),
    'anthropic': ProviderSpec(
        provider='anthropic', display_name='Anthropic Claude',
        protocol='anthropic',
        default_base_url='https://api.anthropic.com',
        default_max_tokens=8192,
        supports_vision=True,
    ),
    'qwen': ProviderSpec(
        provider='qwen', display_name='通义千问',
        protocol='openai',
        default_base_url='https://dashscope.aliyuncs.com/compatible-mode/v1',
        default_max_tokens=16384,
        supports_vision=True,
    ),
    'openrouter': ProviderSpec(
        provider='openrouter', display_name='OpenRouter',
        protocol='openai',
        default_base_url='https://openrouter.ai/api/v1',
        default_max_tokens=4096,
    ),
}

# 厂商别名
PROVIDER_ALIASES = {
    'deepseek-chat': 'deepseek',
    'gpt': 'openai',
    'claude': 'anthropic',
    '通义千问': 'qwen',
    'dashscope': 'qwen',
}
```

### 3.3 统一客户端设计

```
LLMClient (ABC)
├── chat_completion(messages, **kwargs) → LLMResponse
├── chat_completion_stream(messages, **kwargs) → AsyncIterator[LLMChunk]
└── _build_headers() → dict
    _build_payload(messages, **kwargs) → dict
    _parse_response(raw) → LLMResponse

    ├── OpenAICompatibleClient
    │   ├── 适用于: DeepSeek, OpenAI, Qwen, OpenRouter, vLLM, Ollama
    │   └── 协议: POST /v1/chat/completions, Bearer token
    │
    ├── AnthropicClient
    │   ├── 适用于: Claude
    │   └── 协议: POST /v1/messages, x-api-key
    │
    └── [扩展点] 新厂商只需实现ABC的3个方法
```

### 3.4 Failover & 错误处理

借鉴Clawith的FailoverErrorType + Hermes的fallback链：

```python
class FailoverErrorType(Enum):
    RETRYABLE = auto()      # 网络超时/429/5xx → 重试或切fallback
    NON_RETRYABLE = auto()  # 401/403/400 → 直接报错,不重试
    UNKNOWN = auto()

class FailoverGuard:
    """Failover安全守卫"""
    def can_failover(self) -> bool:
        # 已执行过工具 → 禁止failover（防止状态不一致）
        # 已开始流式输出 → 禁止failover
        # 已failover过一次 → 禁止再次failover
```

**Failover策略**：

| 场景 | 行为 |
|------|------|
| 网络超时 | 重试3次，指数退避（2s→4s→8s）→ 仍失败则切fallback模型 |
| HTTP 429（限流） | 重试3次，指数退避 → 切fallback |
| HTTP 5xx | 重试3次 → 切fallback |
| HTTP 401/403 | 不重试，直接报"API Key无效" |
| HTTP 400（参数错误） | 不重试，直接报"请求参数错误" |
| 切fallback后仍失败 | 返回错误给调用方，触发降级策略（如正则回退） |

### 3.5 模块调用示例

#### 合同提取付款计划（当前问题修复 + 接入新服务）

```python
# crm/views.py → 修改后

from apps.core.ai_service import ai

class ContractViewSet(ViewSet):
    @action(detail=True, methods=['post'])
    def extract_payment_plans(self, request, pk=None):
        contract = self.get_object()

        # 1. OCR提取文本（不变）
        text = extract_text_from_pdf(contract.attachment.path)

        # 2. 用AI服务提取结构化数据 ← 改这里
        schema_prompt = """从以下合同文本中提取付款计划，
        返回JSON数组：[{plan_date, amount, percentage, condition}]
        金额必须是完整数字（如92400而非92.4）"""

        plans = ai.extract(
            text=text,
            schema=schema_prompt,
            model=None  # 使用当前活跃模型
        )

        return Response({'payment_plans': plans})
```

#### 其他模块调用示例

```python
# 银行流水智能匹配（finance模块）
from apps.core.ai_service import ai

class BankStatementViewSet(ViewSet):
    @action(detail=False, methods=['post'])
    def auto_match(self, request):
        statement = self.get_object()
        result = ai.analyze(
            prompt=f"""分析以下银行流水摘要，判断应该匹配到哪个收入/支出记录：
            银行摘要: {statement.description}
            金额: {statement.amount}
            日期: {statement.transaction_date}
            候选收入: {list(incomes)}
            候选支出: {list(expenses)}

            返回最匹配的ID和置信度。""",
            model='deepseek-chat'  # 显式指定模型
        )
```

```python
# 任务工时估算（tasks模块）
from apps.core.ai_service import ai

class TaskViewSet(ViewSet):
    @action(detail=True, methods=['get'])
    def estimate_hours(self, request, pk=None):
        task = self.get_object()
        estimation = ai.analyze(
            prompt=f"""根据任务描述估算工时：
            标题: {task.title}
            描述: {task.description}
            优先级: {task.priority}

            返回 {{"estimated_hours": number, "confidence": "high/medium/low", "reason": "..."}}""",
        )
```

```python
# 合同到期预警（定时任务）
from apps.core.ai_service import ai

# cron任务中调用
expiring_contracts = Contract.objects.filter(
    expire_date__gte=today,
    expire_date__lte=today + timedelta(days=30)
)
for contract in expiring_contracts:
    summary = ai.analyze(
        prompt=f"合同{contract.contract_no}将于{contract.expire_date}到期，"
               f"金额{contract.amount}元。请生成一个简洁的续约提醒，"
               f"包含合同关键信息和建议操作。",
    )
    send_notification(user, summary.content)
```

---

## 四、实施计划

### Phase 0 — 修复现有问题（30分钟）
- 修复去重bug：`extract_payment_plans` 去掉金额去重，改为(金额+日期+占比)全字段去重
- 先把3期问题修了，让当前功能能用

### Phase 1 — 建设AI服务层核心（2小时）
- 创建 `apps/core/ai_service/` 目录
  - `__init__.py` → AIService单例外观
  - `clients.py` → LLMClient抽象 + OpenAICompatibleClient + AnthropicClient
  - `registry.py` → ProviderSpec + PROVIDER_REGISTRY
  - `config.py` → 配置读取（SystemSetting + settings.py + 环境变量）
  - `error.py` → FailoverErrorType + FailoverGuard + classify_error
- 在 `config/settings/base.py` 添加 `AI_SERVICE` 配置
- 在 `SystemSetting` 表添加AI相关key

### Phase 2 — 迁移现有调用（1小时）
- `crm/views.py` 的DeepSeek调用 → 改用 `ai.extract()`
- 保留正则回退作为终极降级

### Phase 3 — 管理页面（1小时）
- 系统设置页面增加「AI模型」Tab
  - 模型列表（名称/厂商/状态/额度）
  - 活跃模型切换（下拉框）
  - API Key配置（加密存储）
  - 测试连接按钮

### Phase 4 — 逐步接入各模块（持续）
按优先级接入各场景：

| 优先级 | 模块 | 场景 | 预期收益 |
|--------|------|------|---------|
| P0 | crm | 合同付款计划提取 | ✅ 已部分实现，修复去重即可 |
| P1 | finance | 银行流水智能匹配 | 减少手工对账工作量80% |
| P1 | finance | 费用异常检测 | 及时发现异常支出 |
| P1 | tasks | 任务工时估算 | 提高排期准确性 |
| P2 | crm | 商机赢单预测 | 提高销售预测准确率 |
| P2 | material | 物料智能分类 | 减少手工分类工作量 |
| P2 | equipment | 设备故障预测 | 减少设备停机时间 |
| P3 | core | 审计日志分析 | 发现安全隐患 |
| P3 | approvals | 审批超时预警 | 提高审批效率 |

---

## 五、关键设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| API Key存储 | DB加密存储 + 环境变量覆盖 | DB存储方便页面管理，env变量方便运维 |
| 模型配置 | DB（SystemSetting）为主，settings.py为默认 | 用户可在页面直接切换模型，无需改代码重启 |
| Provider扩增 | 加ProviderSpec + 选客户端子类 | 无需改核心逻辑 |
| Failover策略 | 先重试后切换，tool执行后禁止failover | 防止状态不一致 |
| 结果缓存 | 默认关闭，按需开启 | ERP数据实时性要求高，缓存只用于纯分析场景 |
| 调用统计 | OperationAuditLog统一记录 | 复用现有审计体系，无需额外表 |
| 结构化输出 | Prompt驱动的JSON schema输出 | 不引入额外依赖，灵活度高 |

---

## 六、风险与注意事项

1. **API Key安全**：加密存储（Django AES），不写入代码库，不暴露在日志中
2. **成本控制**：每个模型可配每日/每月Token限额（参考Clawith的max_tokens_per_day）
3. **降级保障**：所有AI功能必须有纯规则/人工回退方案，AI是增强不是替代
4. **审计**：AI调用全部记录到OperationAuditLog，含请求/响应摘要、耗时、消耗Token
5. **隐私**：发送到外部API的数据不能包含敏感字段（密码、身份证号等），需脱敏
6. **响应时间**：AI调用通常3-30秒，前端需加loading状态，后端需加超时控制
