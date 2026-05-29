"""
企业微信回调/验证接口
用于处理企业微信应用的 URL 验证和消息回调
"""
import hashlib
import base64
import logging
import struct
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

logger = logging.getLogger(__name__)

# 回调验证 Token
WECOM_CALLBACK_TOKEN = 'erpnotify2026'
# EncodingAESKey（用户在应用设置中生成）
WECOM_ENCODING_AES_KEY = 'EXoHUS5t3f2gF63dANFQHPmdRywN2hCNNBytrAaG5h2'


def _decrypt_message(encoding_aes_key, encrypted_msg):
    """解密企业微信消息"""
    try:
        # Base64 decode AES key
        aes_key = base64.b64decode(encoding_aes_key + '=')
        # Base64 decode encrypted message
        encrypted = base64.b64decode(encrypted_msg)
        
        # AES-256-CBC 解密
        iv = aes_key[:16]
        cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv))
        decryptor = cipher.decryptor()
        decrypted = decryptor.update(encrypted) + decryptor.finalize()
        
        # 去除 PKCS7 填充
        unpadder = padding.PKCS7(256).unpadder()
        decrypted = unpadder.update(decrypted) + unpadder.finalize()
        
        # 解析：random(16B) + msg_len(4B network order) + msg + corpid(最后)
        msg_len = struct.unpack('>I', decrypted[16:20])[0]
        msg = decrypted[20:20 + msg_len].decode('utf-8')
        return msg
    except Exception as e:
        logger.error(f'[WeCom] 解密失败: {e}')
        return None


@require_GET
@csrf_exempt
def wecom_verify(request):
    """
    企业微信 URL 验证接口
    """
    msg_signature = request.GET.get('msg_signature', '')
    timestamp = request.GET.get('timestamp', '')
    nonce = request.GET.get('nonce', '')
    echostr = request.GET.get('echostr', '')

    # 解密 echostr
    decrypted = _decrypt_message(WECOM_ENCODING_AES_KEY, echostr)
    
    if decrypted:
        logger.info(f'[WeCom Verify] URL验证成功: {decrypted}')
        return HttpResponse(decrypted)
    else:
        # 解密失败，尝试直接返回 echostr（兼容模式）
        logger.warning(f'[WeCom Verify] 解密失败，返回原始echostr')
        return HttpResponse(echostr)


@require_POST
@csrf_exempt
def wecom_callback(request):
    """接收企业微信推送的消息和事件"""
    logger.info(f'[WeCom Callback] 收到回调，body长度: {len(request.body)}')
    return HttpResponse('ok')
