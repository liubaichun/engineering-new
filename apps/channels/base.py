"""
通知渠道插件基类
所有渠道插件必须继承 BaseChannelPlugin 并实现相应方法
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from django.http import HttpRequest


class BaseChannelPlugin(ABC):
    """渠道插件抽象基类"""
    
    channel_type: str = None  # 'feishu', 'wecom', 'wechat'
    channel_name: str = None  # '飞书', '企业微信', '微信'
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
    
    # ========== 插件信息 ==========
    
    @classmethod
    def get_channel_type(cls) -> str:
        return cls.channel_type
    
    @classmethod
    def get_channel_name(cls) -> str:
        return cls.channel_name
    
    @classmethod
    def get_required_config_fields(cls) -> list:
        """返回必需的配置字段列表"""
        return []
    
    @classmethod
    def get_optional_config_fields(cls) -> list:
        """返回可选的配置字段列表"""
        return []
    
    # ========== 凭证验证 ==========
    
    @abstractmethod
    def validate_credentials(self) -> tuple[bool, str]:
        """
        验证凭证是否有效
        Returns: (is_valid, message)
        """
        pass
    
    # ========== 绑定流程 ==========
    
    @abstractmethod
    def get_binding_url(self, callback_url: str) -> str:
        """
        获取绑定URL（用于生成二维码或跳转链接）
        """
        pass
    
    @abstractmethod
    def handle_callback(self, request: HttpRequest, channel) -> tuple[bool, Dict[str, Any]]:
        """
        处理回调，返回 (是否成功, binding_info_dict)
        binding_info_dict 包含: open_id, user_info
        """
        pass
    
    # ========== 消息发送 ==========
    
    @abstractmethod
    def send_message(self, open_id: str, title: str, content: str, extra: Dict = None) -> tuple[bool, str]:
        """
        发送消息
        Returns: (is_success, message)
        """
        pass
    
    # ========== Webhook 处理（可选） ==========
    
    def handle_webhook(self, request: HttpRequest, channel) -> Optional[Dict]:
        """
        处理webhook事件（如果连接模式是webhook）
        子类可选实现
        """
        return None
    
    # ========== 状态检查 ==========
    
    def get_status(self) -> Dict[str, Any]:
        """
        返回插件当前状态
        """
        is_valid, msg = self.validate_credentials()
        return {
            'credentials_valid': is_valid,
            'credentials_message': msg,
        }


class ChannelRegistry:
    """插件注册表"""
    _plugins: Dict[str, type] = {}
    
    @classmethod
    def register(cls, plugin_class: type):
        if not issubclass(plugin_class, BaseChannelPlugin):
            raise ValueError(f"{plugin_class} must inherit from BaseChannelPlugin")
        cls._plugins[plugin_class.channel_type] = plugin_class
    
    @classmethod
    def get_plugin(cls, channel_type: str, config: Dict = None) -> Optional[BaseChannelPlugin]:
        plugin_class = cls._plugins.get(channel_type)
        if plugin_class and config is not None:
            # 解密凭证后再传给插件（凭证在数据库中以密文存储）
            from apps.channels.utils import decrypt_credentials
            decrypted_config = decrypt_credentials(config)
            return plugin_class(decrypted_config)
        return plugin_class
    
    @classmethod
    def get_all_channel_types(cls) -> list:
        return list(cls._plugins.keys())
    
    @classmethod
    def is_registered(cls, channel_type: str) -> bool:
        return channel_type in cls._plugins


# 导入时自动注册插件
from apps.channels.plugins.feishu.plugin import FeishuPlugin
from apps.channels.plugins.wecom.plugin import WecomPlugin
from apps.channels.plugins.wechat.plugin import WechatPlugin
from apps.channels.plugins.dingtalk.plugin import DingtalkPlugin
