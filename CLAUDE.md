# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

E-commerce platform for military/tactical equipment targeting the Colombian market.
- **Brand name:** Franja Pixelada
- **Currency:** COP | **Locale:** es-co | **Timezone:** America/Bogota
- **Tax:** 19% IVA | **Free shipping:** above COP 200,000 | **Base shipping:** COP 15,000

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend API | Django 5.0 + DRF 3.15 |
| Auth | JWT (SimpleJWT) — 60 min access / 7 day refresh |
| Database | PostgreSQL 16 |
| Cache | Redis 7 (falls back to `LocMemCache` if `REDIS_HOST` is unset) |
| Task Queue | Celery + Redis broker (DB 2) + `django_celery_beat` (periodic tasks) + `django_celery_results` (results stored in PostgreSQL) |
| Frontend | Single SPA — `backend/templates/store/index.html` (no build step) |
| Web Server | Nginx 1.25 + Gunicorn + Whitenoise |
| Admin UI | Jazzmin (Django admin theme with KPI dashboard) |
| Containers | Docker + Docker Compose + Certbot (auto-TLS renewal) |
| Payments | Stripe (active) + PayPal (stub — returns 501) + Neki (manual bank transfer) |
| Admin 2FA | django-otp TOTP (Google Authenticator) |

## Development Commands

```bash
# Initial setup
cp .env.example .env          # then edit with credentials

# Start full stack
docker-compose up -d

# Django management (run inside container)
docker-compose exec backend python manage.py migrate
docker-compose exec backend python manage.py createsuperuser
docker-compose exec backend python manage.py ensure_superuser --email-env DJANGO_SUPERUSER_EMAIL --password-env DJANGO_SUPERUSER_PASSWORD  # idempotent: creates or promotes existing user
docker-compose exec backend python manage.py collectstatic --no-input
docker-compose exec backend python manage.py setup_roles               # creates default permission groups
docker-compose exec backend python manage.py check_db                  # verify DB connectivity
docker-compose exec backend python manage.py create_mock_dropship_provider  # seed a MOCK supplier for testing

# Run tests
docker-compose exec backend python manage.py test <app_label>
docker-compose exec backend python manage.py test proveedores          # supplier integration tests

# Shell / DB access
docker-compose exec backend python manage.py shell
docker-compose exec db psql -U franja_pixelada_user franja_pixelada_store

# Celery (started automatically by docker-compose)
docker-compose logs celery         # view Celery worker output
docker-compose logs celery_beat    # view periodic task scheduler output
```

**Django admin:** `http://localhost/<ADMIN_URL>` (default: `admin/`)
**API root:** `http://localhost/api/v1/`

### Desarrollo local (Windows)

El override `docker-compose.dev.yml` expone PostgreSQL al host en el puerto 5432. Úsalo junto al base:

```bash
docker compose -p mi_tienda_militar -f docker-compose.yml -f docker-compose.dev.yml up -d
```

Scripts de conveniencia en `scripts/docker/` (Windows batch):
- `actualizar.bat` — recrear servicios sin limpiar imágenes/volúmenes (modo rápido). `actualizar.bat build` o `nocache` para rebuild.
- `reiniciar.bat` — limpieza profunda: baja todo, borra volúmenes e imágenes, reconstruye desde cero. Ofrece crear superusuario al final vía `create_superuser.ps1`.

### Producción (Docker Compose)

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

