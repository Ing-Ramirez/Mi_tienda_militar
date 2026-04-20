"""
Franja Pixelada — Configuración de Celery
Cola asíncrona para: webhooks de proveedores, envío de pedidos, sincronización periódica.
"""
import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'franja_pixelada.settings')

app = Celery('franja_pixelada')

# Lee configuración con prefijo CELERY_ desde settings.py
app.config_from_object('django.conf:settings', namespace='CELERY')

# Descubre tareas automáticamente en todos los INSTALLED_APPS
app.autodiscover_tasks()


@app.on_after_finalize.connect
def setup_tareas_periodicas(sender, **kwargs):
    """
    Tareas periódicas registradas al iniciar.
    La sincronización periódica actúa como fallback para proveedores
    que no soportan webhooks (polling cada 30 minutos).
    """
    sender.add_periodic_task(
        crontab(minute='*/30'),
        sender.signature('proveedores.sincronizacion_periodica'),
        name='Sincronización periódica de catálogos de proveedores',
    )
    sender.add_periodic_task(
        crontab(hour='3', minute='0'),
        sender.signature('core.cleanup_old_login_attempts'),
        name='Limpieza diaria de intentos de login antiguos',
    )
