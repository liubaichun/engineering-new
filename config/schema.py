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
    'reject_to_requester': '驳回申请人',
    'approve_node': '审批通过节点',
    'reject_node': '驳回节点',
    'approve_batch': '批量审批',
    'submit': '提交审批',
    'withdraw': '撤回审批',
    'delegate': '委托审批',
    'transfer': '转交审批',
    'urge': '催办审批',
    'cancel': '取消审批',
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
    'employees': '员工',
    'clients': '客户', 'suppliers': '供应商', 'contracts': '合同',
    'sources': '客户来源',
    'flows': '审批流', 'nodes': '审批节点', 'templates': '审批模板',
    'channels': '通知渠道', 'bindings': '通知绑定',
    'equipment': '设备', 'material': '物料',
    'categories': '分类', 'files': '文件',
}


def _resource_label(path: str) -> str:
    """从URL路径提取资源中文名称（排除末尾 action 片段）"""
    segments = [s for s in path.strip('/').split('/') if s]
    if not segments:
        return path

    # 过滤掉 {id} 等路径参数
    segments = [s for s in segments if not re.match(r'^\{[^}]+\}$', s)]
    if not segments:
        return path

    # 如果最后一段是 action，回退到前一段（用于 /flows/{id}/approve 等场景）
    if segments[-1] in ACTION_SUMMARY_MAP:
        if len(segments) >= 2:
            segments = segments[:-1]

    last = re.sub(r'\{[^}]+\}', '', segments[-1])  # 去掉嵌入的 {xxx}
    return RESOURCE_LABEL_MAP.get(last, last)


def _custom_action_in_path(path: str) -> str:
    """从URL路径中检测真正的嵌套自定义动作（approve, reject, export 等，非标准HTTP方法）"""
    segments = [s for s in path.strip('/').split('/') if s]
    http_methods = {'list', 'retrieve', 'create', 'update', 'partial_update', 'destroy',
                    'get', 'post', 'put', 'patch', 'delete', 'options', 'head'}
    for seg in segments:
        seg = re.sub(r'\{[^}]+\}', '', seg)  # 去掉 {id} 等
        if seg in ACTION_SUMMARY_MAP and seg not in http_methods:
            return ACTION_SUMMARY_MAP[seg]
    return None


def _build_summary(method: str, operation: dict, resource: str, path: str = '') -> str:
    """根据method、operationId和URL路径构建中文summary"""
    # 1. 在 operationId 中搜索最长匹配的 action
    #    逻辑：先尝试 n-gram 组合（如 reject_to_requester），再尝试单段匹配
    operation_id = operation.get('operationId', '')
    if operation_id:
        sorted_actions = sorted(ACTION_SUMMARY_MAP.keys(), key=lambda x: len(x), reverse=True)
        http_like = {'list', 'retrieve', 'create', 'update', 'partial_update', 'destroy',
                     'get', 'post', 'put', 'patch', 'delete', 'options', 'head'}
        parts = operation_id.split('_')

        # 1a. n-gram 组合优先（如 reject_to_requester，跨多个 _ 片段）
        n = len(parts)
        for act in sorted_actions:
            if act in http_like:
                continue
            for start in range(n):
                for end in range(start + 1, n + 1):
                    if '_'.join(parts[start:end]) == act:
                        action = ACTION_SUMMARY_MAP[act]
                        if resource and action.endswith(resource):
                            return action
                        return f"{action}{resource}"

        # 1b. 单段 action（如 approve, reject, monthly）
        for act in sorted_actions:
            if act in http_like:
                continue
            if act in parts:
                action = ACTION_SUMMARY_MAP[act]
                if resource and action.endswith(resource):
                    return action
                return f"{action}{resource}"

    # 2. 从URL路径检测嵌套自定义动作（operationId 搞不定的边缘情况）
    if path:
        custom_action = _custom_action_in_path(path)
        if custom_action:
            if resource and custom_action.endswith(resource):
                return custom_action
            return f"{custom_action}{resource}"

    # 3. 从自定义action字段推导
    action = operation.get('action', '')
    if action in ACTION_SUMMARY_MAP:
        return f"{ACTION_SUMMARY_MAP[action]}{resource}"

    # 4. 回退到HTTP方法
    method_map = {'get': '获取', 'post': '创建', 'put': '完整更新', 'patch': '部分更新', 'delete': '删除'}
    method_label = method_map.get(method.lower(), method.upper())
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
                summary = _build_summary(method, operation, resource, path)
                operation['summary'] = summary
                modified += 1

    except Exception:
        import sys
        sys.stderr.write("[autogenerate_chinese_summary hook] error, skipping\n")
        import traceback
        traceback.print_exc(file=sys.stderr)

    return result
