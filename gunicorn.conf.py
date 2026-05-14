import resource

# Workers
workers = 2
worker_class = 'sync'
timeout = 60          # 快速失败，不让慢请求占用worker
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
preload_app = True
errorlog = '/root/engineering-new/logs/error.log'
accesslog = '/root/engineering-new/logs/access.log'
loglevel = 'info'
