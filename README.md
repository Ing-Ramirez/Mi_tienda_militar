# Franja Pixelada — Tienda Virtual de Equipamiento Táctico

![Django](https://img.shields.io/badge/Django-5.0-092E20?style=flat-square&logo=django)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?style=flat-square&logo=postgresql)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=flat-square&logo=docker)
![License](https://img.shields.io/badge/Licencia-Propietaria-red?style=flat-square)

---

## Descripción

Franja Pixelada es una plataforma de comercio electrónico especializada en equipamiento militar y táctico para el mercado colombiano. Permite a clientes explorar el catálogo, realizar compras con personalización de prendas (bordado y grupo sanguíneo) y acumular puntos de fidelidad. Resuelve la necesidad de una tienda lista para producción con soporte nativo a dropshipping, pagos locales (Nequi) e internacionales (Stripe), y gestión de inventario en tiempo real.

---

## Características

- Catálogo de productos con variantes (talla, color), imágenes múltiples y reseñas de clientes
- Personalización de prendas: texto bordado y grupo sanguíneo por ítem
- Carrito persistente por usuario o sesión anónima, con cálculo de IVA (19%), envío y cupones
- Checkout Nequi (transferencia manual con comprobante de pago) y Stripe (tarjeta)
- Sistema de puntos de fidelidad: acumulación sobre subtotal, redención como descuento en COP
- Integración dropshipping: sincronización de catálogo y despacho automático de órdenes a proveedores
- Panel de administración con métricas KPI en tiempo real, 2FA TOTP y auditoría de sesiones
- API REST completa con JWT, rate limiting y paginación
- Frontend SPA sin paso de build — edición directa del archivo HTML
- Infraestructura Docker con Nginx, Certbot (TLS automático) y Celery para tareas asíncronas

---

## Demo / Capturas

> Las capturas de pantalla se agregan en `/docs/`. Para contribuir con imágenes del storefront o del panel admin, colócalas en esa carpeta y actualiza esta sección.

```
docs/
└── (agrega aquí: storefront.png, admin-dashboard.png, checkout.png)
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

**URLs de acceso:**

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
4. **Seguimiento** — Recibirás actualizaciones del estado de tu orden. Si pagaste con Nequi, el admin verifica el comprobante antes de despachar.
5. **Puntos de fidelidad** — Cada compra acumula puntos sobre el subtotal. Puedes usar hasta el 20% del total de tu próxima orden como descuento.

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
├── docker-compose.yml     # Stack base
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

- Todo PR debe apuntar a `main` y tener al menos una revisión aprobada antes de hacer merge.
- Los modelos nuevos deben incluir migración y registro en `admin_site` (no en `admin.site`).
- Los campos nuevos en modelos, serializers y respuestas API deben usar claves en inglés (ver `docs/dictionary-es-en.md`).
- No se hace merge si los tests fallan (`python manage.py test`).

---

## Soporte / Ayuda

- **Issues:** Abre un ticket en el repositorio de GitHub con una descripción del problema, pasos para reproducirlo y versión del entorno.
- Para despliegue en producción, consulta [`docs/DEPLOYMENT.md`](./docs/DEPLOYMENT.md).

---

## Roadmap

- [ ] App móvil (Android / iOS) consumiendo la API existente
- [ ] Integración con pasarela de pago local PSE
- [ ] Panel de seguimiento de envíos para el cliente final
- [ ] Notificaciones push de estado de orden

---

## Autores / Mantenedores

| Nombre | Rol |
|--------|-----|
| Equipo Franja Pixelada | Desarrollo y mantenimiento |

---

## Licencia

Copyright (c) 2026 **Franja Pixelada**. Todos los derechos reservados.

Este software es de uso privado y propietario. Queda prohibida su reproducción,
distribución o uso para crear trabajos derivados sin autorización escrita del titular.
Consulta el archivo [`LICENSE`](./LICENSE) para los términos completos.
