"""
Franja Pixelada — Modelos de seguridad y auditoría
"""
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator
import uuid


class ExchangeRate(models.Model):
    """Tasa de cambio USD → COP definida manualmente por el administrador."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rate = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(1)],
        verbose_name='Tasa USD → COP',
        help_text='Cuántos pesos COP equivalen a 1 USD. Ej: 4000.00',
    )
    rate_date = models.DateField(
        verbose_name='Fecha de la tasa',
        help_text='Fecha en que se estableció esta tasa',
    )
    notes = models.CharField(
        max_length=255, blank=True,
        verbose_name='Nota',
        help_text='Opcional. Ej: "Fuente: Banco de la República"',
    )
    created_by = models.ForeignKey(
        'users.User', on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='Registrado por',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Tasa de Cambio'
        verbose_name_plural = 'Tasas de Cambio'
        ordering = ['-rate_date', '-created_at']

    def __str__(self):
        return f'1 USD = {self.rate:,.2f} COP  ({self.rate_date:%d/%m/%Y})'


class LoginAttempt(models.Model):
    """Registro de intentos de login al panel administrador."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(max_length=255, db_index=True)
    ip_address = models.GenericIPAddressField(db_index=True)
    was_successful = models.BooleanField(default=False, db_index=True)
    user_agent = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Intento de Login'
        verbose_name_plural = 'Intentos de Login'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['username', 'was_successful', 'timestamp']),
            models.Index(fields=['ip_address', 'was_successful', 'timestamp']),
        ]

    def __str__(self):
        result = 'OK' if self.was_successful else 'FALLO'
        return f'[{result}] {self.username} desde {self.ip_address} — {self.timestamp:%Y-%m-%d %H:%M}'


class AdminAuditLog(models.Model):
    """Registro de auditoría de acciones administrativas."""
    ACTION_CHOICES = [
        ('create',   'Creación'),
        ('update',   'Modificación'),
        ('delete',   'Eliminación'),
        ('login',    'Inicio de sesión'),
        ('logout',   'Cierre de sesión'),
        ('export',   'Exportación'),
        ('security', 'Evento de seguridad'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    admin = models.ForeignKey(
        'users.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='audit_logs',
        verbose_name='Administrador'
    )
    admin_username = models.CharField(max_length=255, blank=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, db_index=True)
    model_name = models.CharField(max_length=100, blank=True, db_index=True)
    object_id = models.CharField(max_length=255, blank=True)
    object_repr = models.TextField(blank=True)
    changes = models.JSONField(
        default=dict, blank=True,
        help_text='Diccionario con {campo: [valor_anterior, valor_nuevo]}'
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Registro de Auditoría'
        verbose_name_plural = 'Registros de Auditoría'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['admin', '-timestamp']),
            models.Index(fields=['model_name', 'action']),
        ]

    def __str__(self):
        return f'{self.admin_username} — {self.get_action_display()} {self.model_name} [{self.timestamp:%Y-%m-%d %H:%M}]'

    def format_for_email(self):
        lines = [
            f'Administrador : {self.admin_username}',
            f'Acción        : {self.get_action_display()}',
            f'Modelo        : {self.model_name}',
            f'Objeto        : {self.object_repr}',
            f'IP            : {self.ip_address}',
            f'Fecha         : {self.timestamp:%d/%m/%Y %H:%M}',
        ]
        if self.changes:
            lines.append('Cambios:')
            for field, (old, new) in self.changes.items():
                lines.append(f'  {field}: {old!r} → {new!r}')
        return '\n'.join(lines)
