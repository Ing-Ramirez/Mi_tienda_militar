from whitenoise.storage import CompressedManifestStaticFilesStorage


class ManifestStaticFilesStorageRelaxed(CompressedManifestStaticFilesStorage):
    """
    Igual que CompressedManifestStaticFilesStorage pero ignora referencias
    a archivos que no existen (ej: source maps .map de paquetes de terceros).
    """
    manifest_strict = False
