"""
AI 服务配置管理

配置优先级: SystemSetting 表 > settings.py > 环境变量
"""

import os
import json
import logging

from django.conf import settings

logger = logging.getLogger('ai_service')


def get_config(key: str, default=None):
    """
    从 SystemSetting 表读取配置，不存在则返回 settings.py 默认值
    """
    try:
        from apps.core.models import SystemSetting
        val = SystemSetting.get_value(key)
        if val is not None:
            return val
    except Exception:
        pass
    # fallback 到 settings.py
    ai_conf = getattr(settings, 'AI_SERVICE', {})
    return ai_conf.get(key, default)


def get_model_config(model_key: str | None = None) -> dict:
    """获取模型配置（含 API Key）"""
    ai_conf = getattr(settings, 'AI_SERVICE', {})
    models = ai_conf.get('models', {})
    api_key_sources = ai_conf.get('api_key_sources', {})

    if model_key:
        model_cfg = models.get(model_key)
        if not model_cfg:
            raise ValueError(f'未知模型: {model_key}')
    else:
        # 使用活跃模型
        active = get_config('ai_active_model', ai_conf.get('active_model', 'deepseek-chat'))
        if isinstance(active, str):
            try:
                active = json.loads(active)
            except (json.JSONDecodeError, TypeError):
                pass
        if isinstance(active, dict):
            model_key = active.get('model', 'deepseek-chat')
        else:
            model_key = active
        model_cfg = models.get(model_key)
        if not model_cfg:
            logger.warning(f'活跃模型 "{model_key}" 未在配置中，使用 deepseek-chat 兜底')
            model_key = 'deepseek-chat'
            model_cfg = models.get(model_key)

    provider = model_cfg['provider']
    # 尝试 DB 中存储的 Key，再尝试环境变量
    api_key = None
    try:
        from apps.core.models import SystemSetting
        db_cfg = SystemSetting.get_value('ai_model_configs')
        if db_cfg:
            configs = json.loads(db_cfg) if isinstance(db_cfg, str) else db_cfg
            if model_key in configs and configs[model_key].get('api_key'):
                api_key = configs[model_key]['api_key']
    except Exception:
        pass

    if not api_key:
        env_var = api_key_sources.get(provider)
        if env_var:
            api_key = os.environ.get(env_var)

    if not api_key:
        logger.warning(f'[{model_key}] 未找到 API Key')

    return {
        'model_key': model_key,
        'provider': provider,
        'model': model_cfg.get('model', model_key),
        'api_key': api_key,
        'base_url': model_cfg.get('base_url'),
        'max_tokens': model_cfg.get('max_tokens', 4096),
        'supports_vision': model_cfg.get('supports_vision', False),
    }


def get_available_models() -> list[dict]:
    """获取所有可用模型列表"""
    ai_conf = getattr(settings, 'AI_SERVICE', {})
    models = ai_conf.get('models', {})
    result = []
    for key, cfg in models.items():
        result.append({
            'key': key,
            'provider': cfg.get('provider'),
            'display_name': cfg.get('display_name'),
            'model': cfg.get('model'),
            'supports_vision': cfg.get('supports_vision', False),
        })
    return result
