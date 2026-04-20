from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from .models import LoginAttempt


@shared_task(name='core.cleanup_old_login_attempts')
def cleanup_old_login_attempts(retention_days=90):
    cutoff = timezone.now() - timedelta(days=retention_days)
    deleted_count, _ = LoginAttempt.objects.filter(timestamp__lt=cutoff).delete()
    return deleted_count
