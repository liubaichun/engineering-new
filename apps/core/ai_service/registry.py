"""
Provider 注册表

定义 ProviderSpec dataclass 和 PROVIDER_REGISTRY 内建厂商注册表。
"""

from dataclasses import dataclass, field
from typing import Literal, Optional


@dataclass
class ProviderSpec:
    """Provider 注册信息"""

    provider: str  # 标识名: deepseek, openai, anthropic
    display_name: str  # 显示名: DeepSeek, OpenAI, Anthropic Claude
    protocol: Literal['openai', 'anthropic']  # 协议类型
    default_base_url: Optional[str] = None  # 默认API端点
    default_max_tokens: int = 4096
    supports_vision: bool = False
    supports_streaming: bool = True


# ── 内建 Provider 注册表 ────────────────────────────────

PROVIDER_REGISTRY: dict[str, ProviderSpec] = {
    'deepseek': ProviderSpec(
        provider='deepseek',
        display_name='DeepSeek',
        protocol='openai',
        default_base_url='https://api.deepseek.com/v1',
        default_max_tokens=8192,
    ),
    'openai': ProviderSpec(
        provider='openai',
        display_name='OpenAI',
        protocol='openai',
        default_base_url='https://api.openai.com/v1',
        default_max_tokens=16384,
        supports_vision=True,
    ),
    'anthropic': ProviderSpec(
        provider='anthropic',
        display_name='Anthropic Claude',
        protocol='anthropic',
        default_base_url='https://api.anthropic.com',
        default_max_tokens=8192,
        supports_vision=True,
    ),
    'qwen': ProviderSpec(
        provider='qwen',
        display_name='通义千问',
        protocol='openai',
        default_base_url='https://dashscope.aliyuncs.com/compatible-mode/v1',
        default_max_tokens=16384,
        supports_vision=True,
    ),
    'openrouter': ProviderSpec(
        provider='openrouter',
        display_name='OpenRouter',
        protocol='openai',
        default_base_url='https://openrouter.ai/api/v1',
        default_max_tokens=4096,
    ),
}

# 厂商别名（兼容不同写法）
PROVIDER_ALIASES: dict[str, str] = {
    'deepseek-chat': 'deepseek',
    'gpt': 'openai',
    'claude': 'anthropic',
    '通义千问': 'qwen',
    'dashscope': 'qwen',
    'siliconflow': 'openai',
}


def resolve_provider(name: str) -> str:
    """根据模型名或provider名解析为标准provider名称"""
    name = name.lower().strip()
    if name in PROVIDER_REGISTRY:
        return name
    resolved = PROVIDER_ALIASES.get(name)
    if resolved:
        return resolved
    # 尝试从 AI_SERVICE.models 查找
    try:
        from django.conf import settings
        for model_key, model_cfg in settings.AI_SERVICE['models'].items():
            if model_key == name or model_cfg.get('provider', '').lower() == name:
                return model_cfg['provider']
    except Exception:
        pass
    raise ValueError(f'未知 provider: {name}')
