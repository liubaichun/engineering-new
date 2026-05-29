"""
统一错误码与异常处理系统

遵循 docs/质量安全与认证合规规范.md 4.3 节定义的错误码体系。

标准响应格式：
    {
        "code": 2001,
        "message": "输入参数校验失败",
        "detail": { ... }         # 可选，字段级错误信息
    }

错误码范围：
    0:          成功
    1000-1099:  认证授权
    1100-1199:  租户相关
    1200-1299:  数据隔离
    2000-2999:  业务逻辑
    5000:       服务器内部错误
"""

from __future__ import annotations

from typing import Any, Optional

from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework.response import Response
from rest_framework import status as http_status
from django.http import Http404
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
import logging

logger = logging.getLogger(__name__)

# ── 错误码常量 ────────────────────────────────────────


class ErrorCode:
    """统一错误码常量"""

    # 通用成功
    SUCCESS = 0

    # 1000-1099: 认证授权
    NOT_LOGGED_IN = 1001  # 未登录 → 401
    TOKEN_EXPIRED = 1002  # Token已过期 → 401
    TOKEN_INVALID = 1003  # Token无效 → 401
    PERMISSION_DENIED = 1004  # 权限不足 → 403
    ACCOUNT_LOCKED = 1005  # 账号已锁定 → 403
    PASSWORD_EXPIRED = 1006  # 密码已过期 → 403

    # 1100-1199: 租户相关
    TENANT_NOT_FOUND = 1101  # 租户不存在
    TENANT_DISABLED = 1102  # 租户已停用
    TENANT_OVER_LIMIT = 1103  # 租户用量超限

    # 1200-1299: 数据隔离
    CROSS_TENANT_BLOCKED = 1201  # 跨租户访问被阻止
    DATA_PERMISSION_DENIED = 1202  # 数据权限不足

    # 2000-2999: 业务逻辑
    VALIDATION_ERROR = 2001  # 输入参数校验失败 → 400
    NOT_FOUND = 2002  # 资源不存在 → 404
    ALREADY_EXISTS = 2003  # 资源已存在（重复）→ 409
    INVALID_STATE = 2004  # 状态不允许当前操作 → 400
    DEPENDENCY_BLOCKED = 2005  # 操作被依赖资源阻止 → 409

    # 5000: 服务器内部错误
    INTERNAL_ERROR = 5000  # 服务器内部错误 → 500


# ── 自定义异常类 ──────────────────────────────────────


class AppException(Exception):
    """应用级异常基类，携带错误码和详情"""

    default_code = ErrorCode.VALIDATION_ERROR
    default_message = '操作失败'
    default_http_status = http_status.HTTP_400_BAD_REQUEST

    def __init__(
        self,
        message: Optional[str] = None,
        code: Optional[int] = None,
        detail: Any = None,
        http_status_code: Optional[int] = None,
    ) -> None:
        self.code = code or self.default_code
        self.message = message or self.default_message
        self.detail = detail
        self.http_status_code = http_status_code or self.default_http_status
        super().__init__(self.message)


class BadRequest(AppException):
    default_code = ErrorCode.VALIDATION_ERROR
    default_message = '请求参数错误'
    default_http_status = http_status.HTTP_400_BAD_REQUEST


class NotFound(AppException):
    default_code = ErrorCode.NOT_FOUND
    default_message = '资源不存在'
    default_http_status = http_status.HTTP_404_NOT_FOUND


class PermissionDenied(AppException):
    default_code = ErrorCode.PERMISSION_DENIED
    default_message = '权限不足'
    default_http_status = http_status.HTTP_403_FORBIDDEN


class InvalidState(AppException):
    default_code = ErrorCode.INVALID_STATE
    default_message = '当前状态不允许该操作'
    default_http_status = http_status.HTTP_400_BAD_REQUEST


class AlreadyExists(AppException):
    default_code = ErrorCode.ALREADY_EXISTS
    default_message = '资源已存在'
    default_http_status = http_status.HTTP_409_CONFLICT


class InternalError(AppException):
    default_code = ErrorCode.INTERNAL_ERROR
    default_message = '服务器内部错误'
    default_http_status = http_status.HTTP_500_INTERNAL_SERVER_ERROR


# ── 视图层错误响应辅助函数 ───────────────────────────


