"""
统一权限管理系统 - 基于UMP表（位掩码）

本模块替代原来的两套权限系统（UMP+UCP），统一使用UMP表
进行权限检查和数据过滤。

核心设计：
1. 所有权限检查和数据过滤都使用UMP表
2. 位掩码压缩存储，高效查询
3. 模块自动注册机制

使用方式：
    from apps.core.permissions_unified import (
        get_user_companies,        # 获取用户有权限的公司列表
        check_permission,          # 检查权限
        get_module_companies,     # 获取用户在指定模块有权限的公司
        RoleRequired,             # DRF权限类
    )
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple

from django.http import JsonResponse
from rest_framework.permissions import BasePermission
from rest_framework.request import Request

# ============================================================
# 权限位掩码定义
# ============================================================

ACTION_BITS: Dict[str, int] = {
    'read':    0b0000000000000001,   # bit 0
    'create':  0b0000000000000010,   # bit 1
    'update':  0b0000000000000100,   # bit 2
    'delete':  0b0000000000001000,   # bit 3
    'approve': 0b0000000000010000,   # bit 4
    'submit':  0b0000000000100000,   # bit 5
    'pay':     0b0000000001000000,   # bit 6
    'export':  0b0000000010000000,   # bit 7
    'import':  0b0000000100000000,   # bit 8
    'use':     0b0000001000000000,   # bit 9
    'return':  0b0000010000000000,   # bit 10
    'repair':  0b0000100000000000,   # bit 11
    'manage':  0b0001000000000000,   # bit 12
    'reject':  0b0010000000000000,   # bit 13
    '_reserved': 0b0100000000000000, # bit 14
    '_admin':  0b1000000000000000,   # bit 15
}

# DRF标准action自动映射
STANDARD_ACTION_MAP: Dict[str, str] = {
    'list': 'read',
    'retrieve': 'read',
    'create': 'create',
    'update': 'update',
    'partial_update': 'update',
    'destroy': 'delete',
}


# ============================================================
# 核心函数
# ============================================================

def get_user_companies(user: Any) -> Optional[List[int]]:
    """
    获取用户有权限的所有公司ID列表（基于UMP表）
    
    这是统一权限系统的核心函数，所有API数据过滤都使用此函数。
    
    参数：
        user: User对象
        
    返回：
        None: 超级用户，不限制公司（可见所有公司数据）
        []: 无权限用户（不可见任何公司数据）
        [company_id, ...]: 有权限的公司列表
        
    示例：
        cids = get_user_companies(request.user)
        if cids is not None:
            queryset = queryset.filter(company_id__in=cids)
    """
    if not user or not user.is_authenticated:
        return []
    
    if user.is_superuser:
        return None  # 超级用户不限制公司
    
    from apps.core.models import UserModulePermission
    
    cids = list(
        UserModulePermission.objects.filter(user=user)
        .values_list('company_id', flat=True)
        .distinct()
    )
    
    return cids if cids else []


def get_module_companies(user: Any, module_name: str, action: str = 'read') -> Optional[List[int]]:
    """
    获取用户在指定模块有指定动作权限的公司ID列表
    
    参数：
        user: User对象
        module_name: 模块名（如'income', 'expense', 'wage'）
        action: 动作名（如'read', 'create', 'update'）
        
    返回：
        None: 超级用户，不限制公司
        []: 无权限或模块不存在
        [company_id, ...]: 有权限的公司列表
        
    示例：
        cids = get_module_companies(request.user, 'income', 'read')
    """
    if not user or not user.is_authenticated:
        return []
    
    if user.is_superuser:
        return None  # 超级用户不限制
    
    bit = ACTION_BITS.get(action)
    if not bit:
        return []
    
    from apps.core.models import UserModulePermission
    
    cids = list(
        UserModulePermission.objects.filter(
            user=user,
            module__name=module_name,
        )
        .extra(where=['granted_bits & %s = %s'], params=[bit, bit])
        .values_list('company_id', flat=True)
        .distinct()
    )
    
    return cids if cids else []


def check_permission(user: Any, module_name: str, action: str) -> bool:
    """
    检查用户是否有指定模块的指定动作权限
    
    参数：
        user: User对象
        module_name: 模块名
        action: 动作名
        
    返回：
        True: 有权限
        False: 无权限
        
    示例：
        if check_permission(request.user, 'income', 'create'):
            # 允许创建收入
            pass
    """
    if not user or not user.is_authenticated:
        return False
    
    if user.is_superuser:
        return True  # 超级用户有所有权限
    
    bit = ACTION_BITS.get(action)
    if not bit:
        return False
    
    from apps.core.models import UserModulePermission
    
    return UserModulePermission.objects.filter(
        user=user,
        module__name=module_name,
    ).extra(
        where=['granted_bits & %s = %s'],
        params=[bit, bit]
    ).exists()


def check_any_permission(user: Any, permissions: List[Tuple[str, str]]) -> bool:
    """
    检查用户是否拥有指定列表中的任意一个权限
    
    参数：
        user: User对象
        permissions: 权限列表 [(module, action), ...]
        
    返回：
        True: 拥有任意一个权限
        False: 无任何权限
    """
    if not user or not user.is_authenticated:
        return False
    
    if user.is_superuser:
        return True
    
    for module_name, action in permissions:
        if check_permission(user, module_name, action):
            return True
    
    return False


def check_all_permissions(user: Any, permissions: List[Tuple[str, str]]) -> bool:
    """
    检查用户是否拥有指定列表中的所有权限
    
    参数：
        user: User对象
        permissions: 权限列表 [(module, action), ...]
        
    返回：
        True: 拥有所有权限
        False: 缺少任意一个权限
    """
    if not user or not user.is_authenticated:
        return False
    
    if user.is_superuser:
        return True
    
    for module_name, action in permissions:
        if not check_permission(user, module_name, action):
            return False
    
    return True


# ============================================================
# DRF权限类
# ============================================================

class RoleRequired(BasePermission):
    """
    基于UMP表的权限检查类
    
    使用方式：
        class MyViewSet(viewsets.ModelViewSet):
            permission_classes = [IsAuthenticated, RoleRequired]
            required_permissions = [
                ('income', 'read'),
                ('income', 'create'),
            ]
    
    也可以通过action_perms自动映射：
        class MyViewSet(viewsets.ModelViewSet):
            permission_classes = [IsAuthenticated, RoleRequired]
            action_perms = {
                'list': [('income', 'read')],
                'create': [('income', 'create')],
                None: [('income', 'read')],  # 默认权限
            }
    """
    
    _standard_actions: FrozenSet[str] = frozenset(STANDARD_ACTION_MAP.keys())
    
    def has_permission(self, request: Request, view: Any) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False
        
        user = request.user
        
        # 超级用户bypass
        if user.is_superuser:
            return True
        
        # 获取所需权限
        required_perms = self._get_required_permissions(view, request)
        
        if not required_perms:
            return True  # 无需权限
        
        # 检查权限
        return check_all_permissions(user, required_perms)
    
    def _get_required_permissions(self, view: Any, request: Request) -> List[Tuple[str, str]]:
        """
        获取视图所需的权限列表
        """
        # 优先使用 action_perms
        action_perms = getattr(view, 'action_perms', None)
        if action_perms:
            action = getattr(request, 'action', 'list')
            perms = action_perms.get(action) or action_perms.get(None, [])
            return perms
        
        # 其次使用 required_permissions
        required_perms = getattr(view, 'required_permissions', None)
        if required_perms:
            return required_perms
        
        # 默认：无权限要求
        return []


def require_permissions(*required_perms):
    """
    视图函数权限装饰器
    
    使用方式：
        @require_permissions(('income', 'read'), ('income', 'create'))
        def my_view(request):
            pass
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user or not request.user.is_authenticated:
                return JsonResponse({'code': 401, 'message': '未登录'}, status=401)
            
            if not check_all_permissions(request.user, list(required_perms)):
                return JsonResponse({'code': 403, 'message': '权限不足'}, status=403)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


