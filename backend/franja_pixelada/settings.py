"""
Franja Pixelada — Django Settings
"""
import os
import socket
from pathlib import Path
from datetime import timedelta
from django.core.exceptions import ImproperlyConfigured

# Cargar .env en desarrollo local (sin Docker).
# En Docker las variables vienen del entorno directamente.
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent.parent / '.env')
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = os.environ.get('DEBUG', 'False') == 'True'
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# ── OTP/MFA — debe leerse antes de INSTALLED_APPS y MIDDLEWARE ─────────────
# En desarrollo: DISABLE_ADMIN_OTP=True en .env para omitir el token.
# En producción: dejar en False (o no definir) para requerir TOTP.
DISABLE_ADMIN_OTP = os.environ.get('DISABLE_ADMIN_OTP', 'False') == 'True'

_SECRET_KEY = os.environ.get('SECRET_KEY', '')
if not _SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured(
            'SECRET_KEY environment variable must be set in production. '
            'Generate one with: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"'
        )
    _SECRET_KEY = 'dev-only-insecure-key-do-not-use-in-production'
SECRET_KEY = _SECRET_KEY

# ── Clave de cifrado para credenciales de proveedores ──────────────────────
# Generar con: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Agregar ENCRYPTION_KEY=<valor> al .env.dev y .env.prod
_encryption_key = os.environ.get('ENCRYPTION_KEY', '')
if not _encryption_key:
    if not DEBUG:
        pass  # la validación completa se hace más abajo en el bloque de producción
    else:
        # Desarrollo: deriva la clave del SECRET_KEY (no usar en producción)
        import base64, hashlib
        _encryption_key = base64.urlsafe_b64encode(
            hashlib.sha256(_SECRET_KEY.encode()).digest()
        ).decode()
ENCRYPTION_KEY = _encryption_key

# ── Validaciones de seguridad para producción ──────────────────────────────
if not DEBUG:
    _errors = []

    if DISABLE_ADMIN_OTP:
        _errors.append('DISABLE_ADMIN_OTP debe ser False en producción.')

    if not os.environ.get('DB_PASSWORD'):
        _errors.append('DB_PASSWORD no puede estar vacío en producción.')

    if not os.environ.get('REDIS_PASSWORD'):
        _errors.append('REDIS_PASSWORD no puede estar vacío en producción.')

    if not os.environ.get('ENCRYPTION_KEY'):
        _errors.append('ENCRYPTION_KEY debe estar configurada en producción.')

    _admin_url = os.environ.get('ADMIN_URL', 'admin/')
    if _admin_url in ('admin/', 'admin', 'change_me_url_secreta/'):
        _errors.append('ADMIN_URL debe ser una ruta no predecible en producción.')

    if _errors:
        raise ImproperlyConfigured(
            'Configuración insegura detectada para producción:\n  - ' +
            '\n  - '.join(_errors)
        )

# Webhooks de proveedores sin HMAC: solo en desarrollo local explícito (.env).
# Nunca usar True en producción (accesible públicamente sin firma si el proveedor no tiene secreto).
WEBHOOK_ALLOW_UNSIGNED = os.environ.get('WEBHOOK_ALLOW_UNSIGNED', 'False') == 'True'
if not DEBUG and WEBHOOK_ALLOW_UNSIGNED:
    raise ImproperlyConfigured(
        'WEBHOOK_ALLOW_UNSIGNED no está permitido cuando DEBUG=False.'
    )

INSTALLED_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third party
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'django_filters',
    'storages',
    # MFA (TOTP) para el panel de administración (desactivado si DISABLE_ADMIN_OTP=True)
    *(() if DISABLE_ADMIN_OTP else (
        'django_otp',
        'django_otp.plugins.otp_totp',
        'django_otp.plugins.otp_static',
    )),
    # Cola asíncrona
    'django_celery_beat',
    'django_celery_results',
    # Local apps
    'core',
    'users',
    'products',
    'orders',
    'payments',
    'proveedores',
    'loyalty',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    # CSP + cabeceras de seguridad HTTP (antes que el resto para cubrir todas las respuestas)
    'core.middleware.SecurityHeadersMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    # Telemetría de seguridad para SIEM (request-id + eventos sospechosos)
    'core.middleware.SecurityMonitoringMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    # OTP: desactivado si DISABLE_ADMIN_OTP=True en .env
    *(() if DISABLE_ADMIN_OTP else ('django_otp.middleware.OTPMiddleware',)),
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # ── Seguridad del panel administrador ─────────────────
    'core.middleware.AdminBruteForceMiddleware',
    'core.middleware.AdminSessionTimeoutMiddleware',
]

ROOT_URLCONF = 'franja_pixelada.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                # Expone el nonce CSP a index.html para el bloque <script> y <style>
                'core.middleware.csp_nonce_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'franja_pixelada.wsgi.application'

