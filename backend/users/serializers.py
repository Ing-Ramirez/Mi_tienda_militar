"""
Franja Pixelada — Serializers de Usuarios
"""
import re
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError

from .media_tokens import signed_avatar_absolute_url

User = get_user_model()


class _AccountAndAvatarMixin:
    """Expone tipo de cuenta opaco y URL firmada de avatar (sin rutas /media/ públicas)."""

    account_type = serializers.SerializerMethodField()
    profile_image = serializers.SerializerMethodField()

    def get_account_type(self, obj):
        return 'staff' if (obj.is_staff or obj.is_superuser) else 'customer'

    def get_profile_image(self, obj):
        return signed_avatar_absolute_url(self.context.get('request'), obj)


class UserSerializer(_AccountAndAvatarMixin, serializers.ModelSerializer):
    account_type = serializers.SerializerMethodField()
    profile_image = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id', 'email', 'first_name', 'last_name', 'phone',
            'birth_date', 'document_type', 'document_number', 'accepts_marketing',
            'account_type', 'profile_image',
        )
        read_only_fields = ('id', 'email', 'account_type', 'profile_image')

    def validate(self, attrs):
        current_document_type = getattr(self.instance, 'document_type', '') if self.instance else ''
        current_document_number = getattr(self.instance, 'document_number', '') if self.instance else ''
        document_type = (attrs.get('document_type', current_document_type) or '').strip().upper()
        document_number = (attrs.get('document_number', current_document_number) or '').strip()

        if not document_type and not document_number:
            return attrs

        if document_type and not document_number:
            raise serializers.ValidationError({
                'document_number': 'Debes ingresar el número de documento para el tipo seleccionado.'
            })

        validators = {
            'CC': r'^\d{6,10}$',
            'CE': r'^[A-Za-z0-9]{5,12}$',
            'PP': r'^[A-Za-z0-9]{6,12}$',
            'NIT': r'^\d{8,15}(-\d)?$',
        }

        pattern = validators.get(document_type)
        if document_type and not pattern:
            raise serializers.ValidationError({
                'document_type': 'Tipo de documento no soportado.'
            })
        if pattern and not re.fullmatch(pattern, document_number):
            messages = {
                'CC': 'La cédula debe tener entre 6 y 10 dígitos numéricos.',
                'CE': 'La cédula de extranjería debe tener entre 5 y 12 caracteres alfanuméricos.',
                'PP': 'El pasaporte debe tener entre 6 y 12 caracteres alfanuméricos.',
                'NIT': 'El NIT debe tener entre 8 y 15 dígitos y puede incluir un dígito verificador (ej: 900123456-7).',
            }
            raise serializers.ValidationError({'document_number': messages[document_type]})

        attrs['document_type'] = document_type
        attrs['document_number'] = document_number
        return attrs


class AuthUserBriefSerializer(_AccountAndAvatarMixin, serializers.ModelSerializer):
    """
    Representación mínima para flujos de auth (login/register).
    """
    account_type = serializers.SerializerMethodField()
    profile_image = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'email',
            'first_name',
            'last_name',
            'phone',
            'account_type',
            'profile_image',
        )
        # Este serializer solo se usa en respuestas de auth.
        read_only_fields = ('account_type', 'profile_image')


class RegisterSerializer(serializers.ModelSerializer):
    """
    Registro de usuario. Campos requeridos:
      - email, first_name, last_name, password, password2 (confirmación)
    password2 se valida server-side y se descarta antes de crear el objeto.
    """
    password = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True, min_length=8, label='Confirmar contraseña')
    birth_date = serializers.DateField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'phone', 'birth_date', 'password', 'password2')

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({'password2': 'Las contraseñas no coinciden.'})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password2')
        password = validated_data.pop('password')
        email = validated_data['email']
        validated_data.setdefault('username', email)
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Extiende el token response para incluir datos del usuario."""

    def validate(self, attrs):
        data = super().validate(attrs)
        data['user'] = AuthUserBriefSerializer(
            self.user, context=self.context,
        ).data
        return data
