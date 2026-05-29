import os
import resource

# Workers
workers = 2
worker_class = 'sync'
timeout = 60  # 快速失败，不让慢请求占用worker
keepalive = 5
graceful_timeout = 30

# 防止内存泄漏：每个worker处理N个请求后自动重启
max_requests = 1000
max_requests_jitter = 100


def post_fork(server, worker):
    # 限制单worker最大内存 800MB RSS
    try:
        soft, hard = resource.getrlimit(resource.RLIMIT_RSS)
        resource.setrlimit(resource.RLIMIT_RSS, (800 * 1024 * 1024, hard))
    except Exception:
        pass


def worker_abort(worker):
    print(f'Worker {worker.pid} abort (memory/exit)', file=__import__('sys').stderr)


bind = '0.0.0.0:8001'
daemon = False
preload_app = False

# 持久化 ALLOWED_HOSTS，避免重启丢失
raw_env = ['ALLOWED_HOSTS=124.222.227.28,43.156.139.37,localhost,127.0.0.1']

_log_dir = os.environ.get('GUNICORN_LOG_DIR', os.path.join(os.path.dirname(__file__), 'logs'))
os.makedirs(_log_dir, exist_ok=True)
errorlog = os.path.join(_log_dir, 'error.log')
accesslog = os.path.join(_log_dir, 'access.log')
loglevel = 'info'

# Enable DEBUG logging for perm_debug
import logging
import os

_log_dir = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(_log_dir, exist_ok=True)
perm_debug_handler = logging.FileHandler(os.path.join(_log_dir, 'perm_debug.log'))
perm_debug_handler.setLevel(logging.DEBUG)
perm_debug_handler.setFormatter(logging.Formatter('[%(asctime)s] %(message)s', datefmt='%H:%M:%S'))
perm_debug_logger = logging.getLogger('perm_debug')
perm_debug_logger.setLevel(logging.DEBUG)
perm_debug_logger.addHandler(perm_debug_handler)
