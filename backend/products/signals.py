from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.core.files.storage import default_storage


@receiver(post_delete, sender='products.ProductImage')
def cleanup_product_image_file(sender, instance, **kwargs):
    """Elimina el archivo físico tras cualquier delete (incluye bulk queryset.delete())."""
    if not instance.image or not instance.image.name:
        return
    try:
        default_storage.delete(instance.image.name)
    except Exception:
        pass


@receiver(post_delete, sender='products.ProductImage')
def promote_primary_on_delete(sender, instance, **kwargs):
    """Si se eliminó la imagen principal, promueve la siguiente disponible."""
    if not instance.is_primary:
        return
    from products.models import ProductImage
    first = ProductImage.objects.filter(product_id=instance.product_id).first()
    if first:
        ProductImage.objects.filter(pk=first.pk).update(is_primary=True)