# ── Base de Datos — PostgreSQL ─────────────────────────────────────────────
_db_conn_max_age_raw = os.environ.get('DB_CONN_MAX_AGE', '').strip()
if _db_conn_max_age_raw == '':
    _db_conn_max_age = 0 if DEBUG else 120
else:
    _db_conn_max_age = int(_db_conn_max_age_raw)

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'franja_pixelada_store'),
        'USER': os.environ.get('DB_USER', 'franja_pixelada_user'),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
        'CONN_MAX_AGE': _db_conn_max_age,
        'OPTIONS': {
            'connect_timeout': 10,
        },
    }
}

AUTH_USER_MODEL = 'users.User'

# Argon2 como hasher principal; PBKDF2 como fallback para hashes ya existentes.
# Los usuarios con PBKDF2 se migran automáticamente a Argon2 en su próximo login.
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
]

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'es-co'
TIME_ZONE = 'America/Bogota'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── Django REST Framework ──────────────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'franja_pixelada.pagination.StandardPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '600/hour',   # ~10 req/min — suficiente para desarrollo y uso normal
        'user': '3000/hour',
        'login': '5/minute',
    },
}

# ── JWT ────────────────────────────────────────────────────────────────────
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# ── CORS ───────────────────────────────────────────────────────────────────
# El frontend es servido por Django — CORS solo es necesario para clientes
# externos (apps móviles, integraciones de terceros).
CORS_ALLOWED_ORIGINS = os.environ.get(
    'CORS_ALLOWED_ORIGINS',
    'http://localhost:8000,http://127.0.0.1:8000'
).split(',')
CORS_ALLOW_CREDENTIALS = True

# ── URL del panel de administración ───────────────────────────────────────
# Cambiar la URL reduce ataques automatizados.  Sincronizar con franja_pixelada/urls.py
ADMIN_URL = os.environ.get('ADMIN_URL', 'admin/')

# ── Correo de alertas de seguridad ─────────────────────────────────────────
ADMIN_SECURITY_EMAIL = os.environ.get('ADMIN_SECURITY_EMAIL', '')

# ── IP del cliente (django-ipware) ────────────────────────────────────────
# Define qué cabeceras se aceptan como fuente de IP y en qué orden.
# Solo se confía en X-Forwarded-For cuando el request llega a través del
# proxy Nginx interno. Un cliente externo no puede falsificar REMOTE_ADDR.
IPWARE_META_PRECEDENCE_ORDER = (
    # En producción con Nginx: la IP real llega en X-Forwarded-For
    'HTTP_X_FORWARDED_FOR',
    # Fallback directo (desarrollo sin proxy)
    'REMOTE_ADDR',
)
# Número de proxies de confianza que se interponen entre internet y Django.
# Con Nginx en Docker: 1 proxy. Ajustar si hay un load balancer adicional.
IPWARE_TRUSTED_PROXY_COUNT = int(os.environ.get('TRUSTED_PROXY_COUNT', '1'))

# ── Sesiones del administrador ─────────────────────────────────────────────
SESSION_COOKIE_AGE = 1800          # 30 minutos (máximo absoluto)
SESSION_SAVE_EVERY_REQUEST = True  # Reiniciar el contador en cada request
SESSION_COOKIE_HTTPONLY = True     # No accesible desde JS
SESSION_COOKIE_SAMESITE = 'Lax'

# ── Seguridad (todas las variables, aplican en producción y parcialmente en dev)
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
# Django debe confiar en el proto enviado por Nginx para tratar requests como HTTPS.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# ── Pagos ──────────────────────────────────────────────────────────────────
STRIPE_PUBLIC_KEY = os.environ.get('STRIPE_PUBLIC_KEY', '')
STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', '')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')

PAYPAL_CLIENT_ID = os.environ.get('PAYPAL_CLIENT_ID', '')
PAYPAL_SECRET = os.environ.get('PAYPAL_SECRET', '')
PAYPAL_MODE = os.environ.get('PAYPAL_MODE', 'sandbox')

# ── Email ──────────────────────────────────────────────────────────────────
EMAIL_BACKEND = (
    'django.core.mail.backends.console.EmailBackend'
    if DEBUG else
    'django.core.mail.backends.smtp.EmailBackend'
)
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'Franja Pixelada <noreply@franjapixelada.com>')

# ── Redis / Caché ──────────────────────────────────────────────────────────
# Usa Redis si REDIS_HOST está configurado; en otro caso usa caché en memoria.
_redis_host = os.environ.get('REDIS_HOST', '')

