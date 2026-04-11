"""
Comando: ensure_superuser
Crea o actualiza un superusuario de forma idempotente.
"""
import os
import re

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = 'Crea o actualiza un superusuario sin fallar por username repetido.'

    def add_arguments(self, parser):
        parser.add_argument('--email', help='Correo del superusuario')
        parser.add_argument('--password', help='Contrasena del superusuario')
        parser.add_argument('--username', help='Username opcional')
        parser.add_argument(
            '--email-env',
            help='Nombre de variable de entorno que contiene el correo',
        )
        parser.add_argument(
            '--password-env',
            help='Nombre de variable de entorno que contiene la contrasena',
        )
        parser.add_argument(
            '--username-env',
            help='Nombre de variable de entorno que contiene el username opcional',
        )

    def handle(self, *args, **options):
        user_model = get_user_model()
        email = self._resolve_value(options, 'email')
        password = self._resolve_value(options, 'password')
        requested_username = self._resolve_value(options, 'username', required=False)

        if not email:
            raise CommandError('Debes indicar un correo.')
        if not password:
            raise CommandError('Debes indicar una contrasena.')

        manager = user_model._default_manager
        normalizer = getattr(manager, 'normalize_email', None)
        email = normalizer(email) if callable(normalizer) else email
        email = email.strip()

        existing_user = manager.filter(email__iexact=email).first()

        with transaction.atomic():
            if existing_user:
                username = existing_user.username or self._generate_unique_username(
                    user_model,
                    requested_username or self._base_username_from_email(email),
                    exclude_pk=existing_user.pk,
                )
                existing_user.username = username
                existing_user.email = email
                existing_user.is_staff = True
                existing_user.is_superuser = True
                if hasattr(existing_user, 'is_active'):
                    existing_user.is_active = True
                existing_user.set_password(password)
                existing_user.save()
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Superusuario actualizado: {existing_user.email} ({existing_user.username})'
                    )
                )
                return

            username = self._generate_unique_username(
                user_model,
                requested_username or self._base_username_from_email(email),
            )
            user = manager.create_superuser(
                email=email,
                username=username,
                password=password,
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'Superusuario creado: {user.email} ({user.username})'
                )
            )

    def _resolve_value(self, options, key, required=True):
        direct_value = options.get(key)
        if direct_value:
            return direct_value

        env_key = options.get(f'{key}_env')
        if env_key:
            env_value = os.getenv(env_key, '')
            if env_value:
                return env_value

        if required:
            return ''
        return None

    def _base_username_from_email(self, email):
        local_part = email.split('@', 1)[0].strip()
        return local_part or 'admin'

    def _sanitize_username(self, user_model, raw_username):
        username_field = user_model._meta.get_field('username')
        max_length = username_field.max_length or 150
        username = re.sub(r'[^A-Za-z0-9_.@+-]+', '_', (raw_username or '').strip())
        username = username.strip('._-+@')
        if not username:
            username = 'admin'
        return username[:max_length]

    def _generate_unique_username(self, user_model, raw_username, exclude_pk=None):
        username_field = user_model._meta.get_field('username')
        max_length = username_field.max_length or 150
        base_username = self._sanitize_username(user_model, raw_username)
        queryset = user_model._default_manager.all()
        if exclude_pk is not None:
            queryset = queryset.exclude(pk=exclude_pk)

        candidate = base_username
        counter = 1

        while queryset.filter(username=candidate).exists():
            suffix = f'_{counter}'
            candidate = f'{base_username[: max_length - len(suffix)]}{suffix}'
            counter += 1

        return candidate
