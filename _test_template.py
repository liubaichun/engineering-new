import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from django.template.loader import render_to_string

html = render_to_string('channels.html')
# Find the scripts section
start = html.find('loadChannels')
if start > 0:
    print(f'loadChannels found at position {start}')
    print(f'Context: {html[start-30:start+50]}')
else:
    print('loadChannels NOT FOUND in rendered HTML!')
    # Search for key elements
    for keyword in ['function loadChannels', 'var channels', 'renderConfig']:
        pos = html.find(keyword)
        if pos >= 0:
            print(f'{keyword}: found at pos {pos}')
        else:
            print(f'{keyword}: NOT FOUND')