if _redis_host:
    _redis_password = os.environ.get('REDIS_PASSWORD', '')
    _redis_port = os.environ.get('REDIS_PORT', '6379')
    _redis_url = (
        os.environ.get('REDIS_URL')
        or (
            f'redis://:{_redis_password}@{_redis_host}:{_redis_port}/1'
            if _redis_password
            else f'redis://{_redis_host}:{_redis_port}/1'
        )
    )
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': _redis_url,
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            },
        }
    }
else:
    # Sin Redis: caché local en memoria (desarrollo sin contenedor Redis)
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        }
    }

if _redis_host:
    SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
    SESSION_CACHE_ALIAS = 'default'
else:
    SESSION_ENGINE = 'django.contrib.sessions.backends.db'

# ── Celery — Cola asíncrona ────────────────────────────────────────────────
# Broker y backend: Redis DB 2 (DB 1 es la caché de Django)
_celery_redis_password = os.environ.get('REDIS_PASSWORD', '')
_celery_redis_host = os.environ.get('REDIS_HOST', 'redis')
_celery_redis_port = os.environ.get('REDIS_PORT', '6379')

if _celery_redis_password:
    _celery_broker = f'redis://:{_celery_redis_password}@{_celery_redis_host}:{_celery_redis_port}/2'
else:
    _celery_broker = f'redis://{_celery_redis_host}:{_celery_redis_port}/2'

CELERY_BROKER_URL = _celery_broker
CELERY_RESULT_BACKEND = 'django-db'          # Resultados en PostgreSQL via django-celery-results
CELERY_CACHE_BACKEND = 'django-cache'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'America/Bogota'
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 300                 # Máximo 5 min por tarea
CELERY_TASK_SOFT_TIME_LIMIT = 240            # Warning a los 4 min

# ── Sistema de Fidelidad (puntos) ─────────────────────────────────────────────
# 1 punto por cada LOYALTY_POINTS_PER_COP de subtotal.
# Cada punto vale LOYALTY_POINT_VALUE_COP al redimir.
# Máximo redimible por orden: LOYALTY_MAX_REDEMPTION_PCT × total.
LOYALTY_POINTS_PER_COP = int(os.environ.get('LOYALTY_POINTS_PER_COP', '1000'))
LOYALTY_POINT_VALUE_COP = int(os.environ.get('LOYALTY_POINT_VALUE_COP', '10'))
LOYALTY_MAX_REDEMPTION_PCT = float(os.environ.get('LOYALTY_MAX_REDEMPTION_PCT', '0.20'))
LOYALTY_EXPIRATION_DAYS = None   # None = sin expiración; int = días hasta expirar

# ── IVA y Envío ────────────────────────────────────────────────────────────
TAX_RATE = float(os.environ.get('TAX_RATE', '0.19'))
FREE_SHIPPING_THRESHOLD = float(os.environ.get('FREE_SHIPPING_THRESHOLD', '200000'))
BASE_SHIPPING_COST = float(os.environ.get('BASE_SHIPPING_COST', '15000'))

# ── Neki (pago manual — datos mostrados al cliente; no son credenciales reales) ──
NEKI_DISPLAY_PHONE = os.environ.get('NEKI_DISPLAY_PHONE', '+57 300 000 0000')
NEKI_DISPLAY_ACCOUNT_NAME = os.environ.get('NEKI_DISPLAY_ACCOUNT_NAME', 'Franja Pixelada S.A.S. (demo)')

