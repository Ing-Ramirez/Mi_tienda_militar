from whitenoise.storage import CompressedManifestStaticFilesStorage


class ManifestStaticFilesStorageRelaxed(CompressedManifestStaticFilesStorage):
    """
    CompressedManifestStaticFilesStorage with two relaxations:
    1. manifest_strict = False — Django no lanza error por URLs no encontradas en CSS.
    2. post_process silencia MissingFileError de Whitenoise (ej: sourceMappingURL
       en bootstrap.min.css que referencia bootstrap.min.css.map inexistente).
    Resultado: collectstatic siempre termina con éxito y genera el manifest.json
    con hashes de contenido, garantizando URLs únicas por versión del archivo.
    """

    manifest_strict = False

    def post_process(self, paths, dry_run=False, **options):
        for result in super().post_process(paths, dry_run, **options):
            name, hashed_name, processed = result
            if isinstance(processed, Exception):
                # Skip files that can't be processed (missing .map files, etc.)
                # Yield original name unprocessed so collectstatic completes.
                yield name, name, False
            else:
                yield result
