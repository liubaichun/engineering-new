# 企业信息化管理系统 GREEN — 商业版需求报告 v2.0

**版本**：v2.0（从工程管理 → 企业信息化管理）
**日期**：2026-04-29
**定位**：初级商业版（稳定可用，功能完整）

---

## 一、系统定位调整

### 1.1 名称与定位变更

| 原定位 | 新定位 |
|--------|--------|
| 工程管理系统 | **企业信息化管理系统** |
| 聚焦工程行业 | **通用企业行政+业务管理** |
| 工程管理 CRUD | **企业人/财/物/事全链路管理** |

### 1.2 现有模块盘点

| 模块 | App名 | 定位 | 需改造 |
|------|-------|------|--------|
| 项目任务 | tasks | 业务 | 扩展项目管理 |
| 审批流 | approvals | 行政 | 深化企业审批 |
| 财务 | finance | 核心 | 扩展薪酬/社保 |
| CRM | crm | 业务 | 扩展客户全生命周期 |
| 物料 | material | 资产 | 改为物资仓储 |
| 设备 | equipment | 资产 | 扩展保修/折旧 |
| 文件 | files | 行政 | 增强预览 |
| 通知 | notifications | 行政 | 多通道推送 |
| 系统核心 | core | 基础设施 | 扩展组织架构 |

---

## 二、功能深化矩阵

### 2.1 P0（阻塞，必须修）

| # | 模块 | 问题 | 解决方案 | 文件 |
|---|------|------|---------|------|
| P0-1 | 财务 | Invoice.tax_amount未自动计算 | save()中 amount×tax_rate/100 | finance/models.py |
| P0-2 | 财务 | date/expense_date冗余字段 | 统一为expense_date，删date | finance/models.py |
| P0-3 | 审批 | 超时自动升级未集成crontab | check_approval_timeouts进cron | approvals/management |
| P0-4 | 审批 | ApprovalFlow无company字段 | 加ForeignKey | approvals/models.py |
| P0-5 | 通知 | Notification无ViewSet | core/views.py添加 | core/views.py |
| P0-6 | CRM | admin.py空白 | 新建admin.py | crm/admin.py |
| P0-7 | 物料 | admin.py空白 | 新建admin.py | material/admin.py |
| P0-8 | 文件 | admin.py空白 | 新建admin.py | files/admin.py |
| P0-9 | 设备 | admin.py不完整 | 完善list_filter/search | equipment/admin.py |
| P0-10 | 财务 | 工资权限码未初始化 | init_rbac.py添加 | core/management |

### 2.2 P1（影响商业完整性）

| # | 模块 | 问题 | 解决方案 |
|---|------|------|---------|
| P1-1 | 通知 | **飞书个人消息推送**（非机器人） | 飞书开放平台API，Open ID推送 |
| P1-2 | 通知 | **企业微信个人推送**（非群机器人） | 企业微信应用消息API |
| P1-3 | 通知 | **QQ个人消息推送** | QQ开放平台App，私聊消息 |
| P1-4 | 通知 | 统一通知服务 NotifyService | 策略模式多通道 |
| P1-5 | 通知 | 用户通知偏好绑定 | User表加openid字段 |
| P1-6 | 项目 | Project.progress手填，calculated_progress未同步 | perform_update中自动写回 |
| P1-7 | 项目 | Task无自动编号 | Task.save()中生成 |
| P1-8 | CRM | 无import_records action | 参考finance复制 |
| P1-9 | CRM | 合同无到期提醒 | check_contract_expiry cron |
| P1-10 | 文件 | 文件预览功能（图片/PDF/Office） | preview action + 前端模板 |
| P1-11 | 设备 | 无保修到期提醒 | check_warranty_expiry cron |
| P1-12 | 物料 | 库存预警未推送 | check_material_alerts cron |
| P1-13 | 审批 | 驳回重审后无resubmit链路 | 补全resubmit action |

### 2.3 P2（增强）