# ============================================================
# 辅助函数
# ============================================================

def get_user_permissions_detail(user: Any) -> Dict[str, Any]:
    """
    获取用户权限详情（用于调试和权限矩阵显示）
    
    返回：
        {
            'user_id': 1,
            'username': 'admin',
            'is_superuser': True,
            'companies': {
                1: {'income': 'rwd', 'expense': 'rwd'},
                2: {'income': 'r'},
            }
        }
    """
    if not user or not user.is_authenticated:
        return {'error': 'user not authenticated'}
    
    from apps.core.models import UserModulePermission
    from apps.finance.models_company import Company
    
    result = {
        'user_id': user.id,
        'username': user.username,
        'is_superuser': user.is_superuser,
        'companies': {},
    }
    
    if user.is_superuser:
        result['is_superuser'] = True
        return result
    
    umps = UserModulePermission.objects.filter(user=user).select_related('module', 'company')
    
    for ump in umps:
        company_id = ump.company_id
        module_name = ump.module.name
        
        if company_id not in result['companies']:
            result['companies'][company_id] = {
                'company_name': ump.company.name,
                'modules': {},
            }
        
        # 解码位掩码
        bits_str = decode_bits_to_string(ump.granted_bits)
        result['companies'][company_id]['modules'][module_name] = bits_str
    
    return result


