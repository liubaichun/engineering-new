"""
企业微信渠道插件
支持：OAuth扫码绑定 + 发送应用消息
"""
import requests
from django.http import HttpRequest
from apps.channels.base import BaseChannelPlugin


class WecomPlugin(BaseChannelPlugin):
    channel_type = 'wecom'
    channel_name = '企业微信'
    
    def __init__(self, config: dict):
        self.corp_id = config.get('corp_id', '')
        self.corp_secret = config.get('corp_secret', '')
        self.agent_id = config.get('agent_id', '')
        self.bot_name = config.get('bot_name', '企业助手')
        self._token = None
    
    @classmethod
    def get_required_config_fields(cls) -> list:
        return [
            {'name': 'corp_id', 'label': '企业ID(CorpID)', 'type': 'text'},
            {'name': 'corp_secret', 'label': '应用Secret', 'type': 'password'},
            {'name': 'agent_id', 'label': '应用AgentID', 'type': 'text'},
        ]
    
    @classmethod
    def get_optional_config_fields(cls) -> list:
        return [
            {'name': 'bot_name', 'label': '机器人名称', 'type': 'text'},
        ]
    
    def _get_access_token(self) -> tuple[bool, str]:
        """获取access_token"""
        url = 'https://qyapi.weixin.qq.com/cgi-bin/gettoken'
        params = {
            'corpid': self.corp_id,
            'corpsecret': self.corp_secret,
        }
        try:
            resp = requests.get(url, params=params, timeout=10)
            result = resp.json()
            if result.get('errcode') == 0:
                self._token = result['access_token']
                return True, result['access_token']
            return False, f"获取token失败: {result.get('errmsg', '未知错误')}"
        except Exception as e:
            return False, f"请求异常: {str(e)}"
    
    def validate_credentials(self) -> tuple[bool, str]:
        """验证企业微信凭证"""
        success, token = self._get_access_token()
        if success:
            return True, '企业微信应用凭证有效'
        return False, token
    
    def get_binding_url(self, callback_url: str, state: str = '') -> str:
        """生成企业微信OAuth扫码绑定URL"""
        import urllib.parse
        params = {
            'appid': self.corp_id,
            'redirect_uri': callback_url,
            'response_type': 'code',
            'scope': 'snsapi_private',
            'state': state or 'wecom_bind',
        }
        query = urllib.parse.urlencode(params)
        return f'https://open.work.weixin.qq.com/sns/auth?{query}'
    
    def _get_userid_by_code(self, code: str) -> tuple[bool, dict]:
        """用code换userid"""
        if not self._token:
            self._get_access_token()
        
        url = 'https://qyapi.weixin.qq.com/cgi-bin/user/getuserinfo'
        params = {'access_token': self._token, 'code': code}
        
        try:
            resp = requests.get(url, params=params, timeout=10)
            result = resp.json()
            if result.get('errcode') == 0:
                return True, {
                    'userid': result.get('UserId', ''),
                    'openid': result.get('OpenId', ''),
                }
            return False, {'error': f"获取用户信息失败: {result.get('errmsg', '未知错误')}"}
        except Exception as e:
            return False, {'error': f"请求异常: {str(e)}"}
    
    def handle_callback(self, request: HttpRequest, channel) -> tuple[bool, dict]:
        """处理企业微信OAuth回调"""
        code = request.GET.get('code')
        if not code:
            return False, {'error': '缺少code参数'}
        
        # 企业微信用code换userid
        success, result = self._get_userid_by_code(code)
        if not success:
            return False, result
        
        userid = result.get('userid', '')
        openid = result.get('openid', '')
        
        # 获取用户详情
        user_info = {}
        if userid and self._token:
            try:
                url = 'https://qyapi.weixin.qq.com/cgi-bin/user/get'
                params = {'access_token': self._token, 'userid': userid}
                resp = requests.get(url, params=params, timeout=10)
                info = resp.json()
                if info.get('errcode') == 0:
                    user_info = {
                        'name': info.get('name', ''),
                        'avatar': info.get('avatar', ''),
                        'department': info.get('department', []),
                    }
            except:
                pass
        
        return True, {
            'open_id': openid or userid,  # 优先用openid
            'user_info': user_info,
        }
    
    def send_message(self, open_id: str, title: str, content: str, extra: dict = None) -> tuple[bool, str]:
        """发送企业微信应用消息"""
        if not self._token:
            self._get_access_token()
        
        url = 'https://qyapi.weixin.qq.com/cgi-bin/message/send'
        params = {'access_token': self._token}
        
        # 构造消息内容（文本+标题）
        msg_data = {
            'touser': open_id,
            'msgtype': 'text',
            'agentid': self.agent_id,
            'text': {
                'content': f"{title}\n\n{content}\n\n— 来自企业信息化管理系统"
            }
        }
        
        try:
            resp = requests.post(url, params=params, json=msg_data, timeout=15)
            result = resp.json()
            
            if result.get('errcode') == 0:
                return True, '发送成功'
            
            # token失效重试
            if result.get('errcode') == 40014:
                self._get_access_token()
                params['access_token'] = self._token
                resp = requests.post(url, params=params, json=msg_data, timeout=15)
                result = resp.json()
                if result.get('errcode') == 0:
                    return True, '发送成功'
            
            return False, f"发送失败: {result.get('errmsg', '未知错误')}"
        except Exception as e:
            return False, f"发送异常: {str(e)}"
    
    def get_status(self) -> dict:
        """获取企业微信插件状态"""
        is_valid, msg = self.validate_credentials()
        return {
            'credentials_valid': is_valid,
            'credentials_message': msg,
            'corp_id': self.corp_id[:8] + '***' if self.corp_id else '',
            'agent_id': self.agent_id,
        }


# 自动注册到全局插件注册表
from apps.channels.base import ChannelRegistry
ChannelRegistry.register(WecomPlugin)
