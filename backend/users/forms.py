"""
Franja Pixelada — Formularios de admin para usuarios
"""
from django.contrib.auth.forms import UserChangeForm
from .models import User
from .widgets import SplitDateWidget


class UserAdminForm(UserChangeForm):
    """
    Extiende UserChangeForm manteniendo el widget de contraseña estándar
    y reemplazando el DatePicker de birth_date por SplitDateWidget.
    """

    class Meta(UserChangeForm.Meta):
        model = User
        fields = '__all__'
        widgets = {
            'birth_date': SplitDateWidget(),
        }