| # | 模块 | 问题 | 解决方案 |
|---|------|------|---------|
| P2-1 | CRM | Contract无执行进度追踪 | 加signed/completed_amount字段 |
| P2-2 | 物料 | 无库存金额统计 | Material加total_value属性 |
| P2-3 | 物料 | 无独立UsageLog ViewSet | 新建MaterialUsageLogViewSet |
| P2-4 | 设备 | management_type=serial时serial_number未校验 | Equipment.save()加校验 |
| P2-5 | 文件 | 新版上传同名文件version未自动递增 | CompanyFile.save()加逻辑 |
| P2-6 | 文件 | 无文件下载API | download action |
| P2-7 | 通知 | check_alerts未进crontab | /etc/cron.d/engineering-alerts |

---

## 三、新增模块需求（从工程 → 企业管理）

### 3.1 组织架构管理（新增 app: org）

**定位**：企业人事组织基础模块，其他所有模块依赖组织架构数据。

**模型设计**：

```
Organization（组织架构树）
  - name: 部门名称
  - parent: 上级部门（自关联）
  - manager: 部门负责人 → User
  - dept_code: 部门编码
  - dept_type: 部门类型（functional/project/branch）
  - phone/fax/email
  - company → Company（多租户）

Position（岗位/职位）
  - title: 职位名称
  - dept → Organization
  - rank: 职级（1-20）
  - salary_range_min/max
  - company → Company

EmployeeProfile（员工档案，扩展现有Employee）
  - employee → Employee（已有）
  - org → Organization（新增）
  - position → Position（新增）
  - hire_source: 招聘来源
  - emergency_contact: 紧急联系人
  - bank_account: 银行账号
  - social_no: 社保账号
  - political_status: 政治面貌
```

**优先级**：P3

### 3.2 考勤管理（新增 app: attendance）

**模型设计**：

```
AttendanceRecord（每日考勤）
  - employee → User
  - date/check_in/check_out
  - work_hours: 时长（自动计算）
  - status: normal/late/early_leave/absent

LeaveRequest（请假申请）
  - employee/leave_type/start_date/end_date
  - hours/reason/attachment
  - status: pending/approved/rejected
  - → ApprovalFlow

OvertimeRecord（加班记录）
  - employee/date/hours/reason
  - is_compensated: 是否已调休

BusinessTrip（出差记录）
  - employee/destination/start_date/end_date
  - purpose → ApprovalFlow
```

**优先级**：P3

### 3.3 合同全生命周期管理（扩展 crm）

**扩展字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| signed_amount | Decimal | 已执行金额 |
| completed_amount | Decimal | 已结算金额 |
| pending_amount | Decimal | 未执行金额（自动=amount-signed） |
| sign_date | Date | 实际签订日期 |
| expire_date | Date | 到期日期 |
| auto_remind_days | Integer | 提前N天提醒（默认30） |
| contract_type | String | 采购/销售/服务/租赁/分包 |
| payment_terms | String | 付款条件 |
| performance_bond | Decimal | 履约保证金 |
| delivery_date | Date | 交付日期 |

**到期提醒**：提前30天/7天/到期当日，三级提醒，推送至飞书/企业微信。

**优先级**：P2

### 3.4 资产管理（扩展 equipment）

```
EquipmentLifecycle（设备生命周期）
  - equipment/event_type: purchase/maintenance/repair/transfer/scrapped
  - event_date/description/cost/operator

EquipmentDepreciation（折旧记录）
  - equipment/date/original_value/depreciation_rate
  - accumulated_depreciation/net_value（自动）
  - method: straight_line/declining/units
```

**优先级**：P3

### 3.5 物资仓储管理（扩展 material）

```
MaterialCategory（物料分类）
  - name/parent: 上级分类（自关联）/description

MaterialInbound（入库记录）
  - material/quantity/unit_price/total_amount（自动）
  - supplier → Supplier/inbound_date/batch_no
  - → ApprovalFlow/operator

MaterialOutbound（出库记录）
  - material/quantity/project/purpose
  - outbound_date/applicant → ApprovalFlow

MaterialPurchaseRequest（采购申请）
  - material_name/quantity/estimated_price
  - supplier → Supplier/expected_date → ApprovalFlow
```

