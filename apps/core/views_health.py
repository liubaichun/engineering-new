"""健康检查端点 — 验证系统依赖和服务状态"""

import os
import shutil

from django.http import JsonResponse
from django.db import connection
from django.conf import settings


def health_check(request):
    """健康检查：验证数据库 + 磁盘 + 整体状态"""
    result = {'status': 'ok', 'checks': {}}
    http_status = 200

    # 1. 数据库连接
    db_ok = False
    try:
        connection.ensure_connection()
        db_ok = True
        result['checks']['database'] = 'connected'
    except Exception as e:
        result['checks']['database'] = str(e)
        http_status = 503

    # 2. 磁盘空间
    media_root = getattr(settings, 'MEDIA_ROOT', None)
    if media_root and os.path.exists(media_root):
        try:
            usage = shutil.disk_usage(media_root)
            free_gb = usage.free / (1024**3)
            result['checks']['disk_free_gb'] = round(free_gb, 1)
            if free_gb < 1:
                result['status'] = 'degraded'
                http_status = 503
        except OSError:
            pass

    # 3. 整体状态
    result['status'] = 'ok' if http_status == 200 else 'degraded'

    return JsonResponse(result, status=http_status)
