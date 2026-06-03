"""
AIService 单例外观 — 各模块的统一入口
"""

import json
import logging
import time

from django.conf import settings

from .config import get_model_config, get_available_models, get_config
from .clients import create_client, LLMError, LLMResponse
from .error import retry_with_backoff, FailoverGuard

logger = logging.getLogger('ai_service')


class AIService:
    """AI 服务单例外观"""

    def __init__(self):
        self._client_cache: dict[str, object] = {}  # provider: client

    def _get_client(self, model_key: str | None = None):
        """获取客户端（带缓存）"""
        cfg = get_model_config(model_key)
        cache_key = cfg['model_key']
        if cache_key in self._client_cache:
            return self._client_cache[cache_key]

        client = create_client(
            provider=cfg['provider'],
            api_key=cfg['api_key'],
            base_url=cfg.get('base_url'),
            model=cfg['model'],
            max_tokens=cfg.get('max_tokens', 4096),
            timeout=settings.AI_SERVICE.get('request_timeout', 120),
        )
        self._client_cache[cache_key] = client
        return client

    def _call(self, model: str | None, messages: list[dict], **kwargs) -> LLMResponse:
        """统一的 LLM 调用入口"""
        max_retries = kwargs.pop('max_retries', settings.AI_SERVICE.get('max_retries', 3))
        guard = FailoverGuard()

        def do_call():
            client = self._get_client(model)
            return client.chat_completion(messages, **kwargs)

        return retry_with_backoff(do_call, max_retries=max_retries, guard=guard)

    # ── 模块对外接口 ──────────────────────────────────────

    def chat(self, model: str | None = None, system: str | None = None,
             messages: list[dict] | None = None, **kwargs) -> LLMResponse:
        """通用对话"""
        if messages is None:
            messages = []
        if system:
            messages = [{'role': 'system', 'content': system}] + messages
        return self._call(model, messages, **kwargs)

    def extract(self, model: str | None = None, text: str = '',
                schema: str = '', **kwargs) -> list | dict | str:
        """结构化提取 — 从文本中提取 JSON 数据"""
        prompt = f'{text}\n\n请根据以下要求提取结构化数据：\n{schema}\n\n只返回 JSON 格式结果，不要附加说明。'
        resp = self._call(model, [{'role': 'user', 'content': prompt}], **kwargs)
        return resp.json()

    def analyze(self, model: str | None = None, prompt: str = '',
                **kwargs) -> LLMResponse:
        """分析推理"""
        return self._call(model, [{'role': 'user', 'content': prompt}], **kwargs)

    def classify(self, model: str | None = None, text: str = '',
                 categories: list[str] | None = None, **kwargs) -> str:
        """智能分类"""
        cats = ', '.join(categories) if categories else ''
        prompt = (
            f'对以下内容进行分类，只能从以下类别中选择一个：{cats}\n\n'
            f'内容：{text}\n\n只返回类别名称，不要附加说明。'
        )
        resp = self._call(model, [{'role': 'user', 'content': prompt}], **kwargs)
        return resp.content.strip()

    def summarize(self, model: str | None = None, text: str = '',
                  max_length: int = 200, **kwargs) -> str:
        """文本摘要"""
        prompt = f'请用中文对以下内容进行摘要，不超过{max_length}字：\n\n{text}'
        resp = self._call(model, [{'role': 'user', 'content': prompt}], **kwargs)
        return resp.content.strip()

    # ── 模型管理 ─────────────────────────────────────────

    def switch_model(self, model_key: str):
        """运行时切换模型"""
        from apps.core.models import SystemSetting
        SystemSetting.objects.update_or_create(
            key='ai_active_model',
            defaults={'value': json.dumps({'model': model_key}, ensure_ascii=False)},
        )
        self._client_cache.clear()
        logger.info(f'[AIService] 切换模型至: {model_key}')

    def get_current_model(self) -> dict:
        """获取当前活跃模型信息"""
        cfg = get_model_config()
        return cfg

    def get_available_models(self) -> list[dict]:
        """列出可用模型"""
        return get_available_models()
