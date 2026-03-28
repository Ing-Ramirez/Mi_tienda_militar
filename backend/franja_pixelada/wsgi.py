"""
WSGI config for Franja Pixelada project.
"""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'franja_pixelada.settings')
application = get_wsgi_application()
