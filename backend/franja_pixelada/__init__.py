# Cargar la app de Celery al iniciar Django para que las tareas periódicas funcionen.
from .celery import app as celery_app

__all__ = ('celery_app',)
