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
    # Custom actions
    'approve': '审批通过',
    'reject': '审批拒绝',
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


# 资源名 → 中文映射（按URL路径最后一段）
RESOURCE_LABEL_MAP = {
    'users': '用户', 'roles': '角色', 'permissions': '权限',
    'companies': '公司', 'settings': '设置',
    'login-logs': '登录日志', 'operation-audit-logs': '操作日志',
    'operation-audits': '操作审计',
    'notifications': '通知', 'user-roles': '用户角色', 'role-permissions': '角色权限',
    'projects': '项目', 'tasks': '任务',
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


def _resource_label(path: str) -> str:
    """从URL路径提取资源中文名称"""
    segments = [s for s in path.strip('/').split('/') if s]
    if not segments:
        return path
    last = re.sub(r'\d+.*', '', segments[-1])  # 去掉末尾的数字ID
    return RESOURCE_LABEL_MAP.get(last, last)


def _build_summary(method: str, operation: dict, resource: str) -> str:
    """根据method和operationId构建中文summary"""
    method_map = {'get': '获取', 'post': '创建', 'put': '完整更新', 'patch': '部分更新', 'delete': '删除'}
    method_label = method_map.get(method.lower(), method.upper())

    # 从operationId推导动作: "ContractViewSet_list" → list
    operation_id = operation.get('operationId', '')
    if operation_id:
        parts = re.split(r'[_\.]', operation_id)
        if len(parts) > 1:
            # 处理 compound actions: partial_update
            if parts[1] in ('partial', 'partial_update'):
                action = 'partial_update'
            else:
                action = parts[1]
            if action in ACTION_SUMMARY_MAP:
                return f"{ACTION_SUMMARY_MAP[action]}{resource}"

    # 从自定义action推导
    action = operation.get('action', '')
    if action in ACTION_SUMMARY_MAP:
        return f"{ACTION_SUMMARY_MAP[action]}{resource}"

    # 回退到HTTP方法
    return f"{method_label}{resource}"


def autogenerate_chinese_summary(result, generator, **kwargs):
    """
    drf-spectacular POSTPROCESSING_HOOK。
    为所有缺少 summary 的端点自动生成中文摘要。

    result: dict — 包含 'paths', 'components' 等的 OpenAPI schema 字典
    generator: SchemaGenerator 实例
    """
    try:
        paths = result.get('paths', {})
        if not isinstance(paths, dict):
            return result  # 结构异常，保底返回

        modified = 0
        for path, methods in paths.items():
            if not isinstance(methods, dict):
                continue
            for method, operation in methods.items():
                if not isinstance(operation, dict):
                    continue
                if operation.get('summary'):
                    continue  # 已有summary，跳过

                resource = _resource_label(path)
                summary = _build_summary(method, operation, resource)
                operation['summary'] = summary
                modified += 1

    except Exception:
        import sys
        sys.stderr.write("[autogenerate_chinese_summary hook] error, skipping\n")
        import traceback
        traceback.print_exc(file=sys.stderr)

    return result
