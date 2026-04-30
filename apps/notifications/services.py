"""
通知渠道发送服务
支持：飞书、企业微信、钉钉、自定义Webhook
"""
import json
import hashlib
import hmac
import time
import urllib.parse
import urllib.request
import urllib.error
from typing import Optional


class NotificationSendError(Exception):
    """通知发送失败"""
    pass


def send_feishu(webhook_url: str, secret: str, title: str, content: str) -> dict:
    """
    发送飞书消息（支持加密签名）
    飞书机器人 webhook + secret 签名机制
    """
    if not webhook_url:
        raise NotificationSendError("飞书 Webhook URL 不能为空")

    # 如果配置了 secret，使用签名
    if secret:
        timestamp = str(int(time.time() * 1000))
        sign_str = f"{timestamp}\n{secret}"
        sign = hmac.new(
            sign_str.encode('utf-8'),
            sign_str.encode('utf-8'),
            digestmod=hashlib.sha256
        ).hexdigest()
        # 签名加到 URL 参数
        parsed = urllib.parse.urlparse(webhook_url)
        qs = urllib.parse.parse_qs(parsed.query)
        qs['timestamp'] = [timestamp]
        qs['sign'] = [sign]
        new_qs = urllib.parse.urlencode(qs, doseq=True)
        webhook_url = urllib.parse.urlunparse((
            parsed.scheme, parsed.netloc, parsed.path,
            parsed.params, new_qs, parsed.fragment
        ))

    payload = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": title},
                "template": "blue"
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": content
                    }
                },
                {
                    "tag": "hr"
                },
                {
                    "tag": "note",
                    "elements": [
                        {"tag": "plain_text", "content": "工程管理系统 · 自动化通知"}
                    ]
                }
            ]
        }
    }
    return _http_post(webhook_url, payload)


def send_wecom(webhook_url: str, secret: str, title: str, content: str) -> dict:
    """
    发送企业微信消息
    支持加签和密钥两种方式
    """
    if not webhook_url:
        raise NotificationSendError("企业微信 Webhook URL 不能为空")

    # 企业微信支持 Markdown，构造富文本
    payload = {
        "msgtype": "markdown",
        "markdown": {
            "content": f"**{title}**\n>{content}\n\n_工程管理系统通知_"
        }
    }
    return _http_post(webhook_url, payload)


def send_dingtalk(webhook_url: str, secret: str, title: str, content: str) -> dict:
    """
    发送钉钉消息（支持加签）
    """
    if not webhook_url:
        raise NotificationSendError("钉钉 Webhook URL 不能为空")

    # 钉钉加签
    if secret:
        timestamp = str(int(time.time() * 1000))
        sign_str = f"{timestamp}\n{secret}"
        sign = hmac.new(
            sign_str.encode('utf-8'),
            sign_str.encode('utf-8'),
            digestmod=hashlib.sha256
        ).hexdigest()
        sign = urllib.parse.quote_plus(sign)
        separator = '&' if '?' in webhook_url else '?'
        webhook_url = f"{webhook_url}{separator}timestamp={timestamp}&sign={sign}"

    payload = {
        "msgtype": "markdown",
        "markdown": {
            "title": title,
            "text": f"### {title}\n\n{content}\n\n---\n> 工程管理系统"
        }
    }
    return _http_post(webhook_url, payload)


def send_webhook(webhook_url: str, secret: str, title: str, content: str) -> dict:
    """
    发送自定义 Webhook（通用 JSON POST）
    """
    if not webhook_url:
        raise NotificationSendError("Webhook URL 不能为空")

    payload = {
        "title": title,
        "content": content,
        "timestamp": int(time.time()),
    }
    if secret:
        payload["secret"] = secret

    return _http_post(webhook_url, payload)


def send_email(webhook_url: str, secret: str, title: str, content: str) -> dict:
    """
    邮件通知（简单 SMTP URL 格式或直接 API）
    secret 字段存储 SMTP 配置 JSON
    """
    # 邮件使用 Django EmailBackend，通过 settings 处理
    # 此处简化：webhook_url 作为邮件目标，secret 作为发件人配置
    if not webhook_url:
        raise NotificationSendError("邮件目标地址不能为空")

    # 通过 Django send_mail 发送
    from django.core.mail import send_mail
    from django.conf import settings

    try:
        send_mail(
            subject=title,
            message=content,
            from_email=secret or settings.DEFAULT_FROM_EMAIL,
            recipient_list=[webhook_url],
            fail_silently=False,
        )
        return {"status": "ok", "message": "邮件发送成功"}
    except Exception as e:
        raise NotificationSendError(f"邮件发送失败: {str(e)}")


def send_notification(
    channel_type: str,
    webhook_url: str,
    secret: str,
    title: str,
    content: str,
) -> dict:
    """
    根据渠道类型分发发送
    """
    senders = {
        'feishu': send_feishu,
        'wecom': send_wecom,
        'dingtalk': send_dingtalk,
        'email': send_email,
        'webhook': send_webhook,
    }
    sender = senders.get(channel_type)
    if not sender:
        raise NotificationSendError(f"不支持的渠道类型: {channel_type}")

    return sender(webhook_url, secret, title, content)


def test_connection(channel) -> dict:
    """
    测试单个渠道连通性
    channel: NotificationChannel 实例或字典
    """
    channel_type = channel.channel_type if hasattr(channel, 'channel_type') else channel.get('channel_type', '')
    webhook_url = channel.webhook_url if hasattr(channel, 'webhook_url') else channel.get('webhook_url', '')
    secret = channel.secret if hasattr(channel, 'secret') else channel.get('secret', '')

    test_title = "🔔 连通性测试"
    test_content = "这是一条来自**工程管理系统**的连通性测试消息。如果你能看到此消息，说明通知渠道配置正确。"

    try:
        result = send_notification(channel_type, webhook_url, secret, test_title, test_content)
        return {"status": "ok", "message": "测试消息发送成功，请检查是否收到通知", "detail": result}
    except NotificationSendError as e:
        return {"status": "error", "message": str(e)}
    except Exception as e:
        return {"status": "error", "message": f"发送异常: {str(e)}"}


def _http_post(url: str, payload: dict, timeout: int = 10) -> dict:
    """通用 HTTP POST 发送"""
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=data,
        headers={'Content-Type': 'application/json', 'User-Agent': 'EngineeringSystem/1.0'}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            if resp.status != 200:
                raise NotificationSendError(f"HTTP {resp.status}: {result}")
            return result
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8')
        raise NotificationSendError(f"HTTP {e.code}: {body[:500]}")
    except urllib.error.URLError as e:
        raise NotificationSendError(f"网络错误: {e.reason}")
    except json.JSONDecodeError as e:
        raise NotificationSendError(f"响应解析失败: {str(e)}")
