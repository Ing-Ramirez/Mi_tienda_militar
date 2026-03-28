"""
Franja Pixelada — Serializers de Usuarios
"""
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import get_user_model

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'email', 'first_name', 'last_name', 'phone',
                  'document_type', 'document_number', 'accepts_marketing',
                  'is_staff', 'is_superuser')
        read_only_fields = ('id', 'is_staff', 'is_superuser')


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
        data['user'] = UserSerializer(self.user).data
        return data
