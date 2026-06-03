"""
统一 LLM 客户端抽象 + 多协议实现
"""

import json
import logging
from abc import ABC, abstractmethod
from typing import Any

import requests

logger = logging.getLogger('ai_service')


class LLMResponse:
    """标准化响应"""

    def __init__(self, content: str, model: str = '', usage: dict | None = None):
        self.content = content
        self.model = model
        self.usage = usage or {}

    def json(self) -> dict | list | Any:
        """尝试解析 content 为 JSON"""
        try:
            return json.loads(self.content)
        except json.JSONDecodeError:
            return self.content

    def __str__(self) -> str:
        return self.content


class LLMClient(ABC):
    """统一 LLM 客户端抽象基类"""

    def __init__(self, provider: str, api_key: str, base_url: str, **kwargs):
        self.provider = provider
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.model = kwargs.get('model', '')
        self.max_tokens = kwargs.get('max_tokens', 4096)
        self.timeout = kwargs.get('timeout', 120)
        self.session = requests.Session()

    @abstractmethod
    def chat_completion(self, messages: list[dict], **kwargs) -> LLMResponse:
        """同步非流式对话"""
        ...

    def _build_headers(self) -> dict:
        return {'Content-Type': 'application/json', 'Accept': 'application/json'}

    def _log_call(self, messages, response_text: str, duration: float):
        """记录调用日志"""
        last_msg = messages[-1]['content'][:100] if messages else ''
        logger.info(
            f'[AI] {self.provider}/{self.model} | '
            f'prompt="{last_msg}..." | '
            f'resp_len={len(response_text)} | '
            f'took={duration:.1f}s'
        )


class OpenAICompatibleClient(LLMClient):
    """
    适用于: DeepSeek, OpenAI, Qwen, OpenRouter, vLLM, Ollama, SiliconFlow
    协议: POST /v1/chat/completions, Bearer token
    """

    def _build_headers(self) -> dict:
        h = super()._build_headers()
        h['Authorization'] = f'Bearer {self.api_key}'
        return h

    def chat_completion(self, messages: list[dict], **kwargs) -> LLMResponse:
        import time

        t0 = time.time()
        payload = {
            'model': kwargs.get('model', self.model),
            'messages': messages,
            'max_tokens': kwargs.get('max_tokens', self.max_tokens),
            'temperature': kwargs.get('temperature', 0.7),
        }
        # 来自外层调用的额外参数
        for key in ('stream', 'response_format', 'top_p', 'stop'):
            if key in kwargs:
                payload[key] = kwargs[key]
        try:
            resp = self.session.post(
                f'{self.base_url}/chat/completions',
                headers=self._build_headers(),
                json=payload,
                timeout=kwargs.get('timeout', self.timeout),
            )
            resp.raise_for_status()
            data = resp.json()
            content = data['choices'][0]['message']['content']
            model = data.get('model', self.model)
            usage = data.get('usage', {})
            self._log_call(messages, content, time.time() - t0)
            return LLMResponse(content=content, model=model, usage=usage)
        except requests.exceptions.Timeout:
            raise LLMError(LLMErrorType.TIMEOUT, f'{self.provider}: 请求超时 ({self.timeout}s)')
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response else 0
            body = e.response.text[:200] if e.response else ''
            if status in (401, 403):
                raise LLMError(LLMErrorType.AUTH_ERROR, f'{self.provider}: API Key 无效 ({status})')
            elif status == 429:
                raise LLMError(LLMErrorType.RATE_LIMIT, f'{self.provider}: 限流 ({body})')
            elif status >= 500:
                raise LLMError(LLMErrorType.SERVER_ERROR, f'{self.provider}: 服务端错误 ({status} {body})')
            else:
                raise LLMError(LLMErrorType.UNKNOWN, f'{self.provider}: HTTP {status} {body}')
        except requests.exceptions.ConnectionError:
            raise LLMError(LLMErrorType.NETWORK_ERROR, f'{self.provider}: 网络连接失败')
        except Exception as e:
            raise LLMError(LLMErrorType.UNKNOWN, f'{self.provider}: {str(e)}')


