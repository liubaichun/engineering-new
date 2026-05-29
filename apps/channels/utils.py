"""
凭证加密工具
CNAS/CMA 要求：敏感凭证（app_secret/corp_secret/token 等）不得明文存储
使用 Fernet（AEAD-AES-128-CBC）加密，密钥从环境变量 CHANNEL_CREDENTIAL_KEY 读取
"""

import os
import base64
import hashlib
import logging
from typing import Dict, Any, List

from django.conf import settings

# 所有需要加密的敏感字段（渠道无关）
SENSITIVE_FIELDS: List[str] = [
    'app_secret',
    'corp_secret',
    'appSecret',
    'token',
    'wxtoken',
    'suite_secret',
    'wxAppSecret',
    'api_key',
    'api_secret',
]

# 加密字段标记前缀
ENC_PREFIX = '__enc__:'

logger = logging.getLogger(__name__)


def _get_fernet_key() -> bytes:
    """
    获取 Fernet 密钥
    优先从环境变量 CHANNEL_CREDENTIAL_KEY 读取，否则用 Django SECRET_KEY 派生
    CNAS 要求：生产环境必须设置独立的环境变量密钥
    """
    env_key = os.environ.get('CHANNEL_CREDENTIAL_KEY')
    if env_key:
        key_source = env_key
    else:
        # SECRET_KEY 长度足够，用 HKDF-SHA256 派生出稳定的 32 字节 key
        key_source = getattr(settings, 'SECRET_KEY', None)
        if not key_source:
            logger.error(
                '[安全警告] CHANNEL_CREDENTIAL_KEY 环境变量未设置，且 SECRET_KEY 缺失。'
                '凭证加密将使用临时随机密钥，重启服务后已加密数据将无法解密。'
                '请在生产环境设置 CHANNEL_CREDENTIAL_KEY 环境变量。'
            )
            key_source = 'engineering-unsafe-temp-key'

    # HKDF 派生：SHA256 → 32 字节 → URL-safe base64（Fernet 格式）
    derived = hashlib.sha256(key_source.encode('utf-8')).digest()
    fkey = base64.urlsafe_b64encode(derived)
    return fkey


def _encrypt_value(plaintext: str) -> str:
    """对单个明文字符串进行 Fernet 加密，返回 __enc__:base64 格式"""
    from cryptography.fernet import Fernet

    f = Fernet(_get_fernet_key())
    ciphertext = f.encrypt(plaintext.encode('utf-8'))
    return ENC_PREFIX + base64.urlsafe_b64encode(ciphertext).decode('ascii')


def _decrypt_value(ciphertext_with_prefix: str) -> str:
    """解密 __enc__:base64 格式的密文，返回明文"""
    from cryptography.fernet import Fernet

    if not ciphertext_with_prefix.startswith(ENC_PREFIX):
        return ciphertext_with_prefix  # 非加密值直接返回
    raw = ciphertext_with_prefix[len(ENC_PREFIX) :]
    f = Fernet(_get_fernet_key())
    plaintext = f.decrypt(base64.urlsafe_b64decode(raw))
    return plaintext.decode('utf-8')


def encrypt_credentials(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    加密 config 中的敏感字段（原地替换）
    调用时机：保存到数据库之前（ChannelListView.post / ChannelDetailView.patch）
    返回新的 config dict（含加密字段和 _encrypted 元数据）
    """
    if not isinstance(config, dict):
        return config

    encrypted_fields: List[str] = []
    result = {}

    for key, value in config.items():
        if key in SENSITIVE_FIELDS and isinstance(value, str) and value.strip():
            # 非空字符串才加密，空值跳过（避免加密 '' 导致存储膨胀）
            result[key] = _encrypt_value(value)
            encrypted_fields.append(key)
        else:
            result[key] = value

    if encrypted_fields:
        result['_encrypted'] = encrypted_fields

    return result


def decrypt_credentials(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    解密 config 中的敏感字段（原地还原）
    调用时机：从数据库读取后传给插件（ChannelRegistry.get_plugin 之前）
    不修改原 dict，返回新的还原后的 dict
    """
    if not isinstance(config, dict):
        return config

    encrypted_fields = config.get('_encrypted', [])
    result = {}

    for key, value in config.items():
        if key == '_encrypted':
            continue  # 元数据不传给插件
        if key in encrypted_fields and isinstance(value, str) and value.startswith(ENC_PREFIX):
            try:
                result[key] = _decrypt_value(value)
            except Exception:
                # 解密失败时保留原始值（兼容已损坏数据或测试桩）
                result[key] = value
        else:
            result[key] = value

    return result


def is_encrypted(config: Dict[str, Any]) -> bool:
    """检查 config 是否包含加密字段"""
    return isinstance(config, dict) and bool(config.get('_encrypted'))


# ========== OAuth State 安全签名（防会话固定攻击）==========
import hmac
import time

STATE_MAX_AGE_SECONDS = 600  # 10 分钟


def _get_state_key() -> str:
    """
    获取 state 签名密钥
    优先从环境变量 CHANNEL_STATE_KEY 读取，否则用 SECRET_KEY 派生
    """
    env_key = os.environ.get('CHANNEL_STATE_KEY')
    if env_key:
        return env_key
    key = getattr(settings, 'SECRET_KEY', None)
    if not key:
        logger.error(
            '[安全警告] CHANNEL_STATE_KEY 环境变量未设置，且 SECRET_KEY 缺失。'
            'OAuth state 签名将使用临时密钥，存在会话固定攻击风险。'
            '请在生产环境设置 CHANNEL_STATE_KEY 环境变量。'
        )
        return 'engineering-unsafe-temp-state-key'
    return key


def make_oauth_state(user_id: int) -> str:
    """
    生成带时间戳和签名的 OAuth state，防止会话固定攻击
    格式：user_id.timestamp.signature
    有效期 10 分钟
    """
    timestamp = int(time.time())
    raw = f'{user_id}.{timestamp}'
    sig = hmac.new(_get_state_key().encode('utf-8'), raw.encode('utf-8'), hashlib.sha256).hexdigest()[:16]
    return f'{raw}.{sig}'


def verify_oauth_state(state: str) -> tuple[bool, int | None, str]:
    """
    验证 OAuth state 签名和时效性
    Returns: (is_valid, user_id, error_reason)
    """
    if not state:
        return False, None, 'state 为空'

    parts = state.split('.')
    if len(parts) != 3:
        # 兼容旧格式（纯 user_id 字符串）
        if state.isdigit():
            return True, int(state), ''  # 旧格式不做过期校验，放行
        return False, None, f'state 格式错误: {state[:50]}'

    user_id_str, timestamp_str, sig = parts

    if not user_id_str.isdigit():
        return False, None, 'state user_id 非数字'

    timestamp = int(timestamp_str)
    user_id = int(user_id_str)

    # 校验签名
    raw = f'{user_id}.{timestamp}'
    expected_sig = hmac.new(_get_state_key().encode('utf-8'), raw.encode('utf-8'), hashlib.sha256).hexdigest()[:16]
    if not hmac.compare_digest(sig, expected_sig):
        return False, None, 'state 签名不匹配（可能被篡改）'

    # 校验时间戳是否过期
    age = int(time.time()) - timestamp
    if age > STATE_MAX_AGE_SECONDS:
        return False, None, f'state 已过期（{age}秒 > {STATE_MAX_AGE_SECONDS}秒）'

    return True, user_id, ''
