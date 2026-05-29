"""请求耗时追踪中间件

功能：
1. 记录每个请求的处理耗时
2. 对超过阈值的慢请求输出告警日志
3. 提供 prometheus 风格的 metrics 端点（/api/core/metrics/）

使用方法：
在 MIDDLEWARE 中追加（放在最后，以包裹整个请求周期）：

    'apps.core.middleware_timing.RequestTimingMiddleware',

配置（base.py 或 .env）：

    SLOW_REQUEST_THRESHOLD_MS — 慢请求阈值，毫秒，默认 500
"""

import time
import logging
from collections import defaultdict
from threading import Lock

from django.conf import settings
from django.http import JsonResponse

logger = logging.getLogger(__name__)

# ── 线程安全的内存计数器 ───────────────────────────────────
_counter_lock = Lock()
_counter = {
    'total': 0,
    'by_endpoint': defaultdict(lambda: {'count': 0, 'total_ms': 0, 'slow': 0}),
    'slow_count': 0,
}


def _get_threshold():
    """获取慢请求阈值（毫秒），默认 500ms"""
    return getattr(settings, 'SLOW_REQUEST_THRESHOLD_MS', 500)


class RequestTimingMiddleware:
    """请求耗时中间件"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.perf_counter()
        response = self.get_response(request)
        duration_ms = (time.perf_counter() - start) * 1000

        # 跳过健康检查和 metrics 自身，避免递归
        skip_paths = ('/api/core/health/', '/api/core/metrics/')
        if request.path.startswith(skip_paths):
            return response

        threshold = _get_threshold()
        is_slow = duration_ms > threshold

        # 构建端点 key（带方法的路径）
        endpoint = f'{request.method} {request.path}'

        # 更新计数器
        with _counter_lock:
            _counter['total'] += 1
            _counter['by_endpoint'][endpoint]['count'] += 1
            _counter['by_endpoint'][endpoint]['total_ms'] += duration_ms
            if is_slow:
                _counter['by_endpoint'][endpoint]['slow'] += 1
                _counter['slow_count'] += 1

        if is_slow:
            logger.warning(
                'SLOW_REQUEST|%.0fms|%s %s',
                duration_ms,
                request.method,
                request.path,
            )

        return response


def metrics_view(request):
    """返回请求耗时统计数据（JSON）"""
    with _counter_lock:
        data = {
            'total_requests': _counter['total'],
            'slow_requests': _counter['slow_count'],
            'threshold_ms': _get_threshold(),
            'endpoints': {
                ep: {
                    'count': st['count'],
                    'avg_ms': round(st['total_ms'] / st['count'], 1) if st['count'] else 0,
                    'slow': st['slow'],
                }
                for ep, st in sorted(_counter['by_endpoint'].items())
            },
        }
    return JsonResponse(data)
