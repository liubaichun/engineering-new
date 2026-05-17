#!/bin/bash
pkill -TERM -f "gunicorn" || true
sleep 2
cd /root/engineering-new
source venv/bin/activate
exec gunicorn config.wsgi:application -c /root/engineering-new/gunicorn.conf.py