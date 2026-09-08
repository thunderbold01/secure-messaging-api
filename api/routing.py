from django.urls import re_path
from api.consumers import CallConsumer

signaling_routing = [
    re_path(r'ws/call/$', CallConsumer.as_asgi()),
]
