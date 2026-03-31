"""Tokens firmados (de corta duración) para servir avatares en <img> sin cabecera Authorization."""
from urllib.parse import urlencode

from django.core import signing
from django.urls import reverse

_AVATAR_SALT = 'franja-pixelada.user-avatar.v1'
_MAX_AGE_SECONDS = 3600  # 1 h — suficiente para sesión de tienda; se renueva al cargar /me


def build_avatar_media_token(user_id, relative_name: str) -> str:
    if not relative_name:
        raise ValueError('relative_name required')
    return signing.dumps(
        {'u': str(user_id), 'f': relative_name},
        salt=_AVATAR_SALT,
    )


def parse_avatar_media_token(token: str) -> dict:
    return signing.loads(token, max_age=_MAX_AGE_SECONDS, salt=_AVATAR_SALT)


def signed_avatar_absolute_url(request, user):
    """URL absoluta al endpoint que sirve el avatar (token firmado)."""
    if (
        not request
        or not getattr(user, 'profile_image', None)
        or not user.profile_image.name
    ):
        return None
    token = build_avatar_media_token(user.pk, user.profile_image.name)
    path = reverse('avatar_media')
    return request.build_absolute_uri(f'{path}?{urlencode({"t": token})}')