El override `docker-compose.prod.yml` quita el bind mount `./backend:/app` en `backend` y Celery: el código sale **solo de la imagen**. Tras cambiar el backend, reconstruir antes de desplegar:
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml build --no-cache backend
```

Variables relevantes (ver `.env.example`): `GUNICORN_WORKERS`, `GUNICORN_THREADS`, `GUNICORN_TIMEOUT`, `DB_CONN_MAX_AGE`, `SKIP_COLLECTSTATIC_ON_START`. Con `REDIS_HOST` definido, las sesiones de Django usan la caché Redis (`SESSION_ENGINE` cache); sin Redis siguen en base de datos — no uses `LocMemCache` para sesiones con varios workers.

### Disabling TOTP in development
Add `DISABLE_ADMIN_OTP=True` to `.env` — removes `django-otp` from `INSTALLED_APPS` and middleware so you can log into `/admin/` with only username + password.

## Architecture

All Django code lives under `backend/`. The SPA is at `backend/templates/store/index.html`.

```
backend/
├── franja_pixelada/    # Django project (settings.py, urls.py, wsgi.py, celery.py)
├── core/               # Security models, middleware, custom admin site
├── users/              # Custom User model (email as USERNAME_FIELD)
├── products/           # Product catalog
├── orders/             # Cart, Order, Coupon; signals + Celery tasks for dispatch
├── payments/           # Stripe & PayPal views
├── proveedores/        # Dropshipping supplier integration (adapters, sync, dispatch)
├── loyalty/            # Points system (LoyaltyAccount, PointTransaction, services)
├── returns/            # Customer return requests (state machine + audit log)
├── templates/store/    # index.html — the entire SPA
├── manage.py
└── requirements.txt
```

### Django Apps

| App | Key models | Notes |
|-----|-----------|-------|
| `core` | `LoginAttempt`, `AdminAuditLog` | Security middleware, custom `FranjaAdminSite` |
| `users` | `User` (extends `AbstractUser`) | UUID PK, email login, optional SMS 2FA fields |
| `products` | `Category`, `Tag`, `Product`, `ProductImage`, `ProductVariant`, `ProductReview`, `InventoryLog`, `Favorito` | Slug-based routing; `Product` has `stock_by_size` (JSON dict `{"S":5,"M":10}`), `available_sizes` (derived list), `benefits` (JSON list, max 5), `requires_size` flag |
| `orders` | `Cart`, `CartItem`, `Address`, `Order`, `OrderItem`, `Coupon` | Supports personalization (bordado + RH); Neki manual payment |
| `payments` | `Payment` | Stripe PaymentIntent + webhook; PayPal is a stub |
| `proveedores` | `Supplier`, `SupplierProduct`, `SupplierVariant`, `LinkedProduct`, `SupplierOrder`, `SupplierTracking`, `SupplierLog` | Dropshipping: sync, dispatch, webhook reception, stock capping |
| `loyalty` | `LoyaltyAccount` (1:1 User), `PointTransaction` (immutable audit log) | Points system: earn on `subtotal`, redeem as COP discount; `PointTransaction` is never editable or deletable |
| `returns` | `ReturnRequest`, `ReturnItem`, `ReturnEvidence`, `ReturnAuditLog` | Return requests with strict state machine (`VALID_TRANSITIONS` dict); `ReturnAuditLog` is append-only; max attempts per order configurable via `RETURN_MAX_ATTEMPTS_PER_ORDER` (default 3) |

### Services Layer

Business logic is extracted into service modules, not kept in views:
- `orders/services/` (package) — `calculate_cart_totals()`, `create_order_from_cart()`, `create_order_neki_from_cart()`, `build_neki_checkout_preview()`, `validate_cart_for_checkout()` (checks stock per size before checkout); all public via `orders.services`
- `orders/signals.py` — auto-enqueues `send_order_to_provider` Celery task when `manual_payment_status` transitions to `VERIFIED`
- `orders/tasks.py` — `send_order_to_provider` (max 3 retries, exponential backoff)
- `proveedores/services/` — `sincronizacion`, `pedidos`, `despacho`, `vinculos`, `stock_dinamico`, `tracking`, `normalizacion`
- `proveedores/services/adapters/` — `rest_generico`, `dropi`, `mock`; adapter is chosen via `Supplier.adapter` field and dispatched by `adapters/registry.py`
- `proveedores/tasks.py` — `procesar_webhook` (3 retries), `enviar_pedido_a_proveedor` (3 retries), `sincronizacion_periodica` (runs every 30 min via Celery Beat)
- `loyalty/services.py` — `get_or_create_account()`, `calculate_points_earned()`, `preview_redemption()`, `assign_points_for_order()` (idempotent, post-payment), `redeem_points_for_order()` (atomic with order creation), `reverse_points_for_order()` (on cancel/refund); all mutations use `select_for_update()` + F-expressions
- `loyalty/tasks.py` — `assign_loyalty_points` (3 retries), `reverse_loyalty_points` (3 retries)
- `loyalty/signals.py` — triggers `reverse_loyalty_points` when `Order.status` transitions to `cancelled` or `refunded`
- `returns/` — state machine enforced via `VALID_TRANSITIONS` in `returns/models.py`; use `ReturnRequest.transition(new_status, changed_by, note)` — never set `.status` directly

### Dropshipping / Supplier Flow

1. **Webhook** arrives at `POST /api/v1/proveedores/webhooks/<slug>/` → HMAC validated → logged → `procesar_webhook` enqueued.
2. **Stock sync** applies `min(supplier_stock, LinkedProduct.max_stock)` ("capped stock sync") and writes to `products.Product.stock`.
3. **Order dispatch** triggers **only** when admin marks `Order.manual_payment_status = VERIFIED`:
   - `orders/signals.py` detects the transition and calls `orders.tasks.send_order_to_provider.delay(order_id)`.
   - The task calls `proveedores.services.despacho.despachar_orden_a_proveedores(order)`.
4. **Adapter selection**: Each `Supplier` has an `adapter` field (`rest_generico`, `dropi`, `mock`). The adapter registry resolves the correct HTTP client class.
5. **Supplier credentials** are encrypted at rest using Fernet (`ENCRYPTION_KEY`). Use the `credenciales` property — never access `_credentials` directly.
6. Records are **never hard-deleted** — use status fields (`is_active`, `status`) instead.

### Security Architecture

`core/middleware.py` provides three middleware classes loaded in this order:
1. **`SecurityHeadersMiddleware`** — Generates a per-request CSP nonce, sets `Content-Security-Policy` (with `nonce-{nonce}` for inline scripts/styles), `Permissions-Policy`, etc. The nonce is exposed to templates via the `csp_nonce_context` context processor — `index.html` must use `{{ csp_nonce }}` on its `<script>` and `<style>` tags.
2. **`AdminBruteForceMiddleware`** — Tracks failed admin logins in `LoginAttempt`. Soft lock (15 min) at 5 failures, hard lock (60 min) at 10 failures. Sends email alerts to `ADMIN_SECURITY_EMAIL`.
3. **`AdminSessionTimeoutMiddleware`** — Auto-logout after 30 min of inactivity in the admin panel.

`core/admin_site.py` defines `FranjaAdminSite`, a custom `OTPAdminSite` instance (`admin_site`) that requires TOTP verification. It is imported in `franja_pixelada/urls.py` instead of using the default `admin.site`. **All apps must register models with `admin_site`, not `admin.site`.** `each_context()` injects live KPI metrics into every admin page (orders today/month, revenue MTD, active products, low-stock count, out-of-stock count); errors in this block are silently swallowed so the admin never breaks over a bad metric query.

### Admin URL

The admin URL is configurable via `ADMIN_URL` in `.env` (defaults to `admin/`). Changing it reduces automated attack surface. It must be kept in sync between `.env` and `franja_pixelada/urls.py` (which reads it from `settings.ADMIN_URL`). Production validation blocks the default `admin/` value.

### JWT Auth — Cookie-based refresh token

The refresh token is **not** returned in the response body. `users/views.py` stores it as an `HttpOnly` cookie named `refresh_token` scoped to `/api/v1/auth/`. The `/api/v1/auth/token/refresh/` endpoint reads the cookie automatically. The access token is returned in the response body as `access`. Frontend code must never try to parse or store the refresh token from the response.

### API Endpoints (`/api/v1/`)

- `auth/` — register, login, token refresh (cookie-based), logout, me
- `products/` — list/detail (slug), featured, new_arrivals, add_review
  - Filter: `?category=<uuid>&status=active&is_featured=true&is_new=true&personalization_type=bordado|rh|none`
  - Search: `?search=<name|sku|description>`
  - **Note:** `featured` and `new_arrivals` actions return results without DRF pagination
- `products/categories/` — list/detail (slug)
- `products/favoritos/` — list + toggle (POST with `product_id`, authenticated)
- `orders/cart/` — my_cart, add_item, update_item, remove_item, clear, calculate_totals
  - `calculate_totals` accepts `?coupon=<CODE>` query param
- `orders/checkout/` — **Neki (manual):** `GET` datos ficticios de pago + totales; `POST` multipart (mismos campos de envío que checkout + archivo `payment_proof`). Crea orden `manual_payment_status=PENDING`; dropshipping solo tras admin **VERIFIED** (Celery `send_order_to_provider`).
- `orders/orders/` — list; checkout legacy JSON: `POST /orders/orders/checkout/` (no dispara proveedores hasta verificación Neki u otro flujo explícito)
  - Checkout required fields: `shipping_full_name`, `shipping_phone`, `shipping_department`, `shipping_city`, `shipping_address_line1`, `email`
- `orders/coupons/validate/` — POST `{code, subtotal}`, returns discount details
- `payments/stripe/` — create PaymentIntent (`POST {order_number}`), webhook (CSRF-exempt)
  - Stripe `amount` is `order.total × 100` (COP centavos)
- `payments/paypal/` — stub (501)
- `proveedores/webhooks/<slug>/` — POST, public (no JWT), HMAC-validated; returns 200 immediately and enqueues async processing
- `proveedores/estado/` — GET, admin only; all supplier statuses
- `proveedores/<slug>/logs/` — GET, admin only; last 100 logs for a supplier
- `proveedores/<slug>/catalogo/` — GET, admin only; synced variants (`?estado=activo|agotado`, `?sin_vincular=true`)
- `proveedores/vinculados/` — GET list / POST create link (admin only)
- `proveedores/vinculados/<id>/` — GET / PATCH / DELETE a specific link (admin only)
- `proveedores/vinculados/<id>/recalcular/` — POST, forces immediate stock recalculation (admin only)
- `loyalty/balance/` — GET, returns `points_balance`, `balance_in_cop`, `point_value_cop`, `points_per_cop`
- `loyalty/transactions/` — GET, paginated history of `PointTransaction` for the authenticated user
- `loyalty/preview/` — POST `{points_to_use, order_total}`, returns discount preview without persisting
- `returns/` — GET list / POST create return request (authenticated)
  - `returns/<uuid>/` — GET detail (owner or staff)
  - `returns/<uuid>/evidence/` — POST upload image / DELETE remove (only while status=`requested`)
  - `returns/<uuid>/transition/` — POST `{status}`, admin only; enforces `VALID_TRANSITIONS`
  - `returns/eligibility/<order_id>/` — GET, checks if order qualifies (delivered, within window, no active return)
  - `returns/admin/list/` — GET, admin-only full list
  - `returns/policy/` — GET, returns the policy document text
- `core/exchange-rate/live/` — GET, live exchange rate (USD→COP)

### Non-API URLs

- `/health/` — liveness probe (no auth)
- `/internal/staff/orders/<uuid>/payment-proof/` — Neki payment proof for staff (Django session auth, not JWT)

### Naming Convention (ES → EN)

`docs/dictionary-es-en.md` is the authoritative mapping for field names. Rules:
- **DB models, serializers, and API responses use English keys** (`snake_case`).
- Admin and frontend labels display in Spanish.
- **No new Spanish-language keys** in models, serializers, or API responses.

Key mappings: `talla` → `size`, `bordado` → `embroidery_text`, `rh` → `blood_type`, `estado` → `status`, `credenciales` → `credentials`.

### Key Conventions

- **UUID PKs** on all models except `Tag` (which uses Django's default BigAutoField)
- **Slug routing** for products and categories (`lookup_field = 'slug'`)
- **Pagination:** 20 items/page
- **Rate limiting:** 600 req/hr (anon), 3000 req/hr (authenticated), 5/min (login)
- **Permissions:** `IsAuthenticatedOrReadOnly` globally; cart/orders/favorites require auth; proveedores endpoints require `IsAdminUser`
- **Password hashing:** Argon2 primary, PBKDF2 as fallback (auto-upgraded on next login)
- **CartItem uniqueness:** `(cart, product, variant, talla, bordado, rh)` — personalized items are never merged
- **OrderItem** stores a snapshot of product/variant fields at time of purchase (name, SKU, etc.)
- **InventoryLog** must record every stock mutation with an action type and before/after values
- **ProductReview** is unique per `(product, user)` — one review per user per product
- **Supplier soft-delete:** never call `.delete()` on supplier records — use status/is_active fields
- **PointTransaction immutability:** never call `.save()` or `.delete()` on existing transactions — admin enforces this; append-only log
- **Loyalty idempotency:** `Order.loyalty_points_processed` flag + existence check for `EARN` transaction prevent double-accrual on retries
- **Points base:** earned on `order.subtotal` only (excludes IVA and shipping)
- **Loyalty earn trigger:** both Neki VERIFIED (`orders/signals.py`) and Stripe `payment_intent.succeeded` (`payments/views.py`) enqueue `assign_loyalty_points` task
- **Loyalty reversal trigger:** `loyalty/signals.py` detects `Order.status` → `cancelled`/`refunded` and enqueues `reverse_loyalty_points`
- **Returns state machine:** transitions are strictly enforced via `VALID_TRANSITIONS` in `returns/models.py`; use `ReturnRequest.transition(new_status, changed_by, note)` — never set `.status` directly
- **ReturnAuditLog immutability:** append-only; never call `.save()` or `.delete()` on existing log entries
- **Returns window:** 30 days from delivery (`RETURN_WINDOW_DAYS_NEW`); shipment deadline is 5 days after approval (`RETURN_SHIPMENT_WINDOW_DAYS`)
- **Returns eligibility:** order must be `delivered`; excluded by category slug list (`RETURN_EXCLUDED_CATEGORY_SLUGS`) or SKU prefix (`RETURN_SPECIAL_SKU_PREFIXES` default `['DIGI-', 'SPC-']`)

### Updating the Frontend

Edit `backend/templates/store/index.html` directly — it is a self-contained single file (HTML + CSS + JS). The `{{ csp_nonce }}` template variable must remain on all inline `<script nonce="...">` and `<style nonce="...">` tags.

### Docker Network Topology

Two bridge networks isolate layers:
- `app_net` — Nginx ↔ Backend ↔ Redis ↔ Celery workers
- `db_net` — Backend ↔ PostgreSQL only (`internal: true`, not reachable from Nginx or Redis)

The backend port 8000 is not exposed to the host; it is only reachable through Nginx on `app_net`.

## Environment Variables

See `.env.example`. Key variables:
- `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `DOMAIN_NAME`
- `ADMIN_URL` — admin panel path (keep obscure in production; blocked if set to `admin/` in prod)
- `DISABLE_ADMIN_OTP` — set `True` in development to skip TOTP
- `ADMIN_SECURITY_EMAIL` — receives brute-force alert emails
- `DB_*`, `REDIS_*`
- `ENCRYPTION_KEY` — Fernet key for encrypting supplier API credentials. **Required in production.** Generate with: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- `STRIPE_PUBLIC_KEY`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`
- `PAYPAL_CLIENT_ID`, `PAYPAL_SECRET`, `PAYPAL_MODE`
- `NEKI_DISPLAY_PHONE`, `NEKI_DISPLAY_ACCOUNT_NAME` — shown to customers on the Neki checkout screen
- `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`
- `TAX_RATE` (default `0.19`), `FREE_SHIPPING_THRESHOLD` (default `200000`), `BASE_SHIPPING_COST` (default `15000`)
- `TRUSTED_PROXY_COUNT` — number of trusted proxy hops (default `1` for Nginx in Docker)
- `GUNICORN_WORKERS`, `GUNICORN_THREADS`, `GUNICORN_TIMEOUT`, `DB_CONN_MAX_AGE`, `SKIP_COLLECTSTATIC_ON_START`
- `LOYALTY_POINTS_PER_COP` (default `1000`) — COP in subtotal that generate 1 point
- `LOYALTY_POINT_VALUE_COP` (default `10`) — COP value per point when redeeming
- `LOYALTY_MAX_REDEMPTION_PCT` (default `0.20`) — max fraction of order total redeemable via points
- `RETURN_MAX_ATTEMPTS_PER_ORDER` (default `3`) — max return attempts per order
- `RETURN_EXCLUDED_CATEGORY_SLUGS` — comma/list of category slugs ineligible for returns
- `RETURN_EXCLUDE_DIGITAL_PRODUCTS` (default `True`) — exclude SKUs matching `RETURN_SPECIAL_SKU_PREFIXES`
- `RETURN_SPECIAL_SKU_PREFIXES` (default `['DIGI-', 'SPC-']`) — SKU prefixes ineligible for returns

## Local Project Context Skill

To ensure high-precision edits with full project context, use the local skill:

- Cursor: `.cursor/skills/contexto-proyecto-franja-pixelada/SKILL.md`
- Claude local: `.claude/skills/contexto-proyecto-franja-pixelada/SKILL.md`

This skill summarizes architecture, critical business flows, security constraints, Docker model, and editing checklists for safe modifications.
