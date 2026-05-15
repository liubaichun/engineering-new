"""
钉钉渠道插件
支持：OAuth扫码绑定 + 发送应用消息
"""
import requests
from django.http import HttpRequest
from django.utils import timezone
from apps.channels.base import BaseChannelPlugin


class DingtalkPlugin(BaseChannelPlugin):
    channel_type = 'dingtalk'
    channel_name = '钉钉'
    
    def __init__(self, config: dict):
        self.app_key = config.get('app_key', '')
        self.app_secret = config.get('app_secret', '')
        self.agent_id = config.get('agent_id', '')
        self.bot_name = config.get('bot_name', '企业助手')
        self._token = None
    
    @classmethod
    def get_required_config_fields(cls) -> list:
        return [
            {'name': 'app_key', 'label': 'AppKey', 'type': 'text'},
            {'name': 'app_secret', 'label': 'AppSecret', 'type': 'password'},
            {'name': 'agent_id', 'label': 'AgentID', 'type': 'text'},
        ]
    
    @classmethod
    def get_optional_config_fields(cls) -> list:
        return [
            {'name': 'bot_name', 'label': '机器人名称', 'type': 'text'},
        ]
    
    def _get_access_token(self) -> tuple[bool, str]:
        """获取access_token"""
        url = 'https://api.dingtalk.com/v1.0/oauth2/accessToken'
        data = {
            'appKey': self.app_key,
            'appSecret': self.app_secret,
        }
        try:
            resp = requests.post(url, json=data, timeout=10)
            result = resp.json()
            if result.get('success') == True:
                self._token = result.get('accessToken', '')
                return True, self._token
            return False, f"获取token失败: {result.get('errmsg', result)}"
        except Exception as e:
            return False, f"请求异常: {str(e)}"
    
    def validate_credentials(self) -> tuple[bool, str]:
        """验证钉钉凭证"""
        success, token = self._get_access_token()
        if success:
            return True, '钉钉应用凭证有效'
        return False, token
    
    def get_binding_url(self, callback_url: str, state: str = '') -> str:
        """生成钉钉OAuth扫码绑定URL"""
        import urllib.parse
        params = {
            'appkey': self.app_key,
            'redirect_uri': callback_url,
            'response_type': 'code',
            'scope': 'openid',
            'state': state or 'dingtalk_bind',
        }
        query = urllib.parse.urlencode(params)
        return f'https://oa.dingtalk.com/authorize?{query}'
    
    def _get_userid_by_code(self, code: str) -> tuple[bool, dict]:
        """用code换userid"""
        if not self._token:
            self._get_access_token()
        
        url = 'https://api.dingtalk.com/v1.0/contact/users/ad'
        headers = {'x-acs-dingtalk-access-token': self._token}
        data = {'code': code}
        
        try:
            resp = requests.post(url, json=data, headers=headers, timeout=10)
            result = resp.json()
            if result.get('success') == True:
                user_info = result.get('result', {})
                return True, {
                    'userid': user_info.get('userId', ''),
                    'unionid': user_info.get('unionId', ''),
                }
            return False, {'error': f"获取用户信息失败: {result.get('errmsg', '未知错误')}"}
        except Exception as e:
            return False, {'error': f"请求异常: {str(e)}"}
    
    def handle_callback(self, request: HttpRequest, channel) -> tuple[bool, dict]:
        """处理钉钉OAuth回调"""
        code = request.GET.get('code')
        if not code:
            return False, {'error': '缺少code参数'}
        
        success, result = self._get_userid_by_code(code)
        if not success:
            return False, result
        
        userid = result.get('userid', '')
        unionid = result.get('unionid', '')
        
        # 获取用户详情
        user_info = {}
        if userid and self._token:
            try:
                url = f'https://api.dingtalk.com/v1.0/contact/users/{{userid}}'
                headers = {'x-acs-dingtalk-access-token': self._token}
                # 钉钉新版API
            except Exception:
                pass
        
        return True, {
            'open_id': unionid or userid,
            'user_info': user_info or {'name': '钉钉用户'},
        }
    
    def send_message(self, open_id: str, title: str, content: str, extra: dict = None) -> tuple[bool, str]:
        """发送钉钉消息"""
        if not self._token:
            self._get_access_token()
        
        url = 'https://api.dingtalk.com/v1.0/im/messages'
        headers = {
            'x-acs-dingtalk-access-token': self._token,
            'Content-Type': 'application/json',
        }
        
        msg_content = f"**{title}**\n\n{content}\n\n—— 来自企业信息化管理系统"
        
        data = {
            'robotCode': self.app_key,
            'msgId': f'msg_{open_id}_{timezone.now().timestamp()}',
            'msgParam': '{"content":"' + msg_content.replace('"', '\\"') + '"}',
            'msgType': 'text',
            'recipientUsers': [open_id],
        }
        
        try:
            resp = requests.post(url, json=data, headers=headers, timeout=15)
            result = resp.json()
            
            if result.get('success') == True:
                return True, '发送成功'
            
            # token失效重试
            if result.get('errcode') in [40014, 40078]:
                self._get_access_token()
                headers['x-acs-dingtalk-access-token'] = self._token
                resp = requests.post(url, json=data, headers=headers, timeout=15)
                result = resp.json()
                if result.get('success') == True:
                    return True, '发送成功'
            
            return False, f"发送失败: {result.get('errmsg', '未知错误')}"
        except Exception as e:
            return False, f"发送异常: {str(e)}"
    
    def get_status(self) -> dict:
        """获取钉钉插件状态"""
        is_valid, msg = self.validate_credentials()
        return {
            'credentials_valid': is_valid,
            'credentials_message': msg,
            'app_key': self.app_key[:8] + '***' if self.app_key else '',
            'agent_id': self.agent_id,
        }


# 自动注册到全局插件注册表
from apps.channels.base import ChannelRegistry
ChannelRegistry.register(DingtalkPlugin)

from django.utils import timezone
