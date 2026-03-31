"""
Franja Pixelada — Serializers de Usuarios
"""
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import get_user_model

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
        read_only_fields = fields


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'phone', 'password')

    def create(self, validated_data):
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