**优先级**：P2

---

## 四、通知系统重构（多通道个人推送）

### 4.1 平台可行性分析

| 平台 | 个人消息推送 | 方式 | 实现难度 |
|------|------------|------|---------|
| **飞书** | ✅ 可以 | 飞书开放平台 Open API，用 Open ID 发消息 | 低（已有经验） |
| **企业微信** | ✅ 可以 | 企业微信应用消息 API，用 UserID 发消息 | 中（需用户绑定企业微信） |
| **QQ** | ✅ 可以 | QQ 开放平台 App，私聊消息 | 中（需用户加机器人为好友） |
| **个人微信** | ❌ 不可能 | 微信不开放个人消息 API | 不可能 |

### 4.2 多通道通知架构

```
业务代码触发（审批/合同到期/库存预警/系统消息）
                ↓
      NotifyService.send(user, subject, content, channels)
                ↓
    ┌─────────────────────────────────────────┐
    │  NotifyChannel 策略模式                  │
    ├──────────────┬──────────────────────────┤
    │  系统通知      │  即时通讯个人推送          │
    │  (DB记录)     │                          │
    │              ├─ 飞书个人推送（Open ID）   │
    │  邮件(SMTP)  ├─ 企业微信个人推送（UserID） │
    │              └─ QQ个人推送（UIN）         │
    └──────────────┴──────────────────────────┘
```

**用户绑定关系**（User 表扩展字段）：

```python
feishu_openid    = models.CharField('飞书OpenID', max_length=64, blank=True)
wechat_userid    = models.CharField('企业微信UserID', max_length=64, blank=True)
qq_number        = models.CharField('QQ号', max_length=20, blank=True)
notify_channels  = models.JSONField('通知渠道偏好', default=list)
# notify_channels 示例: ['system', 'email', 'feishu']
# 用户可在个人设置中选择接收渠道
```

### 4.3 飞书个人消息推送（P1）

**实现方式**：调用飞书开放平台 IM API，通过 Open ID 直接推送消息到用户飞书 app。

