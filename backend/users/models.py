"""
Franja Pixelada — Modelo de Usuario
"""
from django.contrib.auth.models import AbstractUser
from django.db import models
import uuid


class User(AbstractUser):
    DOCUMENT_CHOICES = [
        ('CC', 'Cédula de Ciudadanía'),
        ('CE', 'Cédula de Extranjería'),
        ('PP', 'Pasaporte'),
        ('NIT', 'NIT'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, verbose_name='Correo electrónico')
    phone = models.CharField(max_length=20, blank=True, verbose_name='Teléfono')
    document_type = models.CharField(
        max_length=5, choices=DOCUMENT_CHOICES,
        blank=True, verbose_name='Tipo de documento'
    )
    document_number = models.CharField(
        max_length=20, blank=True, verbose_name='Número de documento'
    )
    birth_date = models.DateField(null=True, blank=True, verbose_name='Fecha de nacimiento')
    accepts_marketing = models.BooleanField(default=False, verbose_name='Acepta comunicaciones')

    # ── Seguridad 2FA (pendiente integración SMS) ──────────────────────────
    phone_2fa = models.CharField(
        max_length=20, blank=True,
        verbose_name='Teléfono de verificación (2FA)',
        help_text='Formato internacional: +573001234567'
    )
    two_factor_enabled = models.BooleanField(
        default=False,
        verbose_name='2FA activo',
        help_text='Activa la verificación en dos pasos vía SMS'
    )

    profile_image = models.ImageField(
        upload_to='protected/profile_images/', null=True, blank=True,
        verbose_name='Foto de perfil'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'
        db_table = 'users_user'

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'.strip() or self.email
