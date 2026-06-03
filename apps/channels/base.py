"""通知渠道插件基类 — 简化版，只保留必要的抽象方法"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class BaseChannelPlugin(ABC):
    """渠道插件基类 — 每个渠道只需实现验证凭证和发送消息"""

    channel_type: str = None  # 'feishu', 'wecom', 'dingtalk'
    channel_name: str = None  # '飞书', '企业微信'

    def __init__(self, config: Dict[str, Any]):
        self.config = config or {}

    @abstractmethod
    def validate_credentials(self) -> tuple[bool, str]:
        """验证配置的凭证是否有效 → (是否有效, 消息)"""
        pass

    @abstractmethod
    def send_message(self, open_id: str, title: str, content: str, extra: Dict = None) -> tuple[bool, str]:
        """发送消息 → (是否成功, 消息)
        open_id='' 时表示广播（发到群/全体）
        open_id 有值时表示发私信给指定用户
        """
        pass


class ChannelRegistry:
    """插件注册表"""

    _plugins: Dict[str, type] = {}

    @classmethod
    def register(cls, plugin_class: type):
        if not issubclass(plugin_class, BaseChannelPlugin):
            raise ValueError(f'{plugin_class} 必须继承 BaseChannelPlugin')
        cls._plugins[plugin_class.channel_type] = plugin_class

    @classmethod
    def get_plugin(cls, channel_type: str, config: Dict = None) -> Optional[BaseChannelPlugin]:
        plugin_class = cls._plugins.get(channel_type)
        if plugin_class and config is not None:
            return plugin_class(config)
        return plugin_class

    @classmethod
    def get_all_channel_types(cls) -> list:
        return list(cls._plugins.keys())


# 自动注册已实现的插件
from apps.channels.plugins.feishu.plugin import FeishuPlugin
from apps.channels.plugins.wecom.plugin import WecomPlugin
from apps.channels.plugins.dingtalk.plugin import DingtalkPlugin
from apps.channels.plugins.email.plugin import EmailPlugin

ChannelRegistry.register(FeishuPlugin)
ChannelRegistry.register(WecomPlugin)
ChannelRegistry.register(DingtalkPlugin)
ChannelRegistry.register(EmailPlugin)
