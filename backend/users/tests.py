from django.test import TestCase, override_settings
from django.core.cache import cache
from django.core import signing
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient
from core.models import LoginAttempt
from core.tasks import cleanup_old_login_attempts
from .models import User
from .serializers import UserSerializer
from users.views import CaptchaView


def _issue_captcha(code='ABC123'):
    """Genera un token firmado con el código dado en caché."""
    import uuid
    nonce = uuid.uuid4().hex
    cache.set(f'captcha:{nonce}', code, timeout=CaptchaView.TTL)
    token = signing.dumps({'n': nonce}, salt='fp_captcha')
    return token, nonce


@override_settings(DISABLE_CAPTCHA=False, TESTING=True)
class CaptchaValidationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        cache.clear()

    # ── 1. Correcto (mismo case) ────────────────────────────────────────────
    def test_correct_exact_case_passes(self):
        token, _ = _issue_captcha('ABC123')
        from users.views import LoginView
        result = LoginView._validate_captcha(token, 'ABC123')
        self.assertIsNone(result)

    # ── 2. Mismo texto en minúscula → OK (normalización server-side) ───────
    def test_lowercase_input_is_accepted(self):
        token, _ = _issue_captcha('ABC123')
        from users.views import LoginView
        result = LoginView._validate_captcha(token, 'abc123')
        self.assertIsNone(result)

    # ── 3. Expirado (TTL vencido en caché) → ERROR ──────────────────────────
    def test_expired_captcha_rejected(self):
        import uuid
        nonce = uuid.uuid4().hex
        # No guardamos nada en caché → simula expiración
        token = signing.dumps({'n': nonce}, salt='fp_captcha')
        from users.views import LoginView
        result = LoginView._validate_captcha(token, 'ABC123')
        self.assertIsNotNone(result)
        self.assertIn('expiró', result)

    # ── 4. Reutilización → ERROR ────────────────────────────────────────────
    def test_one_time_use_enforced(self):
        token, _ = _issue_captcha('XYZ789')
        from users.views import LoginView
        # Primer uso: correcto
        first = LoginView._validate_captcha(token, 'XYZ789')
        self.assertIsNone(first)
        # Segundo uso con el mismo token: caché ya fue eliminado
        second = LoginView._validate_captcha(token, 'XYZ789')
        self.assertIsNotNone(second)

    # ── 5. TTL = 120 segundos ───────────────────────────────────────────────
    def test_ttl_is_120_seconds(self):
        self.assertEqual(CaptchaView.TTL, 120)

    # ── 6. Token manipulado → ERROR ─────────────────────────────────────────
    def test_bad_signature_rejected(self):
        from users.views import LoginView
        result = LoginView._validate_captcha('token.invalido.firmado', 'ABC123')
        self.assertIsNotNone(result)
        self.assertIn('inválido', result)


class UserSerializerValidationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='cliente@example.com',
            username='cliente@example.com',
            password='PasswordSegura123!',
        )

    def test_cc_document_must_be_numeric(self):
        serializer = UserSerializer(
            instance=self.user,
            data={'document_type': 'CC', 'document_number': 'ABC123'},
            partial=True,
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('document_number', serializer.errors)

    def test_nit_document_accepts_verifier_digit(self):
        serializer = UserSerializer(
            instance=self.user,
            data={'document_type': 'NIT', 'document_number': '900123456-7'},
            partial=True,
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_document_type_requires_document_number(self):
        serializer = UserSerializer(
            instance=self.user,
            data={'document_type': 'CC', 'document_number': ''},
            partial=True,
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('document_number', serializer.errors)

    def test_birth_date_is_exposed_in_serializer_fields(self):
        self.user.birth_date = '1990-01-01'
        self.user.save(update_fields=['birth_date'])
        serializer = UserSerializer(instance=self.user)
        self.assertIn('birth_date', serializer.data)


class LoginAttemptRetentionTaskTests(TestCase):
    def test_cleanup_old_login_attempts_deletes_only_expired(self):
        stale_attempt = LoginAttempt.objects.create(
            username='old@example.com',
            ip_address='10.10.10.10',
            was_successful=False,
        )
        fresh_attempt = LoginAttempt.objects.create(
            username='new@example.com',
            ip_address='10.10.10.11',
            was_successful=False,
        )
        LoginAttempt.objects.filter(pk=stale_attempt.pk).update(
            timestamp=timezone.now() - timedelta(days=91)
        )

        deleted = cleanup_old_login_attempts(retention_days=90)

        self.assertEqual(deleted, 1)
        self.assertFalse(LoginAttempt.objects.filter(pk=stale_attempt.pk).exists())
        self.assertTrue(LoginAttempt.objects.filter(pk=fresh_attempt.pk).exists())
