"""
Gunicorn configuration file for production deployment
Increases timeouts to handle large PDF processing
FIXED: Changed worker class from gevent to sync for Python 3.13 compatibility
"""

import multiprocessing
import os

# Read PORT from environment (Render sets this to 10000)
port = os.getenv('PORT', '10000')

# Server socket
bind = f"0.0.0.0:{port}"
backlog = 2048

# Worker processes
workers = 3
worker_class = 'sync'  # FIXED: Use 'sync' instead of 'gevent' for Python 3.13
worker_connections = 1000

# CRITICAL: Timeout settings for large PDF processing
timeout = 3600  # 60 minutes - main worker timeout (increased from 1800)
graceful_timeout = 120
keepalive = 5

# Logging
accesslog = '-'
errorlog = '-'
loglevel = 'info'
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = 'quiz_generation_api'

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

print("="*60)
print("Gunicorn Configuration Loaded")
print("="*60)
print(f"Workers: {workers}")
print(f"Worker Class: {worker_class}")
print(f"Timeout: {timeout}s ({timeout/60:.1f} minutes)")
print(f"Graceful Timeout: {graceful_timeout}s")
print(f"Bind: {bind}")
print("="*60)

