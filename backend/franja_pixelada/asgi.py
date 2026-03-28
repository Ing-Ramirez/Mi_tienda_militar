"""
ASGI config for Franja Pixelada project.
"""
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'franja_pixelada.settings')
application = get_asgi_application()
