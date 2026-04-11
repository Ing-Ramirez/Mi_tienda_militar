from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase


User = get_user_model()


class EnsureSuperuserCommandTests(TestCase):
    def test_creates_superuser_with_unique_username_when_base_username_is_taken(self):
        User.objects.create_user(
            username='jramirezarru',
            email='existing@example.com',
            password='oldpass123',
        )

        stdout = StringIO()
        call_command(
            'ensure_superuser',
            email='jramirezarru@hotmail.com',
            password='adminpass123',
            stdout=stdout,
        )

        user = User.objects.get(email='jramirezarru@hotmail.com')
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)
        self.assertEqual(user.username, 'jramirezarru_1')
        self.assertTrue(user.check_password('adminpass123'))

    def test_promotes_existing_user_by_email_and_updates_password(self):
        user = User.objects.create_user(
            username='jhon',
            email='jramirezarru@hotmail.com',
            password='oldpass123',
        )

        stdout = StringIO()
        call_command(
            'ensure_superuser',
            email='jramirezarru@hotmail.com',
            password='newpass123',
            stdout=stdout,
        )

        user.refresh_from_db()
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)
        self.assertEqual(user.username, 'jhon')
        self.assertTrue(user.check_password('newpass123'))