# ── Jazzmin — Tema del panel de administración ─────────────────────────────
JAZZMIN_SETTINGS = {
    # Identidad
    "site_title": "Franja Pixelada",
    "site_header": "Franja Pixelada",
    "site_brand": "Franja Pixelada",
    "welcome_sign": "Bienvenido al panel de control",
    "copyright": "Franja Pixelada",

    # Búsqueda global en el admin
    "search_model": ["users.User", "products.Product", "orders.Order"],

    # Menú superior
    "topmenu_links": [
        {"name": "Inicio", "url": "admin:index", "permissions": ["auth.view_user"]},
        {"name": "Ver tienda", "url": "/", "new_window": True},
    ],

    # Sidebar de navegación activo
    "show_sidebar": True,
    "navigation_expanded": True,

    # Orden de apps en el sidebar
    "order_with_respect_to": [
        "users", "products", "orders", "loyalty", "proveedores", "payments", "core", "auth",
    ],

    # Estilos propios (paridad de marca con la tienda — ver static/css/franja_admin.css)
    "custom_css": "css/franja_admin.css",
    # JS global: reinicializa select-all tras navegación pjax de Jazzmin
    "custom_js": "js/franja_admin_global.js",

    # Íconos por modelo (Font Awesome 5)
    "icons": {
        "auth":                    "fas fa-shield-alt",
        "auth.Group":              "fas fa-users",
        "users.User":              "fas fa-user-shield",
        "products.Category":       "fas fa-sitemap",
        "products.Tag":            "fas fa-tag",
        "products.Product":        "fas fa-box-open",
        "products.ProductVariant": "fas fa-code-branch",
        "products.ProductReview":  "fas fa-star",
        "products.InventoryLog":   "fas fa-clipboard-list",
        "products.Favorito":       "fas fa-heart",
        "orders.Cart":             "fas fa-shopping-cart",
        "orders.Order":            "fas fa-file-invoice",
        "orders.Address":          "fas fa-map-marker-alt",
        "orders.Coupon":           "fas fa-ticket-alt",
        "payments.Payment":        "fas fa-credit-card",
        "proveedores.Supplier":         "fas fa-truck-loading",
        "proveedores.SupplierProduct":  "fas fa-boxes",
        "proveedores.SupplierVariant":  "fas fa-layer-group",
        "proveedores.LinkedProduct":    "fas fa-link",
        "proveedores.SupplierOrder":    "fas fa-file-export",
        "proveedores.SupplierTracking": "fas fa-shipping-fast",
        "proveedores.SupplierLog":      "fas fa-scroll",
        "core.LoginAttempt":       "fas fa-lock",
        "core.AdminAuditLog":      "fas fa-history",
        "loyalty.LoyaltyAccount":  "fas fa-coins",
        "loyalty.PointTransaction": "fas fa-exchange-alt",
    },
    "default_icon_parents": "fas fa-folder",
    "default_icon_children": "fas fa-circle",

    # Modales para relaciones (en lugar de abrir nueva pestaña)
    "related_modal_active": True,

    # No mostrar el constructor de UI en producción
    "show_ui_builder": False,

    # Formato de formularios de detalle
    "changeform_format": "horizontal_tabs",

    # No cargar Google Fonts via CDN (ya manejado por el SPA)
    "use_google_fonts_cdn": False,
    "language_chooser": False,
}

JAZZMIN_UI_TWEAKS = {
    # Tamaños de texto
    "navbar_small_text": False,
    "footer_small_text": True,
    "body_small_text": False,
    "brand_small_text": False,

    # Colores — paleta militar oliva
    "brand_colour": False,
    "accent": "accent-olive",
    "navbar": "navbar-dark",
    "no_navbar_border": True,

    # Posición
    "navbar_fixed": True,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": True,

    # Sidebar
    "sidebar": "sidebar-dark-olive",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": True,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,

    # Tema Bootstrap base
    "theme": "flatly",
    "dark_mode_theme": None,

    # Clases de botones
    "button_classes": {
        "primary":   "btn-primary",
        "secondary": "btn-secondary",
        "info":      "btn-outline-info",
        "warning":   "btn-warning",
        "danger":    "btn-danger",
        "success":   "btn-success",
    },
}

# ── Logging ────────────────────────────────────────────────────────────────
SIEM_ENABLED = os.environ.get('SIEM_ENABLED', 'False') == 'True'
SIEM_HOST = os.environ.get('SIEM_HOST', '').strip()
SIEM_PORT = int(os.environ.get('SIEM_PORT', '514'))
SIEM_PROTOCOL = os.environ.get('SIEM_PROTOCOL', 'udp').strip().lower()
_SIEM_SOCKTYPE = socket.SOCK_STREAM if SIEM_PROTOCOL == 'tcp' else socket.SOCK_DGRAM
# Política de retención de datos de auditoría (comando cleanup_logs).
SUPPLIER_LOG_RETENTION_DAYS = int(os.environ.get('SUPPLIER_LOG_RETENTION_DAYS', '90'))
PAYMENT_LOG_RETENTION_DAYS = int(os.environ.get('PAYMENT_LOG_RETENTION_DAYS', '365'))

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs/error.log',
            'formatter': 'verbose',
        },
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        **(
            {
                'siem': {
                    'level': 'WARNING',
                    'class': 'logging.handlers.SysLogHandler',
                    'address': (SIEM_HOST, SIEM_PORT),
                    'socktype': _SIEM_SOCKTYPE,
                    'formatter': 'verbose',
                }
            }
            if SIEM_ENABLED and SIEM_HOST else {}
        ),
    },
    'loggers': {
        'core.security': {
            'handlers': ['console', 'file', *(['siem'] if SIEM_ENABLED and SIEM_HOST else [])],
            'level': 'INFO',
            'propagate': False,
        },
        'security.events': {
            'handlers': ['console', 'file', *(['siem'] if SIEM_ENABLED and SIEM_HOST else [])],
            'level': 'WARNING',
            'propagate': False,
        },
    },
    'root': {
        'handlers': ['console', 'file', *(['siem'] if SIEM_ENABLED and SIEM_HOST else [])],
        'level': 'WARNING',
    },
}