def decode_bits_to_string(bits: int) -> str:
    """
    将位掩码解码为权限字符串
    
    例如：bits=15 (0x000f) -> 'rwd'
    """
    result = []
    if bits & ACTION_BITS.get('read', 0):
        result.append('r')
    if bits & ACTION_BITS.get('create', 0):
        result.append('c')
    if bits & ACTION_BITS.get('update', 0):
        result.append('u')
    if bits & ACTION_BITS.get('delete', 0):
        result.append('d')
    if bits & ACTION_BITS.get('approve', 0):
        result.append('a')
    if bits & ACTION_BITS.get('submit', 0):
        result.append('s')
    if bits & ACTION_BITS.get('pay', 0):
        result.append('p')
    if bits & ACTION_BITS.get('export', 0):
        result.append('e')
    if bits & ACTION_BITS.get('import', 0):
        result.append('i')
    
    return ''.join(result) if result else '-'


def encode_string_to_bits(s: str) -> int:
    """
    将权限字符串编码为位掩码
    
    例如：'rwd' -> 15 (0x000f)
    """
    bits = 0
    if 'r' in s:
        bits |= ACTION_BITS.get('read', 0)
    if 'c' in s:
        bits |= ACTION_BITS.get('create', 0)
    if 'u' in s:
        bits |= ACTION_BITS.get('update', 0)
    if 'd' in s:
        bits |= ACTION_BITS.get('delete', 0)
    if 'a' in s:
        bits |= ACTION_BITS.get('approve', 0)
    if 's' in s:
        bits |= ACTION_BITS.get('submit', 0)
    if 'p' in s:
        bits |= ACTION_BITS.get('pay', 0)
    if 'e' in s:
        bits |= ACTION_BITS.get('export', 0)
    if 'i' in s:
        bits |= ACTION_BITS.get('import', 0)
    
    return bits


# ============================================================
# 导出
# ============================================================

__all__ = [
    'ACTION_BITS',
    'STANDARD_ACTION_MAP',
    'get_user_companies',
    'get_module_companies',
    'check_permission',
    'check_any_permission',
    'check_all_permissions',
    'RoleRequired',
    'require_permissions',
    'get_user_permissions_detail',
    'decode_bits_to_string',
    'encode_string_to_bits',
]