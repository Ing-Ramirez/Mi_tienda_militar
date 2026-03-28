"""
Franja Pixelada — Validadores de archivos subidos
"""
import os
from django.core.exceptions import ValidationError

ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
BLOCKED_EXTENSIONS = {'.exe', '.js', '.html', '.htm', '.php', '.py', '.sh',
                      '.bat', '.cmd', '.ps1', '.rb', '.pl', '.asp', '.aspx'}
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


def validate_image_file(value):
    """
    Valida que:
    - El archivo sea JPG, PNG o WEBP
    - No sea un tipo de archivo peligroso
    - No supere 5 MB
    """
    if not value:
        return

    name = value.name.lower() if hasattr(value, 'name') else str(value).lower()
    ext = os.path.splitext(name)[1]

    # Bloquear extensiones peligrosas
    if ext in BLOCKED_EXTENSIONS:
        raise ValidationError(
            f'Tipo de archivo no permitido: {ext}. '
            'Solo se permiten imágenes JPG, PNG y WEBP.'
        )

    # Verificar extensión permitida
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError(
            f'Extensión "{ext}" no válida. '
            'Solo se permiten: JPG, PNG, WEBP.'
        )

    # Verificar tamaño
    if hasattr(value, 'size') and value.size > MAX_IMAGE_SIZE_BYTES:
        size_mb = value.size / (1024 * 1024)
        raise ValidationError(
            f'La imagen pesa {size_mb:.1f} MB. '
            'El tamaño máximo permitido es 5 MB.'
        )

    # Verificar contenido real del archivo (primeros bytes)
    if hasattr(value, 'read'):
        header = value.read(16)
        value.seek(0)  # Volver al inicio
        _verify_image_magic_bytes(header, ext)


def _verify_image_magic_bytes(header: bytes, declared_ext: str):
    """Verifica que los primeros bytes del archivo correspondan al tipo declarado."""
    MAGIC_BYTES = {
        '.jpg':  [(b'\xff\xd8\xff',)],
        '.jpeg': [(b'\xff\xd8\xff',)],
        '.png':  [(b'\x89PNG\r\n\x1a\n',)],
        '.webp': [(b'RIFF', b'WEBP')],  # RIFF....WEBP
    }
    signatures = MAGIC_BYTES.get(declared_ext, [])
    for sig in signatures:
        if len(sig) == 1:
            if header.startswith(sig[0]):
                return  # Válido
        elif len(sig) == 2:
            # WEBP: header empieza con RIFF y contiene WEBP en posición 8
            if header[:4] == sig[0] and header[8:12] == sig[1]:
                return  # Válido

    if signatures:
        raise ValidationError(
            'El contenido del archivo no corresponde a una imagen válida. '
            'Por favor suba un archivo JPG, PNG o WEBP auténtico.'
        )
