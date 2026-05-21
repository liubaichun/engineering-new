"""
初始化 RBAC 角色权限体系 — 商业化标准预置数据

用法：
    python manage.py init_rbac
    python manage.py init_rbac --force   # 重新初始化（更新现有）

角色（6个）：
    admin        — 系统管理员
    finance      — 财务
    manager      — 部门经理
    hr           — 人事
    staff        — 普通员工
    viewer       — 只读访客

权限分类：
    finance.*  — 财务模块（收入/支出/工资/发票）
    crm.*      — 客户模块（客户/合同/跟进）
    project.*  — 项目模块（项目/任务/看板）
    material.* — 物料模块（入库/出库/库存）
    equipment.* — 设备模块（领用/归还/维修）
    approval.* — 审批模块（审批流/模板）
    system.*   — 系统管理（用户/角色/设置）
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.core.models import Role, Permission, UserRole, RolePermission

User = get_user_model()


PERMISSIONS = [
    # ── 财务 ────────────────────────────────────────────────────────────────
    ('finance', 'income', 'finance:income:read', '查看收入记录'),
    ('finance', 'income', 'finance:income:create', '创建收入记录'),
    ('finance', 'income', 'finance:income:update', '编辑收入记录'),
    ('finance', 'income', 'finance:income:delete', '删除收入记录'),
    ('finance', 'expense', 'finance:expense:read', '查看支出记录'),
    ('finance', 'expense', 'finance:expense:create', '创建支出记录'),
    ('finance', 'expense', 'finance:expense:update', '编辑支出记录'),
    ('finance', 'expense', 'finance:expense:delete', '删除支出记录'),
    ('finance', 'wage', 'finance:wage:read', '查看工资单'),
    ('finance', 'wage', 'finance:wage:create', '创建工资单'),
    ('finance', 'wage', 'finance:wage:update', '编辑工资单'),
    ('finance', 'wage', 'finance:wage:delete', '删除工资单'),
    ('finance', 'wage', 'finance:wage:submit', '提交工资单'),
    ('finance', 'wage', 'finance:wage:approve', '批准工资单'),
    ('finance', 'wage', 'finance:wage:pay', '发放工资'),
    ('finance', 'invoice', 'finance:invoice:read', '查看发票'),
    ('finance', 'invoice', 'finance:invoice:create', '创建发票'),
    ('finance', 'invoice', 'finance:invoice:update', '编辑发票'),
    ('finance', 'invoice', 'finance:invoice:delete', '删除发票'),
    ('finance', 'bank', 'finance:bank:read', '查看银行账户'),
    ('finance', 'bank', 'finance:bank:create', '创建银行账户'),
    ('finance', 'bank', 'finance:bank:update', '编辑银行账户'),
    ('finance', 'bank', 'finance:bank:delete', '删除银行账户'),
    ('finance', 'employee', 'finance:employee:read', '查看员工'),
    ('finance', 'employee', 'finance:employee:create', '创建员工'),
    ('finance', 'employee', 'finance:employee:update', '编辑员工'),
    ('finance', 'employee', 'finance:employee:delete', '删除员工'),
    ('finance', 'company', 'finance:company:read', '查看公司'),
    ('finance', 'company', 'finance:company:create', '创建公司'),
    ('finance', 'company', 'finance:company:update', '编辑公司'),
    ('finance', 'company', 'finance:company:delete', '删除公司'),
    ('finance', 'report', 'finance:report:read', '查看财务报表'),
    # ── CRM ─────────────────────────────────────────────────────────────────
    ('crm', 'customer', 'crm:customer:read', '查看客户'),
    ('crm', 'customer', 'crm:customer:create', '创建客户'),
    ('crm', 'customer', 'crm:customer:update', '编辑客户'),
    ('crm', 'customer', 'crm:customer:delete', '删除客户'),
    ('crm', 'contract', 'crm:contract:read', '查看合同'),
    ('crm', 'contract', 'crm:contract:create', '创建合同'),
    ('crm', 'contract', 'crm:contract:update', '编辑合同'),
    ('crm', 'contract', 'crm:contract:delete', '删除合同'),
    ('crm', 'followup', 'crm:followup:read', '查看跟进'),
    ('crm', 'followup', 'crm:followup:create', '创建跟进'),
    ('crm', 'opportunity', 'crm:opportunity:read', '查看商机'),
    ('crm', 'opportunity', 'crm:opportunity:update', '编辑商机'),
    # ── 项目 ─────────────────────────────────────────────────────────────────
    ('project', 'project', 'project:project:read', '查看项目'),
    ('project', 'project', 'project:project:create', '创建项目'),
    ('project', 'project', 'project:project:update', '编辑项目'),
    ('project', 'project', 'project:project:delete', '删除项目'),
    ('project', 'task', 'project:task:read', '查看任务'),
    ('project', 'task', 'project:task:create', '创建任务'),
    ('project', 'task', 'project:task:update', '编辑任务'),
    ('project', 'task', 'project:task:delete', '删除任务'),
    # ── 物料 ─────────────────────────────────────────────────────────────────
    ('material', 'stock', 'material:stock:read', '查看库存'),
    ('material', 'stock', 'material:stock:update', '管理库存'),
    ('material', 'stock', 'material:stock:delete', '删除库存记录'),
    ('material', 'usage', 'material:usage:read', '查看使用记录'),
    ('material', 'usage', 'material:usage:create', '记录物料使用'),
    # ── 设备 ─────────────────────────────────────────────────────────────────
    ('equipment', 'equipment', 'equipment:equipment:read', '查看设备'),
    ('equipment', 'equipment', 'equipment:equipment:update', '管理设备'),
    ('equipment', 'equipment', 'equipment:equipment:delete', '删除设备'),
    ('equipment', 'equipment', 'equipment:equipment:use', '领用设备'),
    ('equipment', 'equipment', 'equipment:equipment:return', '归还设备'),
    ('equipment', 'equipment', 'equipment:equipment:repair', '报修设备'),
    # ── 审批 ─────────────────────────────────────────────────────────────────
    ('approval', 'flow', 'approval:flow:read', '查看审批流'),
    ('approval', 'flow', 'approval:flow:approve', '审批'),
    ('approval', 'flow', 'approval:flow:update', '编辑审批流'),
    ('approval', 'node', 'approval:node:read', '查看审批节点'),
    ('approval', 'node', 'approval:node:update', '编辑审批节点'),
    ('approval', 'template', 'approval:template:read', '查看审批模板'),
    ('approval', 'template', 'approval:template:manage', '管理审批模板'),
    # ── 系统 ─────────────────────────────────────────────────────────────────
    ('system', 'user', 'system:user:read', '查看用户'),
    ('system', 'user', 'system:user:create', '创建用户'),
    ('system', 'user', 'system:user:update', '编辑用户'),
    ('system', 'user', 'system:user:delete', '删除用户'),
    ('system', 'role', 'system:role:read', '查看角色'),
    ('system', 'role', 'system:role:create', '创建角色'),
    ('system', 'role', 'system:role:update', '编辑角色'),
    ('system', 'role', 'system:role:delete', '删除角色'),
    ('system', 'role', 'system:role:manage', '管理角色权限'),
    ('system', 'setting', 'system:setting:read', '查看系统设置'),
    ('system', 'setting', 'system:setting:update', '编辑系统设置'),
    ('system', 'setting', 'system:setting:manage', '管理系统设置'),
]

ROLE_PERMISSIONS = {
    'admin': [p[2] for p in PERMISSIONS],  # 管理员拥有全部权限
    'finance': [
        'finance:income:read', 'finance:income:create', 'finance:income:update',
        'finance:expense:read', 'finance:expense:create', 'finance:expense:update',
        'finance:wage:read', 'finance:wage:create', 'finance:wage:update',
        'finance:wage:submit', 'finance:wage:approve', 'finance:wage:pay',
        'finance:invoice:read', 'finance:invoice:create', 'finance:invoice:update',
        'finance:report:read',
        'approval:flow:read', 'approval:flow:approve',
        'crm:customer:read',
        'project:project:read',
    ],
    'manager': [
        'finance:income:read', 'finance:expense:read',
        'finance:wage:read', 'finance:report:read',
        'crm:customer:read', 'crm:customer:create', 'crm:contract:read', 'crm:opportunity:read',
        'project:project:read', 'project:project:create', 'project:task:read', 'project:task:create', 'project:task:update',
        'material:stock:read', 'equipment:equipment:read',
        'approval:flow:read', 'approval:flow:approve',
    ],
    'hr': [
        'crm:customer:read', 'crm:followup:read', 'crm:followup:create',
        'finance:wage:read', 'finance:wage:create', 'finance:wage:update',
        'project:project:read', 'project:task:read',
    ],
    'staff': [
        'crm:customer:read',
        'project:project:read', 'project:task:read', 'project:task:create', 'project:task:update',
        'material:stock:read', 'material:usage:create',
        'equipment:equipment:read', 'equipment:equipment:use', 'equipment:equipment:return',
        'approval:flow:read',
    ],
    'viewer': [
        'crm:customer:read',
        'project:project:read', 'project:task:read',
        'material:stock:read',
        'equipment:equipment:read',
        'approval:flow:read',
    ],
}

ROLE_DEFINITIONS = [
    ('admin', '系统管理员', '拥有系统全部权限，可管理所有模块'),
    ('finance', '财务', '财务专员，可处理收入/支出/工资/发票'),
    ('manager', '部门经理', '部门负责人，可审批项目/查看财务数据'),
    ('hr', '人事专员', '人事专员，可管理客户跟进/工资数据'),
    ('staff', '普通员工', '普通员工，可查看/领取任务/设备'),
    ('viewer', '只读访客', '只读权限，可浏览数据但不能修改'),
]


class Command(BaseCommand):
    help = '初始化 RBAC 角色权限体系'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='强制重新初始化（更新现有数据）')

    def handle(self, *args, **options):
        force = options.get('force', False)
        admin_user = User.objects.filter(username='admin').first()

        # 1. 创建所有权限（使用 get_or_create 避免冲突）
        created_perms = 0
        updated_perms = 0
        for category, resource, code, name in PERMISSIONS:
            # action 取 code 的第三段，如 finance:income:create -> create
            action_part = code.rsplit(':', 1)[-1]
            obj, created = Permission.objects.update_or_create(
                code=code,
                defaults={
                    'name': name,
                    'resource': resource,
                    'action': action_part,
                    'category': category,
                    'is_active': True,
                }
            )
            if created:
                created_perms += 1
            else:
                updated_perms += 1
        self.stdout.write(f'权限: 创建 {created_perms}, 更新 {updated_perms}')

        # 2. 创建所有角色
        created_roles = 0
        for code, name, desc in ROLE_DEFINITIONS:
            role, created = Role.objects.get_or_create(
                code=code,
                defaults={'name': name, 'description': desc, 'is_active': True}
            )
            if created:
                created_roles += 1
            # 清空旧权限，重新绑定（--force 时）
            if force:
                RolePermission.objects.filter(role=role).delete()
            # 绑定权限
            perm_codes = ROLE_PERMISSIONS.get(code, [])
            for pcode in perm_codes:
                try:
                    perm = Permission.objects.get(code=pcode)
                    RolePermission.objects.get_or_create(role=role, permission=perm)
                except Permission.DoesNotExist:
                    pass
            # 给 admin 用户分配 admin 角色
            if code == 'admin' and admin_user:
                UserRole.objects.get_or_create(user=admin_user, role=role)
                admin_user.role = 'admin'
                admin_user.save(update_fields=['role'])

        self.stdout.write(f'角色: 创建/更新 {created_roles} 个，绑定权限到各角色')
        self.stdout.write(self.style.SUCCESS('\n✅ RBAC 初始化完成'))
        self.stdout.write(f'\n角色列表:')
        for code, name, _ in ROLE_DEFINITIONS:
            role = Role.objects.get(code=code)
            perm_count = role.permissions.count()
            user_count = role.userrole_set.count()
            self.stdout.write(f'  {code:10s} {name} — 权限 {perm_count} 个，用户 {user_count} 人')

        self.stdout.write(f'\n当前用户角色:')
        for u in User.objects.filter(is_active=True):
            roles = list(u.user_roles.values_list('role__code', flat=True))
            print(f'  {u.username}: {roles or [u.role or "无"]}')