**前提条件**：
1. 在[飞书开放平台](https://open.feishu.cn/)创建自建应用
2. 开通权限：`im:message`（发送消息）
3. 用户在系统里绑定飞书账号（个人设置页面填 Open ID）
4. 用户在飞书 app 里授权应用（飞书管理员审批）

**API 端点**：
```
POST https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id
Authorization: Bearer {tenant_access_token}
```

**Python 实现**：

```python
# apps/notifications/channels/feishu_personal.py
import requests
import os
from django.conf import settings

class FeishuPersonalChannel:
    """飞书个人消息推送（非机器人，通过 Open ID 发送）"""

    API_BASE = 'https://open.feishu.cn/open-apis'

    def __init__(self):
        self.app_id = os.environ.get('FEISHU_APP_ID', settings.FEISHU_APP_ID)
        self.app_secret = os.environ.get('FEISHU_APP_SECRET', settings.FEISHU_APP_SECRET)
        self._token = None

    def _get_token(self):
        """获取tenant_access_token"""
        if self._token:
            return self._token
        url = f'{self.API_BASE}/auth/v3/tenant_access_token/internal'
        resp = requests.post(url, json={
            'app_id': self.app_id,
            'app_secret': self.app_secret
        }, timeout=10)
        resp.raise_for_status()
        self._token = resp.json().get('tenant_access_token')
        return self._token

    def send(self, user, subject, content):
        """
        发送飞书个人消息
        user: User 模型实例，user.feishu_openid 必须有值
        subject: 消息标题（用于通知摘要）
        content: 消息内容
        """
        if not user.feishu_openid:
            return False, '用户未绑定飞书账号'

        try:
            token = self._get_token()
            url = f'{self.API_BASE}/im/v1/messages?receive_id_type=open_id'
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }

            # 支持富文本消息卡片
            payload = {
                'receive_id': user.feishu_openid,
                'msg_type': 'interactive',
                'content': json.dumps({
                    'tag': 'text',
                    'text': f'【{subject}】\n{content}'
                })
            }

            resp = requests.post(url, headers=headers, json=payload, timeout=15)
            result = resp.json()

            if result.get('code') == 0:
                return True, result.get('message_id')
            else:
                return False, f"飞书API错误: {result.get('msg')}"

        except Exception as e:
            return False, str(e)
```

**用户绑定流程**：
1. 管理员在飞书开放平台获取应用的 App ID + App Secret
2. 在系统设置（.env 或 SystemSetting）配置 `FEISHU_APP_ID` / `FEISHU_APP_SECRET`
3. 用户在个人设置页面输入自己的飞书 Open ID（可在飞书「我的账号」里查看）
4. 或：管理员后台批量导入用户飞书 Open ID

**Open ID 获取方式**：
- 用户打开飞书 → 点击头像 → 我的账号 → 复制 Open ID
- 或：通过飞书管理后台批量导出用户的 Open ID

### 4.4 企业微信个人推送（P1）

**实现方式**：调用企业微信应用消息 API，通过 UserID 推送消息到用户企业微信。

**前提条件**：
1. 企业管理员在企业微信后台创建自建应用
2. 开通「应用消息」权限
3. 用户在系统里绑定企业微信账号（UserID）
4. 用户需安装企业微信（手机/PC都支持）

**Python 实现**：

```python
# apps/notifications/channels/wechat_work_personal.py
import requests
import os
from django.conf import settings

class WeChatWorkPersonalChannel:
    """企业微信个人消息推送（通过 UserID 发送，应用消息）"""

    API_BASE = 'https://qyapi.weixin.qq.com/cgi-bin'

    def __init__(self):
        self.corp_id = os.environ.get('WECHAT_WORK_CORP_ID', settings.WECHAT_WORK_CORP_ID)
        self.corp_secret = os.environ.get('WECHAT_WORK_CORP_SECRET', settings.WECHAT_WORK_CORP_SECRET)
        self.agent_id = os.environ.get('WECHAT_WORK_AGENT_ID', settings.WECHAT_WORK_AGENT_ID)
        self._token = None

    def _get_token(self):
        """获取access_token"""
        if self._token:
            return self._token
        url = f'{self.API_BASE}/gettoken'
        resp = requests.get(url, params={
            'corpid': self.corp_id,
            'corpsecret': self.corp_secret
        }, timeout=10)
        resp.raise_for_status()
        result = resp.json()
        if result.get('errcode') != 0:
            raise Exception(f"获取token失败: {result.get('errmsg')}")
        self._token = result.get('access_token')
        return self._token

    def send(self, user, subject, content):
        """
        发送企业微信个人消息
        user: User 模型实例，user.wechat_userid 必须有值
        """
        if not user.wechat_userid:
            return False, '用户未绑定企业微信账号'

        try:
            token = self._token or self._get_token()
            url = f'{self.API_BASE}/message/send'
            payload = {
                'touser': user.wechat_userid,
                'msgtype': 'text',
                'agentid': int(self.agent_id),
                'text': {
                    'content': f'【{subject}】\n{content}'
                }
            }

            resp = requests.post(url, params={'access_token': token},
                               json=payload, timeout=15)
            result = resp.json()

            if result.get('errcode') == 0:
                return True, 'ok'
            else:
                return False, f"企业微信API错误: {result.get('errmsg')}"

        except Exception as e:
            return False, str(e)
```

**用户绑定**：
- 企业微信的 UserID 由企业管理员在后台获取
- 用户在系统个人设置中填写自己的企业微信 UserID

### 4.5 QQ 个人消息推送（P1）

**实现方式**：通过 QQ 开放平台「QQ 机器人」发送私聊消息。

**前提条件**：
1. 在 [QQ 开放平台](https://q.qq.com/) 创建应用（选择「QQ 机器人」类型）
2. 获得 App ID + App Token
3. 用户主动添加机器人为好友
4. 机器人调用 `/v1/private_msg` API 发送私聊

**Python 实现**：

```python
# apps/notifications/channels/qq_personal.py
import requests
import os
from django.conf import settings

class QQPersonalChannel:
    """QQ 个人消息推送（通过 QQ 机器人发送私聊）"""

    def __init__(self):
        self.app_id = os.environ.get('QQ_APP_ID', settings.QQ_APP_ID)
        self.token = os.environ.get('QQ_BOT_TOKEN', settings.QQ_BOT_TOKEN)
        # QQ 机器人 API 地址（基于 go-cqhttp 或 Lagrange 部署）
        self.api_base = os.environ.get('QQ_BOT_API', settings.QQ_BOT_API)

    def send(self, user, subject, content):
        """
        发送QQ私聊消息
        user: User 模型实例，user.qq_number 必须有值
        """
        if not user.qq_number:
            return False, '用户未绑定QQ号'

        try:
            url = f'{self.api_base}/send_private_msg'
            payload = {
                'user_id': int(user.qq_number),
                'message': f'【{subject}】\n{content}'
            }
            headers = {
                'Authorization': f'Bearer {self.token}'
            }

            resp = requests.post(url, json=payload, headers=headers, timeout=15)
            result = resp.json()

            if result.get('retcode') == 0:
                return True, 'ok'
            else:
                return False, f"QQ机器人API错误: {result.get('wording', 'unknown')}"

        except Exception as e:
            return False, str(e)
```

**部署架构**：
```
Django 系统 ──→ QQ 机器人 API（go-cqhttp / Lagrange ONEBot）
                      │
                      └──→ 用户的 QQ 号（私聊消息）
```

- 推荐部署 [Lagrange Core](https://github.com/LagrangeDev/Lagrange.Core)（纯 C# 实现，更稳定）
- 或 [go-cqhttp](https://github.com/Mrs4s/go-cqhttp)（Go 实现）
- 部署在同台服务器或内网，通过 HTTP API 调用

### 4.6 统一通知服务（NotifyService）

```python
# apps/notifications/services.py
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

class NotifyService:
    """
    统一通知服务
    通过策略模式支持多通道发送，用户按偏好选择渠道
    """

    def __init__(self):
        from .channels.system import SystemChannel
        from .channels.email import EmailChannel
        from .channels.feishu_personal import FeishuPersonalChannel
        from .channels.wechat_work_personal import WeChatWorkPersonalChannel
        from .channels.qq_personal import QQPersonalChannel

        self.channels = {
            'system': SystemChannel(),       # DB记录（始终执行）
            'email': EmailChannel(),         # SMTP邮件
            'feishu': FeishuPersonalChannel(),      # 飞书个人
            'wechat': WeChatWorkPersonalChannel(),  # 企业微信个人
            'qq': QQPersonalChannel(),              # QQ个人
        }

    def send(self, user, subject: str, content: str,
             channels: Optional[List[str]] = None,
             force_channels: bool = False):
        """
        发送通知

        参数:
            user: User 模型实例
            subject: 通知标题
            content: 通知内容
            channels: 指定渠道列表，如 ['system', 'email', 'feishu']
                      None = 使用用户偏好（user.notify_channels）
            force_channels: True = 忽略用户偏好，强制使用 channels
        """
        # 确定使用哪些渠道
        if channels and force_channels:
            active_channels = channels
        elif channels:
            active_channels = channels
        else:
            active_channels = user.notify_channels or ['system']

        # 系统通知始终记录
        if 'system' not in active_channels:
            active_channels = ['system'] + active_channels

        errors = []
        for ch in active_channels:
            channel = self.channels.get(ch)
            if not channel:
                continue
            try:
                ok, msg = channel.send(user, subject, content)
                if not ok:
                    errors.append(f'[{ch}]: {msg}')
                logger.info(f'通知发送结果 [{ch}] user={user.id} ok={ok} msg={msg}')
            except Exception as e:
                errors.append(f'[{ch}]: {str(e)}')
                logger.exception(f'通知发送异常 [{ch}]')

        return errors if errors else None

    # ─── 业务专用方法 ───

    def send_approval_notice(self, approval_flow, action: str):
        """审批通知：自动推送给相关人"""
        subject = '审批通知'
        content = f'您的审批「{approval_flow.title}」已被{action}'
        recipients = [approval_flow.requester]
        for node in approval_flow.nodes.filter(status='pending', approver__isnull=False):
            if node.approver:
                recipients.append(node.approver)

        for user in set(recipients):
            self.send(user, subject, content)

    def send_contract_expiry(self, contract, days_left: int):
        """合同到期提醒"""
        subject = '合同到期提醒'
        content = (f'合同「{contract.name}」（编号：{contract.contract_no}）'
                   f'还有 {days_left} 天到期，请及时处理。')
        self.send(contract.owner, subject, content,
                 channels=['system', 'email', 'feishu'])

    def send_equipment_warranty(self, equipment, days_left: int):
        """设备保修到期提醒"""
        subject = '设备保修到期提醒'
        content = f'设备「{equipment.name}」（编号：{equipment.code}）还有 {days_left} 天过保，请注意。'
        # 推送给设备管理员（暂定owner）
        self.send(equipment.owner, subject, content,
                 channels=['system', 'email', 'feishu'])

    def send_material_alert(self, material, current_stock: float):
        """物料库存预警"""
        subject = '物料库存预警'
        content = (f'物料「{material.name}」（编号：{material.code}）'
                   f'当前库存 {current_stock}，低于预警值 {material.alert_threshold}，请及时补充。')
        self.send(material.manager or material.owner, subject, content,
                 channels=['system', 'email', 'feishu'])
```

**用户通知偏好设置页面**：

```python
# apps/core/views.py - UserNotificationSettingsViewSet
class UserNotificationSettingsViewSet(ViewSet):
    """用户通知偏好设置"""

    @action(detail=False, methods=['get', 'put'])
    def settings(self, request):
        user = request.user
        if request.method == 'GET':
            return Response({
                'notify_channels': user.notify_channels or ['system', 'email'],
                'feishu_openid': user.feishu_openid or '',
                'wechat_userid': user.wechat_userid or '',
                'qq_number': user.qq_number or '',
            })
        elif request.method == 'PUT':
            data = request.data
            user.notify_channels = data.get('notify_channels', ['system', 'email'])
            user.feishu_openid = data.get('feishu_openid', '').strip()
            user.wechat_userid = data.get('wechat_userid', '').strip()
            user.qq_number = data.get('qq_number', '').strip()
            user.save()
            return Response({'status': 'ok'})
```

### 4.7 消息模板（MessageCard 富文本）

飞书支持 MessageCard 格式，比纯文本更美观：

```python
def build_feishu_card(subject, content, action_url=None):
    """构建飞书 MessageCard"""
    card = {
        'msg_type': 'interactive',
        'card': {
            'header': {
                'title': {'tag': 'plain_text', 'content': subject},
                'template': 'red'  # 或 blue/green/gray
            },
            'elements': [
                {'tag': 'div', 'text': {'tag': 'lark_md', 'content': content}}
            ]
        }
    }
    if action_url:
        card['card']['elements'].append({
            'tag': 'action',
            'actions': [{
                'tag': 'link',
                'text': {'tag': 'plain_text', 'content': '查看详情'},
                'url': action_url
            }]
        })
    return json.dumps(card)
```

---

## 五、文件预览功能

### 5.1 支持预览格式

| 类型 | 格式 | 预览方案 |
|------|------|---------|
| 图片 | JPG/PNG/GIF/BMP/WebP | `<img src="...">` |
| PDF | PDF | PDF.js 内嵌预览 |
| Word | DOC/DOCX | docx-preview 前端预览 |
| Excel | XLS/XLSX | SheetJS/xlsx 前端预览 |
| PowerPoint | PPT/PPTX | 转PDF或前端预览 |
| 文本 | TXT/JSON/CSV/MD | `<pre>` 或 CodeMirror |
| 视频 | MP4/AVI/MOV | HTML5 `<video>` |
| 音频 | MP3/WAV | HTML5 `<audio>` |
| 其他 | ZIP/RAR 等 | **不预览，只下载** |

### 5.2 预览 API

```python
# apps/files/views.py CompanyFileViewSet

@action(detail=True, methods=['get'])
def preview(self, request, pk=None):
    """获取文件预览信息"""
    f = self.get_object()
    ext = f.file_name.rsplit('.', 1)[-1].lower()

    preview_map = {
        'jpg': 'image', 'jpeg': 'image', 'png': 'image',
        'gif': 'image', 'bmp': 'image', 'webp': 'image',
        'pdf': 'pdf',
        'doc': 'word', 'docx': 'word',
        'xls': 'excel', 'xlsx': 'excel',
        'ppt': 'ppt', 'pptx': 'ppt',
        'txt': 'text', 'json': 'text', 'csv': 'text', 'md': 'text',
        'mp4': 'video', 'avi': 'video', 'mov': 'video',
        'mp3': 'audio', 'wav': 'audio', 'ogg': 'audio',
    }

    return Response({
        'preview_type': preview_map.get(ext),
        'file_url': request.build_absolute_uri(f.file.url),
        'file_name': f.file_name,
        'file_size': f.file_size,
        'is_previewable': ext in preview_map
    })

@action(detail=True, methods=['get'])
def download(self, request, pk=None):
    """下载文件"""
    f = self.get_object()
    return FileResponse(
        f.file.open('rb'),
        as_attachment=True,
        filename=f.file_name
    )
```

### 5.3 前端预览页面

```html
<!-- templates/files/file_preview.html -->
<div id="preview-container" class="container mt-4">
  <h4>{{ file_name }}</h4>

  <!-- 图片 -->
  <img v-if="preview_type === 'image'" :src="file_url" class="img-fluid" />

  <!-- PDF -->
  <iframe v-else-if="preview_type === 'pdf'" :src="pdfjsUrl" class="w-100" style="height:85vh;border:none;" />

  <!-- Word -->
  <div v-else-if="preview_type === 'word'">
    <div id="word-container" style="height:85vh;overflow:auto;"></div>
  </div>

  <!-- Excel -->
  <div v-else-if="preview_type === 'excel'">
    <div id="excel-container" style="height:85vh;overflow:auto;"></div>
  </div>

  <!-- 视频 -->
  <video v-else-if="preview_type === 'video'" :src="file_url" controls class="w-100"></video>

  <!-- 音频 -->
  <audio v-else-if="preview_type === 'audio'" :src="file_url" controls class="w-100 mt-3"></audio>

  <!-- 文本 -->
  <pre v-else-if="preview_type === 'text'" class="bg-light p-3" style="max-height:85vh;overflow:auto;">{{ text_content }}</pre>

  <!-- 不支持 -->
  <div v-else class="alert alert-info">
    <p>该文件类型不支持在线预览</p>
    <a :href="file_url" class="btn btn-primary" download>下载文件</a>
  </div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/docx-preview@0.1.20/dist/docx-preview.js"></script>
<script src="https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js"></script>
```

---

## 六、模块化设计方案

### 6.1 分层架构

```
┌─────────────────────────────────────────────┐
│              通用基础层（所有系统可用）          │
├─────────────────────────────────────────────┤
│  core           │ 用户/角色/权限/通知          │
│  files          │ 文件管理/预览/版本控制       │
│  notifications  │ 多通道通知服务               │
├─────────────────────────────────────────────┤
│              企业业务层（企业管理系统标配）        │
├─────────────────────────────────────────────┤
│  org            │ 组织架构/岗位/员工档案        │
│  attendance     │ 考勤/请假/加班/出差          │
│  finance        │ 工资/社保/报销/发票          │
├─────────────────────────────────────────────┤
│              业务扩展层（行业定制）              │
├─────────────────────────────────────────────┤
│  projects       │ 项目管理（工程/IT/咨询）      │
│  crm            │ 客户/供应商/合同             │
│  material       │ 物资/采购/仓储               │
│  equipment      │ 设备/维修/折旧              │
│  approvals      │ 审批流引擎（通用）           │
└─────────────────────────────────────────────┘
```

### 6.2 可复用模块清单

| 模块 | 功能 | 可复用系统 |
|------|------|---------|
| `enterprise-core` | User+Role+Permission+Notification+Org | 任何系统 |
| `enterprise-files` | 文件上传/预览/版本/分类 | 任何系统 |
| `enterprise-approval` | 可视化审批流引擎 | OA/ERP/项目管理系统 |
| `enterprise-attendance` | 考勤+请假+加班 | HR系统 |
| `enterprise-finance` | 工资/社保/报销/发票 | 任何有财务的系统 |
| `enterprise-crm` | 客户/供应商/合同 | B2B业务系统 |
| `enterprise-inventory` | 物资/采购/仓储 | 零售/仓储/制造系统 |
| `enterprise-asset` | 设备/资产/折旧 | 资产管理系统 |

### 6.3 模块依赖关系

```
notifications（通知服务）
       ↑
    core ← org ← attendance
    ↑
  finance（工资需要org组织架构）
    ↑
  crm ← projects ← tasks（合同关联项目）
    ↑
  material ← inventory（物资关联采购）
    ↑
  equipment ← assets（设备关联维修）

所有业务模块依赖：
  core（认证/权限/通知）
  files（文件存储）
  approvals（审批流）
```

---

## 七、执行计划

### 阶段一：P0 修复（1-2天）

```
1. P0-1: Invoice.tax_amount 自动计算
2. P0-2: Expense date/expense_date 冗余字段统一
3. P0-3: 审批超时 cron 集成
4. P0-4: ApprovalFlow 加 company 字段
5. P0-5: Notification ViewSet
6. P0-6~9: admin.py 补全（CRM/物料/文件/设备）
7. P0-10: 工资权限码初始化
```

### 阶段二：通知系统（2-3天）

```
1. User 表加 notify_channels / feishu_openid / wechat_userid / qq_number 字段
2. 新建 apps/notifications/channels/ 目录
   - system.py（DB记录）
   - email.py（SMTP）
   - feishu_personal.py（飞书个人推送）
   - wechat_work_personal.py（企业微信个人推送）
   - qq_personal.py（QQ个人推送）
3. 新建 apps/notifications/services.py（NotifyService）
4. 新建个人设置页面（通知偏好 + openid 绑定）
5. 集成 cron 任务：合同到期/设备保修/物料预警 → NotifyService
6. 审批通知 → NotifyService
```

### 阶段三：P1 功能（2-3天）

```
1. Project.progress 自动同步
2. Task 自动编号
3. CRM import_records
4. 文件预览（API + 前端模板）
5. 驳回重审 resubmit 链路
6. check_alerts 进 crontab
```

### 阶段四：P2 功能（3-4天）

```
1. Contract 执行进度字段
2. Material total_value 库存金额
3. MaterialUsageLogViewSet
4. Equipment serial_number 校验
5. 文件版本自动递增
6. 文件下载 API
7. check_contract_expiry / check_warranty_expiry / check_material_alerts cron
```

### 阶段五：P3 新模块（后续迭代）

```
1. 组织架构 org app
2. 考勤 attendance app
3. 物资全链路
4. 设备折旧计算
```

---

## 八、技术债务

| # | 问题 | 清理方案 |
|---|------|---------|
| 1 | 旧 Dockerfile/docker-compose（根目录） | 确认引用关系后删除 |
| 2 | settings.py DEBUG=True 硬编码 | 改为环境变量 |
| 3 | gunicorn workers=2 偏低 | 建议改为 4 |
| 4 | 无 API 限流 | 添加 django-ratelimit |
| 5 | crontab 散落管理 | 建议 django-cron 集中管理 |

---

*本需求报告为商业版 v1.0 制定，后续迭代根据用户反馈调整。*
