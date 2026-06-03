#!/usr/bin/env python3
import os
import sys
import django

sys.path.insert(0, '/root/engineering-new')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
os.chdir('/root/engineering-new')
django.setup()

from django.urls import get_resolver

resolver = get_resolver()
for pattern in resolver.url_patterns:
    print(f'{pattern.pattern}')
