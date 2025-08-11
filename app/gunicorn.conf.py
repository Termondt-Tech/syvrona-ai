# gunicorn.conf.py
import os

bind = "0.0.0.0:5000"
worker_class = "gthread"
workers = int(os.getenv("GUNICORN_WORKERS", 5))
threads = int(os.getenv("GUNICORN_THREADS", 2))

timeout = int(os.getenv("GUNICORN_TIMEOUT", 120))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", 30))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", 5))

max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", 100))
max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", 20))

preload_app = False
worker_tmp_dir = "/dev/shm"

# Log to stdout/stderr (Docker-friendly) with PID in access logs
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOGLEVEL", "info")
access_log_format = '%(h)s %(l)s %(u)s "%(r)s" %(s)s %(b)s %(L)s pid=%(p)s'
