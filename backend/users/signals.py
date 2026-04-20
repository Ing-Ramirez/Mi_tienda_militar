from django.contrib.auth import get_user_model
from django.db.models.signals import post_delete
from django.dispatch import receiver

User = get_user_model()


@receiver(post_delete, sender=User)
def delete_avatar_on_user_delete(sender, instance, **kwargs):
    if instance.profile_image:
        instance.profile_image.delete(save=False)
