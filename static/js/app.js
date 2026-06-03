/* ================================================================
   GREEN ERP — 全局应用 JavaScript
   提取自 templates/base.html，2026-05-28
   ================================================================ */

// ── iframe 自动隐藏侧边栏 ─────────────────────────
(function() {
    if (window.self !== window.top) {
        var style = document.createElement('style');
        style.id = 'iframe-hide-sidebar';
        style.textContent = 'nav.sidebar,.sidebar,nav.bottom-tabs,.bottom-tabs{display:none!important;}main.main-content,div.main-content{margin-left:0!important;}';
        document.head.appendChild(style);
    }
})();

// ── 全局权限管理 ──────────────────────────────────
(function() {
    var original = window.UserPermissionManager;
    window.UserPermissionManager = {
        USER_PERMS: { codes: [], menu_codes: [], is_superuser: false },
        permsLoaded: false,

        loadPermissions: function() {
            var self = this;
            fetchWithTimeout('/api/core/auth/user/my-permissions/', { credentials: 'include' }, 5000)
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    if (data.status === 'success') {
                        self.USER_PERMS.codes = data.codes || [];
                        self.USER_PERMS.menu_codes = data.menu_codes || [];
                        self.USER_PERMS.is_superuser = data.is_superuser || false;
                        window.__userId = data.user_id || null;
                        window.__isSuperuserKnown = true;
                        window.__userIsSuperuser = data.is_superuser || false;
                        self.hideUnauthorizedButtons();
                    }
                    self.permsLoaded = true;
                })
                .catch(function() { self.permsLoaded = true; });
        },

        hasPermission: function(permCode) {
            if (!permCode) return true;
            if (this.USER_PERMS.is_superuser) return true;
            var codes = this.USER_PERMS.codes || [];
            // 超级用户标记 '*' 放行所有
            if (codes.length === 1 && codes[0] === '*') return true;
            // 兼容 .add↔.create、.remove↔.delete、.change↔.update 写法
            if (!codes.includes(permCode)) {
                var altCode = permCode.replace('.add', '.create').replace('.create', '.add')
                                       .replace('.remove', '.delete').replace('.delete', '.remove')
                                       .replace('.change', '.update').replace('.update', '.change');
                if (altCode !== permCode) return codes.includes(altCode);
            }
            return codes.includes(permCode);
        },

        hideUnauthorizedButtons: function() {
            document.querySelectorAll('[data-perm]').forEach(function(el) {
                var perms = el.getAttribute('data-perm').split(',').map(function(p) { return p.trim(); });
                var allowed = perms.some(function(p) { return this.hasPermission(p); }.bind(this));
                if (!allowed) {
                    el.style.display = 'none';
                }
            }.bind(this));
        },

        waitForPermissions: function(callback) {
            // 已知is_superuser，直接放行（无需等待API）
            if (window.__isSuperuserKnown && window.__userIsSuperuser) {
                callback();
                return;
            }
            // 如果已有权限数据，直接回调
            if (this.USER_PERMS.codes && this.USER_PERMS.codes.length > 0) {
                callback();
                return;
            }
            // 如果 is_superuser，直接回调
            if (this.USER_PERMS.is_superuser) {
                window.__isSuperuserKnown = true;
                window.__userIsSuperuser = true;
                callback();
                return;
            }
            // 标记is_superuser未知，等API返回后决定
            window.__isSuperuserKnown = false;
            // 非superuser才等待API权限数据
            var attempts = 0;
            var interval = setInterval(function() {
                attempts++;
                if (this.permsLoaded) {
                    clearInterval(interval);
                    if (this.USER_PERMS.is_superuser) {
                        window.__isSuperuserKnown = true;
                        window.__userIsSuperuser = true;
                    } else {
                        window.__isSuperuserKnown = true;
                        window.__userIsSuperuser = false;
                    }
                    callback();
                } else if (attempts >= 100) { // 最多10秒
                    clearInterval(interval);
                    window.__isSuperuserKnown = true;
                    window.__userIsSuperuser = false;
                    callback();
                }
            }.bind(this), 100);
        }
    };

    // Restore original if it existed
    if (original) {
        for (var key in original) {
            if (original.hasOwnProperty(key) && !window.UserPermissionManager.hasOwnProperty(key)) {
                window.UserPermissionManager[key] = original[key];
            }
        }
    }
})();

// ── 页面初始化 ────────────────────────────────────
var pm = window.UserPermissionManager;

document.addEventListener('DOMContentLoaded', function() {
    // 检查是否已登录（改进：不因 API 临时故障跳登录）
    // 原则：真正的认证校验在 Django 中间件和服务端做，
    // 前端 checkAuth 仅作辅助判断。API 失败时静默降级，
    // 不 redirect 到 /login/（避免瞬断导致用户被踢）
    function checkAuth() {
        // iframe内不执行认证检查（base_content.html 已消除侧边栏，但仍保留iframe检查作为安全垫）
        if (window.self !== window.top) return;
        fetchWithTimeout('/api/core/auth/user/', { credentials: 'include' }, 8000)
        .then(function(response) {
            if (response.ok) {
                return response.json().then(function(data) {
                    window.__isSuperuserKnown = true;
                    window.__userId = data.user_id || data.user?.id || null;
                    window.__userIsSuperuser = data.is_superuser || false;
                }).catch(function() {});
                return;
            }
            // 非200：API故障，静默降级（不跳登录页）
            console.warn('[Auth] API returned ' + response.status + ', proceeding with server-side auth');
        })
        .catch(function(err) {
            // AbortError = 页面导航中止，不处理
            if (err.name === 'AbortError') return;
            // 网络错误，静默降级
            console.warn('[Auth] Network error, proceeding with server-side auth');
        });
    }
    checkAuth();

    // 加载权限
    pm.loadPermissions();

    // Toast通知支持
    window.showToast = function(message, type) {
        type = type || 'info';
        var container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            container.className = 'toast-container';
            document.body.appendChild(container);
        }
        var toast = document.createElement('div');
        toast.className = 'toast-msg ' + type;
        var icons = { success: 'bi-check-circle-fill', error: 'bi-x-circle-fill', warning: 'bi-exclamation-triangle-fill', info: 'bi-info-circle-fill' };
        toast.innerHTML = '<i class="bi ' + (icons[type] || icons.info) + '"></i><span>' + message + '</span>';
        container.appendChild(toast);
        setTimeout(function() { toast.remove(); }, 3000);
    };
});

// ── 工具函数 ──────────────────────────────────────
function fetchWithTimeout(url, options, timeout) {
    timeout = timeout || 10000;
    var controller = new AbortController();
    if (typeof _sharedControllers !== 'undefined') {
        // 清理已中止的controller，避免内存堆积
        _sharedControllers = _sharedControllers.filter(function(c) {
            try { return c.signal.aborted === false; } catch(e) { return false; }
        });
        _sharedControllers.push(controller);
    }
    var timeoutId = setTimeout(function() { controller.abort(); }, timeout);
    return fetch(url, Object.assign({}, options || {}, { signal: controller.signal }))
        .finally(function() {
            clearTimeout(timeoutId);
            if (typeof _sharedControllers !== 'undefined') {
                var idx = _sharedControllers.indexOf(controller);
                if (idx !== -1) _sharedControllers.splice(idx, 1);
            }
        });
}

function toggleSidebar() {
    document.getElementById('sidebar').classList.toggle('show');
    document.querySelector('.sidebar-overlay').classList.toggle('show');
}
