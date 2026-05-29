# ── 兼容重导出层 ──────────────────────────────────────────────
# 所有 View 已迁移到 views_*.py，此处保留向后兼容
# 新代码请直接从对应的 views_*.py 导入

from .views_channel import ChannelListView, ChannelDetailView
from .views_binding import BindingQRCodeView, BindingCallbackView, WebhookView, BindingListCreateView
from .views_notify import SendNotificationView, NotificationLogView
from .views_role_test import RoleBindingListView, ValidateCredentialsView, SendTestMessageView

__all__ = [
    'ChannelListView',
    'ChannelDetailView',
    'BindingQRCodeView',
    'BindingCallbackView',
    'WebhookView',
    'BindingListCreateView',
    'SendNotificationView',
    'NotificationLogView',
    'RoleBindingListView',
    'ValidateCredentialsView',
    'SendTestMessageView',
]
