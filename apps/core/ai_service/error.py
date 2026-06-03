"""
Failover 错误处理
"""

import time
import logging

from .clients import LLMError, LLMErrorType

logger = logging.getLogger('ai_service')


class FailoverGuard:
    """Failover 安全守卫 — 确保副作用操作后不自动切换模型"""

    def __init__(self):
        self._has_tool_executed = False
        self._has_attempted_failover = False
        self._current_attempt = 0

    def mark_tool_executed(self):
        self._has_tool_executed = True

    @property
    def can_failover(self) -> bool:
        if self._has_tool_executed:
            logger.warning('[FailoverGuard] 已执行工具操作，禁止 failover')
            return False
        if self._has_attempted_failover:
            logger.warning('[FailoverGuard] 已 failover 过一次，禁止再次切换')
            return False
        return True

    def mark_failover_attempted(self):
        self._has_attempted_failover = True

    def increment_attempt(self):
        self._current_attempt += 1

    @property
    def current_attempt(self) -> int:
        return self._current_attempt


def retry_with_backoff(
    fn,
    max_retries: int = 3,
    base_delay: float = 2.0,
    guard: FailoverGuard | None = None,
) -> str:
    """
    带指数退避的重试 + Failover 策略

    返回: 成功时的 content string
    抛出: 最后一次失败的 LLMError
    """
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            if guard:
                guard.increment_attempt()
            return fn()
        except LLMError as e:
            last_error = e
            if e.is_retryable and attempt < max_retries:
                delay = base_delay * (2 ** (attempt - 1))
                logger.warning(f'[Retry] 第{attempt}次失败 ({e.error_type})，{delay}s后重试...')
                time.sleep(delay)
                continue
            elif not e.is_retryable:
                logger.warning(f'[Retry] 不可重试错误 ({e.error_type})，直接抛出不重试')
                raise
            else:
                # 已达最大重试次数
                logger.warning(f'[Retry] 已重试{max_retries}次仍失败，抛出最终错误')
                raise

    # 所有重试耗尽
    raise last_error or LLMError(LLMErrorType.UNKNOWN, '未知错误')
