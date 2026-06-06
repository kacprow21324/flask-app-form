import os

bind = f"0.0.0.0:{os.environ.get('FLASK_PORT', '5000')}"

workers = int(os.environ.get('GUNICORN_WORKERS', '2'))
worker_class = 'gthread'
threads = int(os.environ.get('GUNICORN_THREADS', '4'))

timeout = int(os.environ.get('GUNICORN_TIMEOUT', '120'))
graceful_timeout = 30
keepalive = 5

max_requests = 1000
max_requests_jitter = 100

accesslog = '-'
errorlog = '-'
loglevel = os.environ.get('GUNICORN_LOGLEVEL', 'info')
access_log_format = '%(h)s "%(r)s" %(s)s %(b)sb %(D)sµs'

proc_name = 'flask-app-form'
