# Franja Pixelada — E-commerce táctico

[![Django](https://img.shields.io/badge/Django-5.0.4-092E20?style=flat-square&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![DRF](https://img.shields.io/badge/DRF-3.15.2-red?style=flat-square&logo=django&logoColor=white)](https://www.django-rest-framework.org/)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?style=flat-square&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?style=flat-square&logo=redis&logoColor=white)](https://redis.io/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white)](https://docs.docker.com/compose/)
[![Licencia](https://img.shields.io/badge/Licencia-Propietaria-red?style=flat-square)](./LICENSE)

---

## Descripción

Plataforma de comercio electrónico Django para equipamiento militar y táctico en el mercado colombiano. El backend expone una API REST con JWT y 8 aplicaciones Django. El frontend es una SPA de ~9.900 líneas en un único archivo HTML sin paso de build.

Pagos activos: Stripe (PaymentIntent + webhook HMAC) y Neki/Nequi (comprobante manual con verificación admin). PayPal está presente como stub que retorna 501. El sistema soporta personalización de prendas por ítem (texto bordado y grupo sanguíneo) y dropshipping con sincronización de stock y despacho automático vía Celery.

---

## Stack técnico

| Capa | Tecnología |
|------|-----------|
| Backend | Django 5.0.4 + DRF 3.15.2 |
| Auth | SimpleJWT — access token en header `Bearer`, refresh en cookie `HttpOnly` restringida a `/api/v1/auth/` |
| Base de datos | PostgreSQL 16 (psycopg2 2.9.9) |
| Caché / broker | Redis 7 (django-redis 5.4.0) — DB 0: caché; DB 2: Celery broker |
| Cola asíncrona | Celery 5.4.0 + django-celery-beat (scheduler en DB) + django-celery-results |
| Frontend | SPA en `backend/templates/store/index.html` — HTML + CSS + JS inline, sin build step |
| Servidor web | Nginx 1.25 + Gunicorn 22 + WhiteNoise 6.6 |
| TLS | Certbot (renovación automática vía Docker) |
| Admin UI | Jazzmin 2.6.0 + django-otp 1.4.0 (TOTP 2FA) |
| Pagos | Stripe 9.5.0 (activo) · Neki/comprobante manual (activo) · PayPal (stub 501) |
| Cifrado | cryptography 43.0.0 — Fernet AES-128-CBC para credenciales de proveedores |
| Hashing | Argon2 (argon2-cffi) principal; PBKDF2 como fallback de migración automática |
| Imágenes | Pillow 10.3.0 + validación de magic bytes |
| Python | 3.12 |

---

## Arquitectura — Apps Django

### `core`

Middleware en orden de carga:

1. **`SecurityHeadersMiddleware`** — genera nonce CSP único por request. Admin usa `unsafe-inline` (limitación de templates Django); frontend público usa `nonce-{nonce}` estricto. Agrega `X-Content-Type-Options`, `Permissions-Policy`, `Referrer-Policy`, `HSTS`.
2. **`AdminBruteForceMiddleware`** — registra intentos en `LoginAttempt`. 5 fallos → bloqueo 15 min; 10 fallos → 60 min. Envía email a `ADMIN_SECURITY_EMAIL` al alcanzar umbrales.
3. **`AdminSessionTimeoutMiddleware`** — cierra sesión admin tras 30 min de inactividad (`ADMIN_SESSION_TIMEOUT`).
4. **`SecurityMonitoringMiddleware`** — asigna `X-Request-ID`, detecta patrones de inyección y probing (`<script`, `union select`, `../`), registra eventos 401/403/429 en rutas de auth, órdenes y pagos al logger `security.events`.

Modelos inmutables: `LoginAttempt`, `AdminAuditLog` (acciones create/update/delete/login/logout, con diff de cambios en JSON).

`FranjaAdminSite` (en `core/admin_site.py`) extiende `OTPAdminSite` de django-otp. Todos los modelos deben registrarse con `admin_site`, no con `admin.site`. `each_context()` inyecta KPIs en tiempo real (órdenes hoy/mes, ingresos MTD, productos activos, stock bajo, sin stock) con manejo silencioso de errores para que el admin nunca rompa por una métrica fallida.

### `users`

`User` extiende `AbstractUser`: UUID PK, `USERNAME_FIELD = 'email'`, `REQUIRED_FIELDS = ['username']`. Campos `phone_2fa` y `two_factor_enabled` presentes en el modelo para 2FA SMS — sin integración activa.

JWT: access token en body de respuesta; refresh token en cookie `HttpOnly` con `SameSite=Lax`, `Secure=True` en producción, `path='/api/v1/auth/'`. El frontend nunca debe leer ni almacenar el refresh token.

CAPTCHA: generado como SVG (código no expuesto en JSON), case-sensitive, TTL 120 segundos, uso único (token eliminado de caché tras validación correcta). Controlado por `DISABLE_CAPTCHA` en settings; el startup lanza `ImproperlyConfigured` si `DISABLE_CAPTCHA=True` con `DEBUG=False`.

Avatar: subida con validación de magic bytes y firma de URL con `django.core.signing` (sin Bearer token para etiquetas `<img>`).

Throttling: `LoginRateThrottle` (5/min), `RegisterRateThrottle` (30/h).

### `products`

`Category`: árbol de profundidad 1 (campo `parent` FK a sí misma). Slug autogenerado.

`Product`: `requires_size` controla si el stock es global o por talla. `stock_by_size` almacena un dict JSON `{"S": 5, "M": 10}`; `stock` y `available_sizes` se recalculan en `save()`. `benefits` es una lista JSON de hasta 5 strings. Cuatro estados: `active`, `inactive`, `out_of_stock`, `coming_soon`. Propiedades calculadas: `is_in_stock`, `is_low_stock`, `discount_percentage`, `main_image`.

`ProductVariant`: `color_hex` con `RegexValidator` `^#[0-9A-Fa-f]{6}$` o vacío.

`ProductReview`: `unique_together = ['product', 'user', 'order']` — un usuario puede dejar múltiples reseñas del mismo producto si provienen de órdenes distintas. Flujo de moderación: `pending → approved | hidden`. `is_verified_purchase` se establece en `True` al crear la reseña via el endpoint de compra verificada.

`ProductImage`: señal `post_delete` en `products/signals.py` cubre cleanup del archivo físico en storage (incluyendo bulk deletes). Segunda señal promueve automáticamente la siguiente imagen como principal si se elimina la primaria. El método `delete()` sobreescrito maneja el caso de borrado individual.

`InventoryLog`: inmutable, append-only. Registra acción (`add`, `remove`, `sale`, `return`, `adjustment`), valores antes/después y usuario responsable.

`validate_image_file` verifica magic bytes — no confía en la extensión del archivo. Aplicada a avatares, comprobantes de pago, evidencias de reseñas y devoluciones.

### `orders`

`Cart`: por usuario (`OneToOneField`) o por sesión anónima (`session_key`).

`CartItem`: `unique_together = ['cart', 'product', 'variant', 'talla', 'bordado', 'rh']` — ítems con personalización diferente nunca se fusionan.

`Order`: número generado como `FP` + 10 hex de UUID (3 reintentos con manejo de colisión `IntegrityError`). Snapshot completo de dirección en el momento del pedido. Campos de fidelidad (`loyalty_points_used`, `loyalty_discount_amount`, `loyalty_points_earned`, `loyalty_points_processed`) donde `loyalty_points_processed` actúa como bandera de idempotencia.

`ManualPaymentStatus` (state machine para Neki):

```
'' → PENDING → PAID → VERIFIED (terminal)
                    ↘ REJECTED (terminal)
              ↘ VERIFIED (terminal)
              ↘ REJECTED (terminal)
```

Validado en `Order.clean()`. La señal `post_save` detecta la transición a `VERIFIED`, descuenta stock dentro de `transaction.atomic()` con `select_for_update()`, actualiza `order.status = processing` y encola `send_order_to_provider` y `assign_loyalty_points` en Celery.

`calculate_cart_totals()` en `orders/services/__init__.py` es la única fuente de verdad para totales. Calcula subtotal, envío (gratuito si `subtotal >= FREE_SHIPPING_THRESHOLD`), IVA (19%) y descuento por cupón.

`CartViewSet` usa `select_for_update()` + expresiones `F()` para actualizar cantidades, eliminando race conditions con múltiples workers concurrentes.

### `payments`

`Payment` registra transacciones. `raw_response` guarda el payload filtrado del proveedor.

Stripe: `PaymentIntent` con `request_three_d_secure: automatic`. El webhook verifica firma HMAC, compara `amount_received` con `order.total` (en centavos COP) y usa `select_for_update()` al actualizar la orden. Al recibir `payment_intent.succeeded`, encola `assign_loyalty_points`.

PayPal: `PayPalCreateOrderView` y `PayPalCaptureView` retornan `HTTP 501` con `{'detail': 'PayPal no configurado en este entorno.'}`. Los endpoints existen y están en las URLs.

Neki: gestionado enteramente en `orders/` — usa `payment_proof` (ImageField) + `ManualPaymentStatus` en `Order`. No tiene entidad `Payment` propia.

### `loyalty`

`LoyaltyAccount`: 1:1 con User. Campos: `points_balance`, `total_earned`, `total_redeemed`.

`PointTransaction`: inmutable, append-only. `points > 0` = crédito; `points < 0` = débito. Tipos: `earn`, `redeem`, `reverse_earn`, `reverse_redeem`, `adjustment`. Nunca llamar `.save()` ni `.delete()` sobre transacciones existentes.

`loyalty/services.py` centraliza toda la lógica de negocio. Todas las mutaciones de saldo usan `select_for_update()` sobre `LoyaltyAccount` + expresiones `F()` para evitar race conditions con múltiples workers Celery. La acumulación de puntos es idempotente vía `Order.loyalty_points_processed` + búsqueda de transacción `EARN` existente.

Configuración por settings: `LOYALTY_POINTS_PER_COP` (default 1000), `LOYALTY_POINT_VALUE_COP` (default 10 COP/punto), `LOYALTY_MAX_REDEMPTION_PCT` (default 0.20).

El reverso de puntos se dispara desde `loyalty/signals.py` cuando `Order.status` transiciona a `cancelled` o `refunded`.

### `returns`

`ReturnRequest` implementa una máquina de estados con 10 estados y transiciones validadas en `VALID_TRANSITIONS`:

```
requested → reviewing → approved → in_transit → received → validated → refunded → closed
         ↘ rejected_subsanable → closed
         ↘ rejected_definitive → closed
```

Usar siempre `ReturnRequest.transition(new_status, changed_by, note)` — nunca asignar `.status` directamente. El método valida la transición, asigna fechas automáticas y crea un `ReturnAuditLog` inmutable.

Soporta reintentos: `parent_return` FK + `attempt_number`. Máximo de intentos configurable (`RETURN_MAX_ATTEMPTS_PER_ORDER`, default 3). `return_code` autogenerado con formato `DEV-XXXXXXXX`.

Ventanas de devolución: 30 días para producto nuevo (`RETURN_WINDOW_DAYS_NEW`), 14 días para usado. Categorías y prefijos de SKU excluibles vía settings.

`ReturnAuditLog`: inmutable, append-only.

### `proveedores`

`Supplier`: credenciales de API cifradas con Fernet en columna `_credentials`. Acceder siempre vía la property `credenciales`, nunca directamente. Nunca llamar `.delete()` sobre registros de proveedor — usar `is_active` o `status`.

Adapters disponibles: `dropi`, `rest_generico` (Bearer + endpoint `/orders/`), `mock` (sin red, para tests). El adapter se selecciona por el campo `Supplier.adapter` y se resuelve en `proveedores/services/adapters/registry.py`.

`LinkedProduct`: vínculo entre `SupplierVariant` y `Product`. Stock visible al cliente = `min(stock_proveedor, LinkedProduct.max_stock)` ("capped stock sync").

Flujo de despacho: se dispara exclusivamente cuando admin marca `Order.manual_payment_status = VERIFIED`. La señal encola `send_order_to_provider.delay()` que llama `proveedores.services.despacho.despachar_orden_a_proveedores()`.

`SupplierLog`: inmutable, registra todos los eventos del módulo.

---

## Instalación

### Requisitos

- Docker 24+ y Docker Compose 2.x
- Git

### Variables de entorno

```bash
cp .env.example .env
# editar .env con los valores reales
```

Variables mínimas para desarrollo:

```env
SECRET_KEY=<genera con: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())">
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DB_PASSWORD=<contraseña-local>
REDIS_PASSWORD=<contraseña-redis>
DISABLE_ADMIN_OTP=True
DISABLE_CAPTCHA=True
TESTING=True
```

Variables adicionales requeridas en producción:

| Variable | Descripción |
|----------|-------------|
| `DEBUG` | `False` (obligatorio) |
| `DOMAIN_NAME` | Dominio del servidor |
| `ADMIN_URL` | Ruta del admin — producción falla si es `admin/` o `admin` |
| `ENCRYPTION_KEY` | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `STRIPE_SECRET_KEY` | Dashboard de Stripe |
| `STRIPE_WEBHOOK_SECRET` | Firmado de webhooks Stripe |
| `ADMIN_SECURITY_EMAIL` | Destino de alertas de brute force |
| `DISABLE_ADMIN_OTP` | `False` obligatorio — startup falla si `True` con `DEBUG=False` |
| `DISABLE_CAPTCHA` | `False` obligatorio — startup falla si `True` con `DEBUG=False` |
| `TESTING` | `False` obligatorio — startup falla si `True` con `DEBUG=False` |

### Inicio

```bash
# Levantar stack
docker compose up -d

# Migraciones y superusuario
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py createsuperuser

# Datos iniciales
docker compose exec backend python manage.py setup_roles
docker compose exec backend python manage.py create_mock_dropship_provider
```

### URLs

| Servicio | URL |
|----------|-----|
| Tienda | `http://localhost` |
| Panel admin | `http://localhost/<ADMIN_URL>/` (default dev: `admin/`) |
| API | `http://localhost/api/v1/` |

---

## Estructura del proyecto

```
├── backend/
│   ├── franja_pixelada/   # Settings, URLs, Celery, paginación, storage
│   ├── core/              # 4 middlewares, FranjaAdminSite (OTP), ExchangeRate, AdminAuditLog
│   ├── users/             # User (UUID/email), JWT cookies, CAPTCHA SVG, AvatarUpload, media tokens
│   ├── products/          # Catálogo completo, signals (cleanup/promote), validate_image_file
│   ├── orders/            # Cart, Order (Neki state machine), services/calculate_cart_totals
│   ├── payments/          # Stripe webhook · PayPal stub (501)
│   ├── loyalty/           # LoyaltyAccount, PointTransaction (inmutable), services con select_for_update
│   ├── returns/           # ReturnRequest (10 estados, VALID_TRANSITIONS), ReturnAuditLog (inmutable)
│   ├── proveedores/       # Supplier (Fernet), adapters (dropi/rest_generico/mock), LinkedProduct
│   └── templates/store/   # index.html — SPA completa (~9.900 líneas, sin build step)
├── .github/workflows/
│   ├── ci.dev.yml         # Desarrollo: no bloqueante (continue-on-error: true en todos los jobs)
│   ├── ci.prod.yml        # Producción: bloqueante — lint→tests→bandit→pip-audit→trivy(CRITICAL)→CodeQL v4→gitleaks
│   ├── security.yml       # Cron lunes 06:00 UTC: pip-audit, bandit, trivy, gitleaks
│   └── security.dev.yml   # Variante dev del cron de seguridad
├── nginx/                 # Configuración Nginx + SSL
├── docs/
│   └── dictionary-es-en.md  # Convención de nombres: español → inglés para campos de API
├── scripts/               # Utilidades de desarrollo (Windows batch)
├── DEPLOYMENT.md          # Guía completa de despliegue en producción
├── docker-compose.yml     # Stack base
├── docker-compose.prod.yml# Overrides producción (elimina bind mount de código fuente)
└── .env.example           # Plantilla de variables de entorno
```

---

## CI/CD

### Pipelines

| Archivo | Trigger | Comportamiento | Herramientas |
|---------|---------|---------------|--------------|
| `ci.dev.yml` | push/PR a `develop`, `feature/**` | No bloqueante — `continue-on-error: true` en todos los jobs | flake8, tests Django, bandit, pip-audit, trivy |
| `ci.prod.yml` | push/PR a `main`/`master` | Bloqueante — fallo corta el pipeline | flake8 → tests → bandit → pip-audit → trivy (CRITICAL) → CodeQL v4 → gitleaks → gate final |
| `security.yml` | Cron lunes 06:00 UTC + push a main | Informativo | pip-audit, bandit SARIF, trivy FS + imagen, gitleaks |
| `security.dev.yml` | Variante dev | Informativo | CodeQL v4, bandit, pip-audit, trivy, gitleaks |

### Herramientas de análisis (producción)

| Herramienta | Configuración | Bloquea en |
|------------|--------------|-----------|
| flake8 | `max-line-length=120`, excluye `migrations/` | Cualquier error |
| Bandit | severity/confidence ≥ medium, excluye tests | Job requerido por gate |
| pip-audit | Contra `requirements.txt` | Job requerido por gate |
| Trivy | Escaneo de imagen Docker, `ignore-unfixed: true` | `CRITICAL` únicamente |
| CodeQL v4 | Python, queries `security-extended` | Cualquier hallazgo |
| Gitleaks | `fetch-depth: 0` (historial completo) | No bloquea (continue-on-error) |

**Nota**: `security.yml` usa `github/codeql-action/upload-sarif@v3`; `ci.prod.yml` usa `@v4`. Pendiente normalizar a v4.

---

## Despliegue

```bash
# Construir imagen y levantar en modo producción
docker compose -f docker-compose.yml -f docker-compose.prod.yml build --no-cache backend
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

El override `docker-compose.prod.yml` elimina el bind mount del código fuente — el contenedor usa únicamente la imagen construida. Tras cualquier cambio en el backend, reconstruir antes de desplegar.

El startup de Django en producción (`DEBUG=False`) valida la configuración y lanza `ImproperlyConfigured` si detecta cualquiera de las siguientes condiciones: `DISABLE_ADMIN_OTP=True`, `DISABLE_CAPTCHA=True`, `TESTING=True`, `DB_PASSWORD` vacío, `REDIS_PASSWORD` vacío, `ENCRYPTION_KEY` ausente, o `ADMIN_URL` igual a `admin/` o `admin`.

Para la guía completa de despliegue, ver [`DEPLOYMENT.md`](./DEPLOYMENT.md).

---

## Estado del sistema

| Componente | Estado | Notas |
|-----------|--------|-------|
| Stripe PaymentIntent + webhook | Activo | 3DS automatic, verificación firma HMAC |
| Neki checkout (comprobante manual) | Activo | Despacho vía Celery tras verificación admin |
| PayPal | Stub — retorna 501 | Endpoints presentes en URLs |
| 2FA TOTP (admin) | Activo | OTPAdminSite, desactivable con `DISABLE_ADMIN_OTP` en dev |
| 2FA SMS (usuarios) | Pendiente | Campos `phone_2fa` y `two_factor_enabled` en `User`, sin integración activa |
| Dropshipping Dropi | Adapter disponible | Requiere credenciales reales en `Supplier` |
| Dropshipping REST genérico | Adapter disponible | Bearer + endpoint `/orders/` configurable |
| Dropshipping Mock | Activo | Para tests sin red; creado con `create_mock_dropship_provider` |
| Panel seguimiento envíos (cliente) | No implementado | Modelo `SupplierTracking` existe en DB |
| Notificaciones push | No implementado | — |

---

## Contribución

### Flujo de trabajo

```bash
git checkout -b feature/nombre-de-la-funcionalidad
git add <archivos>
git commit -m "tipo: descripción corta del cambio"
git push origin feature/nombre-de-la-funcionalidad
```

### Convenciones de commit

| Prefijo | Uso |
|---------|-----|
| `feat:` | Nueva funcionalidad |
| `fix:` | Corrección de error |
| `docs:` | Cambios en documentación |
| `refactor:` | Cambios de código sin nueva funcionalidad |
| `test:` | Agregar o corregir pruebas |
| `ci:` | Cambios en pipelines |
| `chore:` | Tareas de mantenimiento |

### Reglas para Pull Requests

- Todo PR apunta a `main` con al menos una revisión aprobada antes del merge.
- Los modelos nuevos deben incluir migración y registro en `admin_site` (no en `admin.site`).
- Los campos nuevos en modelos, serializers y respuestas API deben usar claves en inglés; registrar en `docs/dictionary-es-en.md`.
- Los nuevos signals deben registrarse en `AppConfig.ready()` del `apps.py` de la app correspondiente.
- Las mutaciones de saldo de fidelidad deben pasar por `loyalty/services.py`, nunca directamente al modelo.
- Las imágenes subidas por usuarios deben validarse con `validate_image_file` (magic bytes).
- Para tests que involucren CAPTCHA, usar `DISABLE_CAPTCHA=True` vía `@override_settings`.
- Las transiciones de estado de devoluciones deben usar `ReturnRequest.transition()`, nunca asignar `.status` directamente.
- No hacer merge si los tests fallan (`python manage.py test`).

---

## Roadmap

- [ ] Integrar SMS para 2FA de usuarios (campos `phone_2fa` y `two_factor_enabled` ya existen en `User`)
- [ ] Implementar PayPal (endpoints stub activos, retornan 501)
- [ ] Vista de seguimiento de envíos para clientes (modelo `SupplierTracking` ya existe en DB)
- [ ] Normalizar `upload-sarif` a v4 en `security.yml` (actualmente usa v3)
- [ ] App móvil — API REST ya expone todos los endpoints necesarios

---

## Licencia

Copyright (c) 2026 **Franja Pixelada**. Todos los derechos reservados.

Este software es de uso privado y propietario. Queda prohibida su reproducción,
distribución o uso para crear trabajos derivados sin autorización escrita del titular.
Consulta el archivo [`LICENSE`](./LICENSE) para los términos completos.

*Última actualización: 2026-04-18*
