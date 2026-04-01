"""
Franja Pixelada — Serializers de Usuarios
"""
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
            'document_type', 'document_number', 'accepts_marketing',
            'account_type', 'profile_image',
        )
        read_only_fields = ('id', 'account_type', 'profile_image')


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
        read_only_fields = ('email', 'first_name', 'last_name', 'phone', 'account_type', 'profile_image')


class RegisterSerializer(serializers.ModelSerializer):
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