class AnthropicClient(LLMClient):
    """
    适用于: Claude
    协议: POST /v1/messages, x-api-key
    """

    def _build_headers(self) -> dict:
        h = super()._build_headers()
        h['x-api-key'] = self.api_key
        h['anthropic-version'] = '2023-06-01'
        return h

    def chat_completion(self, messages: list[dict], **kwargs) -> LLMResponse:
        import time

        t0 = time.time()

        # Anthropic 消息格式: system + messages
        system = None
        chat_messages = messages
        if messages and messages[0].get('role') == 'system':
            system = messages[0]['content']
            chat_messages = messages[1:]

        payload = {
            'model': kwargs.get('model', self.model),
            'messages': chat_messages,
            'max_tokens': kwargs.get('max_tokens', self.max_tokens),
        }
        if system:
            payload['system'] = system
        if 'temperature' in kwargs:
            payload['temperature'] = kwargs['temperature']
        try:
            resp = self.session.post(
                f'{self.base_url}/v1/messages',
                headers=self._build_headers(),
                json=payload,
                timeout=kwargs.get('timeout', self.timeout),
            )
            resp.raise_for_status()
            data = resp.json()
            content = '\n'.join(b['text'] for b in data.get('content', []) if b.get('type') == 'text')
            model = data.get('model', self.model)
            usage = data.get('usage', {})
            self._log_call(messages, content, time.time() - t0)
            return LLMResponse(content=content, model=model, usage=usage)
        except requests.exceptions.Timeout:
            raise LLMError(LLMErrorType.TIMEOUT, f'{self.provider}: 请求超时')
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response else 0
            body = e.response.text[:200] if e.response else ''
            if status in (401, 403):
                raise LLMError(LLMErrorType.AUTH_ERROR, f'{self.provider}: API Key 无效')
            elif status == 429:
                raise LLMError(LLMErrorType.RATE_LIMIT, f'{self.provider}: 限流')
            elif status >= 500:
                raise LLMError(LLMErrorType.SERVER_ERROR, f'{self.provider}: 服务端错误')
            else:
                raise LLMError(LLMErrorType.UNKNOWN, f'{self.provider}: HTTP {status} {body}')
        except requests.exceptions.ConnectionError:
            raise LLMError(LLMErrorType.NETWORK_ERROR, f'{self.provider}: 网络连接失败')
        except Exception as e:
            raise LLMError(LLMErrorType.UNKNOWN, f'{self.provider}: {str(e)}')


# ── 错误体系 ─────────────────────────────────────────────


class LLMErrorType:
    TIMEOUT = 'timeout'
    RATE_LIMIT = 'rate_limit'
    SERVER_ERROR = 'server_error'
    AUTH_ERROR = 'auth_error'
    NETWORK_ERROR = 'network_error'
    UNKNOWN = 'unknown'
    NON_RETRYABLE = 'non_retryable'


RETRYABLE_ERRORS = {
    LLMErrorType.TIMEOUT,
    LLMErrorType.RATE_LIMIT,
    LLMErrorType.SERVER_ERROR,
    LLMErrorType.NETWORK_ERROR,
}


class LLMError(Exception):
    def __init__(self, error_type: str, message: str = ''):
        self.error_type = error_type
        self.message = message
        super().__init__(f'[{error_type}] {message}')

    @property
    def is_retryable(self) -> bool:
        return self.error_type in RETRYABLE_ERRORS


# ── 工厂函数 ─────────────────────────────────────────────


def create_client(provider: str, api_key: str, base_url: str | None = None, **kwargs) -> LLMClient:
    """创建对应的 LLM 客户端实例"""
    from .registry import PROVIDER_REGISTRY, resolve_provider

    provider = resolve_provider(provider)
    spec = PROVIDER_REGISTRY[provider]

    base = base_url or spec.default_base_url
    if not base:
        raise ValueError(f'Provider {provider} 没有默认 base_url，需显式提供')

    if spec.protocol == 'anthropic':
        return AnthropicClient(provider=provider, api_key=api_key, base_url=base, **kwargs)
    else:
        return OpenAICompatibleClient(provider=provider, api_key=api_key, base_url=base, **kwargs)