def api_error(
    code: int,
    message: str,
    detail: Any = None,
    status_code: int = http_status.HTTP_400_BAD_REQUEST,
) -> Response:
    """
    视图函数中使用的快捷函数，返回统一格式的错误 Response。

    用法：
        return api_error(ErrorCode.INVALID_STATE, '当前状态不允许提交')
        return api_error(2004, '库存不足')
    """
    body = {'code': code, 'message': message}
    if detail is not None:
        body['detail'] = detail
    return Response(body, status=status_code)


def api_validation_error(message: str, detail: Any = None) -> Response:
    """校验失败的快捷方式"""
    return api_error(ErrorCode.VALIDATION_ERROR, message, detail, status_code=http_status.HTTP_400_BAD_REQUEST)


def api_not_found(message: str = '资源不存在') -> Response:
    """资源不存在的快捷方式"""
    return api_error(ErrorCode.NOT_FOUND, message, status_code=http_status.HTTP_404_NOT_FOUND)


def api_permission_denied(message: str = '权限不足') -> Response:
    """权限不足的快捷方式"""
    return api_error(ErrorCode.PERMISSION_DENIED, message, status_code=http_status.HTTP_403_FORBIDDEN)


def api_server_error(message: str = '服务器内部错误') -> Response:
    """服务器错误的快捷方式"""
    return api_error(ErrorCode.INTERNAL_ERROR, message, status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR)


# ── DRF 统一异常处理器 ───────────────────────────────


def unified_exception_handler(exc: Exception, context: dict) -> Optional[Response]:
    """
    替换 DEFAULT_EXCEPTION_HANDLER，捕获所有异常并统一格式。
    注册到 settings: 'EXCEPTION_HANDLER': 'apps.core.exceptions.unified_exception_handler'
    """
    # ── AppException（自定义异常） ──
    if isinstance(exc, AppException):
        body = {'code': exc.code, 'message': exc.message}
        if exc.detail is not None:
            body['detail'] = exc.detail
        logger.warning('AppException: code=%s message=%s detail=%s', exc.code, exc.message, exc.detail)
        return Response(body, status=exc.http_status_code)

    # ── Django Http404 ──
    if isinstance(exc, Http404):
        return Response({'code': ErrorCode.NOT_FOUND, 'message': str(exc)}, status=http_status.HTTP_404_NOT_FOUND)

    # ── Django PermissionDenied ──
    if isinstance(exc, DjangoPermissionDenied):
        return Response(
            {'code': ErrorCode.PERMISSION_DENIED, 'message': '权限不足'}, status=http_status.HTTP_403_FORBIDDEN
        )

    # ── DRF 原生异常处理 ──
    response = drf_exception_handler(exc, context)
    if response is not None:
        data = response.data

        # 如果是 serializer.errors 的字段级校验
        if isinstance(data, dict) and any(isinstance(v, list) for v in data.values()):
            flat_messages = []
            detail = {}
            for field, msgs in data.items():
                if isinstance(msgs, list):
                    flat_messages.extend(str(m) for m in msgs)
                    detail[field] = [str(m) for m in msgs]
                else:
                    flat_messages.append(str(msgs))
            message = flat_messages[0] if flat_messages else '校验失败'
            return Response(
                {'code': ErrorCode.VALIDATION_ERROR, 'message': message, 'detail': detail}, status=response.status_code
            )

        # 普通 DRF 异常（AuthenticationFailed, NotAuthenticated 等）
        if isinstance(data, dict):
            message = data.get('detail', str(data))
            if isinstance(message, list):
                message = message[0]
            code = ErrorCode.VALIDATION_ERROR
            status_int = response.status_code
            if status_int == 401:
                code = ErrorCode.NOT_LOGGED_IN
            elif status_int == 403:
                code = ErrorCode.PERMISSION_DENIED
            elif status_int == 404:
                code = ErrorCode.NOT_FOUND
            elif status_int == 409:
                code = ErrorCode.ALREADY_EXISTS
            elif status_int == 500:
                code = ErrorCode.INTERNAL_ERROR
            return Response({'code': code, 'message': str(message)}, status=status_int)

        return response

    # ── 未捕获异常（500） ──
    logger.exception('Unhandled exception: %s', exc)
    return Response(
        {'code': ErrorCode.INTERNAL_ERROR, 'message': '服务器内部错误'},
        status=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
