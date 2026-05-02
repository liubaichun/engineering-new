"""
微信个人号渠道插件
支持：扫码绑定（通过PushPlus/Server酱等第三方服务）+ 发送通知

说明：微信个人号没有官方API，本插件通过第三方推送服务实现
推荐使用 PushPlus（pushplus.plus）- 免费、稳定、简单
"""
import requests
from django.http import HttpRequest
from apps.channels.base import BaseChannelPlugin


class WechatPlugin(BaseChannelPlugin):
    channel_type = 'wechat'
    channel_name = '微信个人号'
    
    def __init__(self, config: dict):
        # 第三方服务配置（PushPlus为例）
        self.api_url = config.get('api_url', 'http://pushplus.plus/send')
        self.token = config.get('token', '')
        self.topic = config.get('topic', '')  # 群发标签
        self.bot_name = config.get('bot_name', '企业助手')
    
    @classmethod
    def get_required_config_fields(cls) -> list:
        return [
            {'name': 'token', 'label': 'PushPlus Token', 'type': 'text'},
        ]
    
    @classmethod
    def get_optional_config_fields(cls) -> list:
        return [
            {'name': 'api_url', 'label': 'API地址', 'type': 'text'},
            {'name': 'topic', 'label': '群发主题', 'type': 'text'},
            {'name': 'bot_name', 'label': '机器人名称', 'type': 'text'},
        ]
    
    def validate_credentials(self) -> tuple[bool, str]:
        """验证PushPlus token是否有效（发送测试消息）"""
        test_data = {
            'token': self.token,
            'title': '连接测试',
            'content': '这是一条测试消息，如果收到此消息，说明绑定成功！',
        }
        try:
            resp = requests.post(self.api_url, json=test_data, timeout=10)
            result = resp.json()
            if result.get('code') == 200:
                return True, '微信推送服务正常'
            return False, f"验证失败: {result.get('msg', '未知错误')}"
        except Exception as e:
            return False, f"连接异常: {str(e)}"
    
    def get_binding_url(self, callback_url: str) -> str:
        """
        获取绑定URL
        微信个人号不支持OAuth，返回空字符串表示需要手动绑定
        """
        return ''  # 微信不支持OAuth，依赖手动输入token绑定
    
    def handle_callback(self, request: HttpRequest, channel) -> tuple[bool, dict]:
        """
        处理第三方服务回调
        微信个人号通常不需要回调，绑定即视为成功
        """
        # 微信个人号不需要open_id，直接用token标识
        return True, {
            'open_id': self.token,  # 用token作为标识
            'user_info': {
                'name': '微信用户',
                'note': '微信个人号绑定'
            }
        }
    
    def send_message(self, open_id: str, title: str, content: str, extra: dict = None) -> tuple[bool, str]:
        """发送微信消息（通过PushPlus API）"""
        # 微信消息内容
        msg_content = f"**{title}**\n\n{content}\n\n—— 来自企业信息化管理系统"
        
        data = {
            'token': self.token,
            'title': title,
            'content': msg_content,
        }
        
        # 如果有topic（群发标识），加入请求
        if self.topic:
            data['topic'] = self.topic
        
        try:
            resp = requests.post(self.api_url, json=data, timeout=15)
            result = resp.json()
            
            if result.get('code') == 200:
                return True, '发送成功'
            return False, f"发送失败: {result.get('msg', '未知错误')}"
        except Exception as e:
            return False, f"发送异常: {str(e)}"
    
    def get_status(self) -> dict:
        """获取微信插件状态"""
        is_valid, msg = self.validate_credentials()
        return {
            'credentials_valid': is_valid,
            'credentials_message': msg,
            'token': self.token[:6] + '***' if self.token else '',
        }


# 自动注册到全局插件注册表
from apps.channels.base import ChannelRegistry
ChannelRegistry.register(WechatPlugin)
