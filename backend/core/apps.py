from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    verbose_name = 'Seguridad y Auditoría'

    def ready(self):
        import core.signals  # noqa: F401 — conecta señales de auditoría
