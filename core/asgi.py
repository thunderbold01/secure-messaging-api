import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from api.routing import signaling_routing

application = ProtocolTypeRouter({
    'http': get_asgi_application(),
    'websocket': URLRouter(signaling_routing),
})
