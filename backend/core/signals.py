"""
Franja Pixelada — Señales de auditoría automática
Registra creaciones, modificaciones y eliminaciones hechas desde el Django Admin.
"""
import logging
from django.contrib.admin.models import LogEntry, ADDITION, CHANGE, DELETION
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger('core.audit')

ACTION_MAP = {
    ADDITION: 'create',
    CHANGE:   'update',
    DELETION: 'delete',
}


@receiver(post_save, sender=LogEntry)
def on_admin_logentry(sender, instance: LogEntry, created, **kwargs):
    """
    Cada vez que Django Admin registra una acción (LogEntry),
    creamos nuestro propio AdminAuditLog con más detalle.
    """
    if not created:
        return

    try:
        from .models import AdminAuditLog

        action = ACTION_MAP.get(instance.action_flag, 'update')

        # Intentar extraer los cambios del message de Django
        changes = {}
        if instance.action_flag == CHANGE and instance.change_message:
            import json
            try:
                msgs = json.loads(instance.change_message)
                for msg in msgs:
                    if 'changed' in msg:
                        for field in msg['changed'].get('fields', []):
                            changes[field] = ['(anterior)', '(nuevo)']
            except (json.JSONDecodeError, TypeError, KeyError):
                pass

        AdminAuditLog.objects.create(
            admin_id=instance.user_id,
            admin_username=str(instance.user),
            action=action,
            model_name=instance.content_type.model if instance.content_type else '',
            object_id=str(instance.object_id or ''),
            object_repr=instance.object_repr or '',
            changes=changes,
        )
        logger.info(
            f'Auditoría: {instance.user} {action} '
            f'{instance.content_type} #{instance.object_id}'
        )
    except Exception as e:
        logger.error(f'Error creando AdminAuditLog: {e}')
