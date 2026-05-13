"""
飞书渠道插件
支持：二维码扫码绑定 + 发送通知
"""
import requests
from django.http import HttpRequest
from apps.channels.base import BaseChannelPlugin


class FeishuPlugin(BaseChannelPlugin):
    channel_type = 'feishu'
    channel_name = '飞书'
    
    def __init__(self, config: dict):
        self.app_id = config.get('app_id', '')
        self.app_secret = config.get('app_secret', '')
        self.bot_name = config.get('bot_name', '企业助手')
        self.webhook_url = config.get('webhook_url', '')
        self.webhook_secret = config.get('webhook_secret', '')
        self._token = None
    
    @classmethod
    def get_required_config_fields(cls) -> list:
        return [
            {'name': 'app_id', 'label': 'App ID', 'type': 'text'},
            {'name': 'app_secret', 'label': 'App Secret', 'type': 'password'},
        ]
    
    @classmethod
    def get_optional_config_fields(cls) -> list:
        return [
            {'name': 'bot_name', 'label': '机器人名称', 'type': 'text'},
            {'name': 'webhook_url', 'label': '机器人 Webhook URL（群播模式）', 'type': 'text'},
            {'name': 'webhook_secret', 'label': '签名密钥（群播模式）', 'type': 'password'},
        ]
    
    def _get_tenant_access_token(self) -> tuple[bool, str]:
        """获取tenant_access_token"""
        url = 'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token'
        data = {
            'app_id': self.app_id,
            'app_secret': self.app_secret,
        }
        try:
            resp = requests.post(url, json=data, timeout=10)
            result = resp.json()
            if result.get('code') == 0:
                self._token = result['tenant_access_token']
                return True, result['tenant_access_token']
            return False, f"获取token失败: {result.get('msg', '未知错误')}"
        except Exception as e:
            return False, f"请求异常: {str(e)}"
    
    def validate_credentials(self) -> tuple[bool, str]:
        """验证App ID和Secret是否有效"""
        success, token = self._get_tenant_access_token()
        if success:
            return True, '飞书应用凭证有效'
        return False, token
    
    def get_binding_url(self, callback_url: str, state: str = '') -> str:
        """生成飞书OAuth扫码绑定URL"""
        import urllib.parse
        params = {
            'redirect_uri': callback_url,
            'app_id': self.app_id,
            'scope': 'im:message:send_as_bot',
            'state': state or 'feishu_bind',
        }
        query = urllib.parse.urlencode(params)
        return f'https://open.feishu.cn/open-apis/authen/v1/index?{query}'
    
    def handle_callback(self, request: HttpRequest, channel) -> tuple[bool, dict]:
        """
        处理飞书OAuth回调
        1. 用code换open_id
        2. 获取用户信息
        """
        code = request.GET.get('code')
        if not code:
            return False, {'error': '缺少code参数'}
        
        # 用code换user_access_token
        url = 'https://open.feishu.cn/open-apis/authen/v1/oidc/access_token'
        headers = {'Authorization': f'Bearer {self._token}'}
        data = {'grant_type': 'authorization_code', 'code': code}
        
        try:
            resp = requests.post(url, json=data, headers=headers, timeout=10)
            result = resp.json()
            
            if result.get('code') != 0:
                # token可能过期，重新获取
                self._get_tenant_access_token()
                headers = {'Authorization': f'Bearer {self._token}'}
                resp = requests.post(url, json=data, headers=headers, timeout=10)
                result = resp.json()
            
            if result.get('code') == 0:
                data_body = result.get('data', {})
                open_id = data_body.get('open_id', '')
                name = data_body.get('name', '')
                avatar_url = data_body.get('avatar_url', '')
                
                return True, {
                    'open_id': open_id,
                    'user_info': {
                        'name': name,
                        'avatar': avatar_url,
                    }
                }
            return False, {'error': f"获取用户信息失败: {result.get('msg', '未知错误')}"}
        except Exception as e:
            return False, {'error': f"回调处理异常: {str(e)}"}
    
    def send_message(self, open_id: str, title: str, content: str, extra: dict = None) -> tuple[bool, str]:
        """发送飞书消息

        - open_id 有值 → IM 应用消息（需要用户已绑定）
        - open_id 为空 + webhook_url 有值 → Webhook 群播（兼容旧系统）
        """
        # 群播模式：open_id 为空且配置了 webhook_url
        if not open_id and self.webhook_url:
            return self._send_webhook_message(title, content)

        # IM 模式：必须有 open_id
        if not open_id:
            return False, 'open_id 不能为空（请使用群播模式或先绑定用户）'

        if not self._token:
            self._get_tenant_access_token()

        url = 'https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id'
        headers = {
            'Authorization': f'Bearer {self._token}',
            'Content-Type': 'application/json',
        }

        msg_content = {
            'msg_type': 'interactive',
            'content': {
                'card': {
                    'header': {
                        'title': {'tag': 'plain_text', 'content': title},
                        'template': 'blue',
                    },
                    'elements': [
                        {'tag': 'div', 'text': {'tag': 'lark_md', 'content': content}},
                        {'tag': 'hr'},
                        {'tag': 'note', 'elements': [
                            {'tag': 'plain_text', 'content': '来自企业信息化管理系统'}
                        ]},
                    ],
                }
            }
        }

        try:
            resp = requests.post(url, json=msg_content, headers=headers, timeout=15)
            result = resp.json()

            if result.get('code') == 0:
                return True, '发送成功'

            if result.get('code') in (99991663, 99991664):
                self._get_tenant_access_token()
                headers['Authorization'] = f'Bearer {self._token}'
                resp = requests.post(url, json=msg_content, headers=headers, timeout=15)
                result = resp.json()
                if result.get('code') == 0:
                    return True, '发送成功'

            return False, f"发送失败: {result.get('msg', '未知错误')}"
        except Exception as e:
            return False, f"发送异常: {str(e)}"

    def _send_webhook_message(self, title: str, content: str) -> tuple[bool, str]:
        """飞书 Webhook 群播（兼容旧系统）"""
        import time
        import hmac
        import hashlib

        webhook_url = self.webhook_url
        secret = self.webhook_secret

        if secret:
            timestamp = str(int(time.time() * 1000))
            sign_str = f"{timestamp}\n{secret}"
            sign = hmac.new(
                sign_str.encode('utf-8'), sign_str.encode('utf-8'),
                digestmod=hashlib.sha256
            ).hexdigest()
            separator = '&' if '?' in webhook_url else '?'
            webhook_url = f"{webhook_url}{separator}timestamp={timestamp}&sign={sign}"

        payload = {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {"tag": "plain_text", "content": title},
                    "template": "blue"
                },
                "elements": [
                    {"tag": "div", "text": {"tag": "lark_md", "content": content}},
                    {"tag": "hr"},
                    {"tag": "note", "elements": [
                        {"tag": "plain_text", "content": "工程管理系统 · 自动化通知"}
                    ]},
                ]
            }
        }

        try:
            resp = requests.post(webhook_url, json=payload, timeout=15)
            result = resp.json()
            if result.get('code') == 0 or result.get('StatusCode') == 0:
                return True, 'Webhook 群播成功'
            return False, f"Webhook 发送失败: {result.get('msg', result.get('errmsg', '未知错误'))}"
        except Exception as e:
            return False, f"Webhook 请求异常: {str(e)}"
    
    def get_status(self) -> dict:
        """获取飞书插件状态"""
        is_valid, msg = self.validate_credentials()
        return {
            'credentials_valid': is_valid,
            'credentials_message': msg,
            'app_id': self.app_id[:8] + '***' if self.app_id else '',
        }


# 自动注册到全局插件注册表
from apps.channels.base import ChannelRegistry
ChannelRegistry.register(FeishuPlugin)
