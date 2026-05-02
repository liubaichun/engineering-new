"""
drf-spectacular postprocessing hooks for GREEN enterprise system.
Auto-generates Chinese summaries for all API endpoints that lack them.
"""
import re


# 动作名 → 中文映射
ACTION_SUMMARY_MAP = {
    # DRF stock actions
    'list': '列表',
    'retrieve': '详情',
    'create': '新建',
    'update': '更新',
    'partial_update': '部分更新',
    'destroy': '删除',
    # HTTP methods
    'get': '获取',
    'post': '创建',
    'put': '完整更新',
    'patch': '部分更新',
    'delete': '删除',
    # Custom actions (sorted by prefix)
    'approve': '审批通过',
    'reject': '审批拒绝',
    'bind': '绑定',
    'unbind': '解绑',
    'test': '测试',
    'my_bindings': '我的绑定',
    'active': '可用列表',
    'export': '导出',
    'import': '导入',
    'monthly': '月度报表',
    'yearly': '年度报表',
    'wage_summary': '工资汇总',
    'invoice_summary': '发票汇总',
    'balance_sheet': '资产负债表',
    'unread_count': '未读数量',
    'toggle': '切换',
    'all_settings': '全部设置',
    'types': '类型列表',
    'stock_alerts': '库存预警',
}


def _translate_action(action: str) -> str:
    """Translate an action name to Chinese."""
    return ACTION_SUMMARY_MAP.get(action, action)


def _resource_label(path: str) -> str:
    """Extract a human-readable resource label from path."""
    # /api/tasks/projects/ → 项目
    # /api/finance/incomes/ → 收入
    resource_map = {
        'users': '用户', 'roles': '角色', 'permissions': '权限',
        'companies': '公司', 'settings': '设置',
        'login-logs': '登录日志', 'operation-audit-logs': '操作日志',
        'notifications': '通知', 'operation-audits': '操作审计',
        'user-roles': '用户角色', 'role-permissions': '角色权限',
        'projects': '项目', 'tasks': '任务', 'stages': '阶段',
        'flow-templates': '审批模板', 'flow-nodes': '审批节点',
        'flow-instances': '审批实例', 'flow-transitions': '审批流转',
        'stage-instances': '阶段实例', 'stage-activities': '阶段活动',
        'incomes': '收入', 'expenses': '支出', 'invoices': '发票',
        'wages': '工资', 'ar-ap': '应收应付', 'reports': '报表',
        'social-configs': '社保配置', 'employee-companies': '员工公司',
        'clients': '客户', 'suppliers': '供应商', 'contracts': '合同',
        'sources': '客户来源',
        'flows': '审批流', 'nodes': '审批节点', 'templates': '审批模板',
        'channels': '通知渠道', 'bindings': '通知绑定',
        'equipment': '设备', 'material': '物料',
        'categories': '分类', 'files': '文件',
    }
    # Extract last non-empty path segment
    segments = [s for s in path.strip('/').split('/') if s]
    if not segments:
        return path
    last = segments[-1]
    # Remove trailing slashes/IDs
    last = re.sub(r'/|\d+.*$', '', last)
    return resource_map.get(last, last)


def autogenerate_chinese_summary(registry, **kwargs):
    """
    drf-spectacular postprocessing hook.
    Auto-fills 'summary' field for all operations that don't have one.
    """
    from drf_spectacular.generators import Generator
    # `registry` is a dict-like: {path: {method: operation_object}}
    for path, methods in registry.items():
        for method, operation in methods.items():
            if 'summary' in operation and operation['summary']:
                continue  # already has summary

            # Build auto-summary from method + resource
            method_label = ACTION_SUMMARY_MAP.get(method.lower(), method.upper())
            action = operation.get('action', '')
            resource = _resource_label(path)

            # Try to derive from operationId first (e.g., "ContractViewSet_retrieve")
            operation_id = operation.get('operationId', '')
            if operation_id:
                # Extract action and model name
                parts = re.split(r'[_\.]', operation_id)
                if len(parts) >= 2:
                    view_name = parts[0]  # e.g., ContractViewSet
                    op_action = parts[1] if len(parts) > 1 else ''

                    if op_action in ACTION_SUMMARY_MAP:
                        summary = f"{_translate_action(op_action)}{resource}"
                    else:
                        summary = f"{_translate_action(op_action)}{resource}" if op_action else f"{method_label}{resource}"
                else:
                    summary = f"{method_label}{resource}"
            elif action in ACTION_SUMMARY_MAP:
                summary = f"{_translate_action(action)}{resource}"
            elif method.lower() in ACTION_SUMMARY_MAP:
                summary = f"{_translate_action(method.lower())}{resource}"
            else:
                summary = f"{method_label} {resource}"

            operation['summary'] = summary

    return registry
