# Franja Pixelada — Tienda Virtual de Equipamiento Táctico

[![Django](https://img.shields.io/badge/Django-5.0-092E20?style=flat-square&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![DRF](https://img.shields.io/badge/DRF-3.15-red?style=flat-square&logo=django&logoColor=white)](https://www.django-rest-framework.org/)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?style=flat-square&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?style=flat-square&logo=redis&logoColor=white)](https://redis.io/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white)](https://docs.docker.com/compose/)
[![Licencia](https://img.shields.io/badge/Licencia-Propietaria-red?style=flat-square)](./LICENSE)

---

## Descripción

**Franja Pixelada** es una plataforma de comercio electrónico especializada en equipamiento militar y táctico para el mercado colombiano. Permite explorar el catálogo, realizar compras con personalización de prendas (bordado y grupo sanguíneo) y acumular puntos de fidelidad.

Diseñada para producción con soporte nativo a dropshipping, pagos locales (Nequi) e internacionales (Stripe), gestión de inventario en tiempo real y panel de administración seguro con 2FA.

---

## Características

- Catálogo con variantes (talla, color), imágenes múltiples y reseñas verificadas
- Personalización de prendas: texto bordado y grupo sanguíneo por ítem
- Carrito persistente con IVA (19%), costo de envío y cupones de descuento
- Checkout Nequi (comprobante manual) y Stripe (tarjeta de crédito/débito)
- Sistema de puntos de fidelidad: acumulación sobre subtotal, redención en COP
- Integración dropshipping: sincronización de catálogo y despacho automático a proveedores
- Panel admin con KPIs en tiempo real, 2FA TOTP y auditoría de sesiones
- API REST completa con JWT, rate limiting y paginación
- Frontend SPA sin paso de build — archivo HTML editable directamente
- Infraestructura Docker con Nginx, Certbot (TLS automático) y Celery

---

## Demo / Capturas

> Las capturas se ubican en `docs/`. Para agregar imágenes del storefront o panel admin, colócalas en esa carpeta.

| Vista | Descripción |
|-------|-------------|
| ![Storefront](docs/storefront.png) | Catálogo principal |
| ![Admin Dashboard](docs/admin-dashboard.png) | Panel de administración con KPIs |
| ![Checkout](docs/checkout.png) | Flujo de pago |

```
docs/
└── storefront.png
└── admin-dashboard.png
└── checkout.png
```

---

## Instalación

### Requisitos previos

- Docker 24+ y Docker Compose 2.x
- Git

### Pasos

```bash
# 1. Clonar el repositorio
git clone <url-del-repositorio>
cd Mi_tienda_militar

# 2. Crear el archivo de entorno
cp .env.example .env
```

Editar `.env` con los valores reales. Variables mínimas para desarrollo:

```env
SECRET_KEY=<genera con: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())">
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DB_PASSWORD=<contraseña-local>
REDIS_PASSWORD=<contraseña-redis>
DISABLE_ADMIN_OTP=True
```

```bash
# 3. Levantar el stack completo
docker compose up -d

# 4. Aplicar migraciones y crear superusuario
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py createsuperuser

# 5. (Opcional) Cargar roles y proveedor de prueba
docker compose exec backend python manage.py setup_roles
docker compose exec backend python manage.py create_mock_dropship_provider
```

### URLs de acceso

| Servicio | URL |
|----------|-----|
| Tienda | `http://localhost` |
| Panel admin | `http://localhost/admin/` |
| API | `http://localhost/api/v1/` |

---

## Uso

1. **Explorar el catálogo** — Navega por categorías, filtra por talla o tipo de personalización y agrega productos al carrito.
2. **Personalizar prenda** — Al agregar un producto compatible, escribe el texto de bordado y/o selecciona el grupo sanguíneo.
3. **Checkout** — Completa los datos de envío y elige entre Nequi (sube comprobante) o pago con tarjeta vía Stripe.
4. **Seguimiento** — Recibirás actualizaciones del estado de tu orden. Con Nequi, el admin verifica el comprobante antes de despachar.
5. **Puntos de fidelidad** — Cada compra acumula puntos sobre el subtotal. Usa hasta el 20% del total de tu próxima orden como descuento.

---

## Estructura del proyecto

```
├── backend/
│   ├── franja_pixelada/   # Configuración Django (settings, urls, celery)
│   ├── core/              # Seguridad: middleware CSP, brute-force, sesión admin
│   ├── users/             # Modelo User con UUID PK y login por email
│   ├── products/          # Catálogo: Product, Category, Variant, Review, InventoryLog
│   ├── orders/            # Cart, Order, Coupon; servicios de checkout y totales
│   ├── payments/          # Stripe webhook + PayPal stub
│   ├── proveedores/       # Dropshipping: adaptadores, sincronización, despacho
│   ├── loyalty/           # Puntos de fidelidad: LoyaltyAccount, PointTransaction
│   └── templates/store/   # index.html — SPA completa (HTML + CSS + JS)
├── nginx/                 # Configuración Nginx con SSL
├── docs/                  # Capturas, diccionario de campos y guía de despliegue
├── scripts/               # Utilidades de desarrollo
├── docker-compose.yml     # Stack base (desarrollo)
├── docker-compose.prod.yml# Overrides de producción (sin bind mount)
└── .env.example           # Plantilla de variables de entorno
```

---

## Contribución

### Flujo de trabajo

```bash
# 1. Crear rama desde main
git checkout -b feature/nombre-de-la-funcionalidad

# 2. Realizar cambios y confirmarlos
git add <archivos>
git commit -m "tipo: descripción corta del cambio"

# 3. Subir la rama y abrir Pull Request
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

### Reglas para Pull Requests

- Todo PR debe apuntar a `main` y tener al menos una revisión aprobada antes del merge.
- Los modelos nuevos deben incluir migración y registro en `admin_site` (no en `admin.site`).
- Los campos nuevos en modelos, serializers y respuestas API deben usar claves en inglés (ver `docs/dictionary-es-en.md`).
- No se hace merge si los tests fallan (`python manage.py test`).

---

## Despliegue

### Producción con Docker Compose

```bash
# Construir imágenes y levantar en modo producción
docker compose -f docker-compose.yml -f docker-compose.prod.yml build --no-cache backend
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

El override `docker-compose.prod.yml` elimina el bind mount del código fuente — el contenedor usa solo la imagen construida.

### Variables de entorno clave para producción

| Variable | Descripción |
|----------|-------------|
| `DEBUG` | Debe ser `False` |
| `DOMAIN_NAME` | Dominio del servidor |
| `ADMIN_URL` | Ruta del admin (evitar `admin/`) |
| `ENCRYPTION_KEY` | Clave Fernet para credenciales de proveedores |
| `STRIPE_SECRET_KEY` | Clave secreta de Stripe |

> Para la guía completa de despliegue, consulta [`docs/DEPLOYMENT.md`](./docs/DEPLOYMENT.md).

---

## Roadmap

- [ ] App móvil (Android / iOS) consumiendo la API existente
- [ ] Integración con pasarela de pago PSE
- [ ] Panel de seguimiento de envíos para el cliente final
- [ ] Notificaciones push de estado de orden

---

## Autores

| Nombre | Rol |
|--------|-----|
| Equipo Franja Pixelada | Desarrollo y mantenimiento |

---

## Licencia

Copyright (c) 2026 **Franja Pixelada**. Todos los derechos reservados.

Este software es de uso privado y propietario. Queda prohibida su reproducción,
distribución o uso para crear trabajos derivados sin autorización escrita del titular.
Consulta el archivo [`LICENSE`](./LICENSE) para los términos completos.
