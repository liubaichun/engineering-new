from django.http import JsonResponse
from django.db import connection


def health_check(request):
    """健康检查：验证数据库连接，返回服务状态"""
    try:
        connection.ensure_connection()
        return JsonResponse({'status': 'ok', 'database': 'connected'}, status=200)
    except Exception as e:
        return JsonResponse({'status': 'error', 'database': str(e)}, status=503)
