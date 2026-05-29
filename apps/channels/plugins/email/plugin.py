"""
邮件渠道插件
支持 SMTP 直发邮件（无需用户绑定 open_id）
"""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header

from apps.channels.base import BaseChannelPlugin

logger = logging.getLogger('channels')


class EmailPlugin(BaseChannelPlugin):
    channel_type = 'email'
    channel_name = '邮件'

    def __init__(self, config: dict):
        self.smtp_host = config.get('smtp_host', 'smtp.example.com')
        self.smtp_port = int(config.get('smtp_port', 587))
        self.smtp_user = config.get('smtp_user', '')
        self.smtp_password = config.get('smtp_password', '')
        self.from_email = config.get('from_email', self.smtp_user)
        self.from_name = config.get('from_name', '企业信息化管理系统')
        self.use_tls = config.get('use_tls', True)

    @classmethod
    def get_required_config_fields(cls) -> list:
        return [
            {'name': 'smtp_host', 'label': 'SMTP 主机', 'type': 'text'},
            {'name': 'smtp_port', 'label': 'SMTP 端口', 'type': 'number'},
            {'name': 'smtp_user', 'label': 'SMTP 用户名', 'type': 'text'},
            {'name': 'smtp_password', 'label': 'SMTP 密码', 'type': 'password'},
        ]

    @classmethod
    def get_optional_config_fields(cls) -> list:
        return [
            {'name': 'from_email', 'label': '发件人邮箱', 'type': 'text'},
            {'name': 'from_name', 'label': '发件人昵称', 'type': 'text'},
            {'name': 'use_tls', 'label': '启用 TLS', 'type': 'boolean'},
        ]

    def validate_config(self, config: dict) -> list:
        """验证 SMTP 配置是否有效"""
        errors = []
        if not config.get('smtp_host'):
            errors.append('SMTP 主机不能为空')
        if not config.get('smtp_user'):
            errors.append('SMTP 用户名不能为空')
        if not config.get('smtp_password'):
            errors.append('SMTP 密码不能为空')
        return errors

    def validate_credentials(self) -> tuple[bool, str]:
        """验证 SMTP 凭证：尝试连接"""
        try:
            server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10)
            if self.use_tls:
                server.starttls()
            server.login(self.smtp_user, self.smtp_password)
            server.quit()
            return True, 'SMTP 凭证有效'
        except smtplib.SMTPAuthenticationError:
            return False, 'SMTP 认证失败，用户名或密码错误'
        except Exception as e:
            return False, f'SMTP 连接失败: {str(e)}'

    # 邮件渠道无需 OAuth 绑定，提供空实现
    def get_binding_url(self, callback_url: str, state: str = '') -> str:
        return ''

    def handle_callback(self, request, channel) -> tuple[bool, dict]:
        return False, {'error': '邮件渠道不需要绑定'}

    def send_message(self, open_id: str, title: str, content: str, extra: dict = None) -> tuple[bool, str]:
        """
        发送邮件。

        open_id 在邮件场景下即为 recipient_email，
        如果 open_id 为空但 extra['to_emails'] 有值则用后者。
        """
        # 邮件渠道不需要 open_id，直接从 extra 或已知地址获取收件人
        to_email = open_id  # 约定：open_id 就是邮件地址
        if not to_email and extra:
            to_email = extra.get('to_email', '')

        if not to_email:
            return False, '收件人邮箱不能为空'

        msg = MIMEMultipart('alternative')
        msg['From'] = f'{self.from_name} <{self.from_email}>'
        msg['To'] = to_email
        msg['Subject'] = Header(title, 'utf-8')

        # 纯文本版本
        text_part = MIMEText(content, 'plain', 'utf-8')
        msg.attach(text_part)

        # HTML 版本（如果 content 包含 HTML 标签）
        if '<html' in content.lower() or '<body' in content.lower():
            html_part = MIMEText(content, 'html', 'utf-8')
            msg.attach(html_part)

        try:
            server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=15)
            if self.use_tls:
                server.starttls()
            server.login(self.smtp_user, self.smtp_password)
            server.sendmail(self.from_email, [to_email], msg.as_string())
            server.quit()
            return True, f'邮件已发送至 {to_email}'
        except smtplib.SMTPAuthenticationError:
            return False, '邮件发送失败：SMTP 认证失败'
        except smtplib.SMTPRecipientsRefused:
            return False, f'邮件发送失败：收件人地址被拒绝: {to_email}'
        except Exception as e:
            return False, f'邮件发送异常: {str(e)}'
