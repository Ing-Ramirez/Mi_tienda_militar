from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('captcha/', views.CaptchaView.as_view(), name='captcha'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    # El refresh token viaja en HttpOnly cookie, no en el body
    path('token/refresh/', views.CookieTokenRefreshView.as_view(), name='token_refresh'),
    path('me/', views.MeView.as_view(), name='me'),
    path('me/avatar/', views.AvatarUploadView.as_view(), name='avatar_upload'),
    path('me/avatar/file/', views.AvatarMediaView.as_view(), name='avatar_media'),
]
