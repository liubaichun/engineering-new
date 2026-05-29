from rest_framework.throttling import UserRateThrottle


class StaffRateThrottle(UserRateThrottle):
    """员工角色专用限流：每分钟600次"""

    scope = 'staff'


class ExportRateThrottle(UserRateThrottle):
    """导出操作专用限流：每分钟20次"""

    scope = 'exports'
