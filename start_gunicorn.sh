#!/bin/bash
cd /root/engineering-new
source venv/bin/activate
export DEEPSEEK_API_KEY
exec gunicorn config.wsgi:application --bind 0.0.0.0:8001 --workers 3 --timeout 180 --max-requests 1000 --max-requests-jitter 50 --access-logfile /var/log/engineering-gunicorn-access.log --error-logfile /var/log/engineering-gunicorn-error.log --log-level info
