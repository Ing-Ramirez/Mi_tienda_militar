# 🪖 Franja Pixelada — Guía de Despliegue Completa

## Requisitos del Servidor
- Ubuntu 22.04 LTS
- Docker 24+ y Docker Compose 2.x
- Dominio apuntando a tu IP
- Mínimo 2GB RAM, 20GB disco

---

## 1. PREPARAR EL SERVIDOR

```bash
# Actualizar sistema
sudo apt update && sudo apt upgrade -y

# Instalar Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker

# Instalar Docker Compose
sudo apt install docker-compose-plugin -y

# Verificar instalación
docker --version && docker compose version
```

---

## 2. CLONAR Y CONFIGURAR

```bash
# Clonar el repositorio
git clone https://github.com/tuusuario/tactistore.git
cd tactistore

# Crear archivo de variables de entorno
cp .env.example .env
nano .env
```

### Configurar `.env`:

```env
# ── SEGURIDAD ────────────────────────────────────
SECRET_KEY=genera-una-clave-de-50-caracteres-random
DEBUG=False
ALLOWED_HOSTS=tudominio.com,www.tudominio.com
# ── BASE DE DATOS ─────────────────────────────────
DB_NAME=franja_pixelada_store
DB_USER=postgres
DB_PASSWORD=contraseña-muy-segura-aqui

# ── REDIS ─────────────────────────────────────────
REDIS_PASSWORD=redis-contraseña-segura

# ── STRIPE ───────────────────────────────────────
STRIPE_PUBLIC_KEY=pk_live_...
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# ── PAYPAL ───────────────────────────────────────
PAYPAL_CLIENT_ID=tu-paypal-client-id
PAYPAL_SECRET=tu-paypal-secret
PAYPAL_MODE=live  # sandbox para pruebas

# ── EMAIL ─────────────────────────────────────────
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=tucorreo@gmail.com
EMAIL_HOST_PASSWORD=contraseña-app-gmail
DEFAULT_FROM_EMAIL=Franja Pixelada <noreply@tudominio.com>

# ── CORS ──────────────────────────────────────────
CORS_ALLOWED_ORIGINS=https://tudominio.com,https://www.tudominio.com
```

---

## 3. CERTIFICADO SSL (Let's Encrypt)

```bash
# Primero, levantar nginx solo para HTTP
docker compose up nginx certbot -d

# Obtener certificado
docker compose run --rm certbot certonly \
  --webroot \
  --webroot-path=/var/www/certbot \
  -d tudominio.com \
  -d www.tudominio.com \
  --email tu@email.com \
  --agree-tos \
  --no-eff-email
```

---

## 4. CONSTRUIR Y LEVANTAR

```bash
# Construir todas las imágenes
docker compose build --no-cache

# Levantar todos los servicios
docker compose up -d

# Ver logs
docker compose logs -f

# Verificar que todos estén corriendo
docker compose ps
```

---

## 5. CONFIGURAR DJANGO

```bash
# Crear superusuario admin
docker compose exec backend python manage.py createsuperuser

# Cargar datos iniciales (categorías, productos de ejemplo)
docker compose exec backend python manage.py loaddata fixtures/initial_data.json

# Verificar migraciones
docker compose exec backend python manage.py showmigrations
```

---

## 6. CONFIGURAR STRIPE WEBHOOK

1. Ir a [stripe.com/dashboard/webhooks](https://dashboard.stripe.com/webhooks)
2. Crear endpoint: `https://tudominio.com/api/v1/payments/stripe/webhook/`
3. Eventos a escuchar:
   - `payment_intent.succeeded`
   - `payment_intent.payment_failed`
4. Copiar el webhook secret al `.env`

---

## 7. VERIFICAR EL DESPLIEGUE

```bash
# Probar productos (no existe /health/ — verificar con la API directamente)
curl https://tudominio.com/api/v1/products/

# Ver logs en tiempo real
docker compose logs -f backend nginx
```

---

## COMANDOS ÚTILES DE MANTENIMIENTO

```bash
# Reiniciar un servicio
docker compose restart backend

# Ver logs de un servicio
docker compose logs -f backend

# Actualizar el código
git pull origin main
docker compose -f docker-compose.yml -f docker-compose.prod.yml build --no-cache backend
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Backup de la base de datos
docker compose exec db pg_dump -U postgres franja_pixelada_store > backup_$(date +%Y%m%d).sql

# Restaurar base de datos
cat backup.sql | docker compose exec -T db psql -U postgres franja_pixelada_store

# Escalar backend (para más tráfico)
docker compose up -d --scale backend=3

# Ver tamaño de volúmenes
docker system df

# Limpiar imágenes no usadas
docker system prune -f
```

---

## 📊 PANEL ADMINISTRATIVO

Accede al panel de Django Admin en la URL configurada en `ADMIN_URL` (`.env`):
```
https://tudominio.com/<ADMIN_URL>/
```
> ⚠️ En producción **no uses** `admin/` como valor de `ADMIN_URL` — el sistema lo bloquea. Usa una ruta no predecible.

Funcionalidades disponibles:
- ✅ Agregar/editar/eliminar productos
- ✅ Gestionar inventario y stock
- ✅ Ver y gestionar órdenes
- ✅ Administrar usuarios
- ✅ Crear cupones de descuento
- ✅ Ver historial de inventario
- ✅ Gestionar categorías

---

## 🛒 GUÍA: AGREGAR PRODUCTOS

### Opción 1: Panel de Admin (Fácil)

1. Ir a `https://tudominio.com/<ADMIN_URL>/` (el valor de `ADMIN_URL` en `.env`)
2. **Productos** → Agregar producto
3. Llenar los campos:
   - **SKU**: Código único (ej: MT-001)
   - **Nombre**: Nombre del producto
   - **Categoría**: Seleccionar del menú desplegable
   - **Precio**: En pesos colombianos
   - **Stock**: Cantidad disponible
   - **Imágenes**: Subir fotos del producto
   - **Estado**: Activo/Inactivo/Agotado
4. Guardar

### Opción 2: API REST (Para importación masiva)

```bash
# Obtener token de admin
TOKEN=$(curl -X POST https://tudominio.com/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@email.com","password":"tucontraseña"}' \
  | jq -r '.access')

# Crear producto
curl -X POST https://tudominio.com/api/v1/products/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "sku": "MT-001",
    "name": "Mochila Táctica 45L",
    "description": "Descripción completa...",
    "price": "189900.00",
    "stock": 50,
    "category": "UUID_DE_CATEGORIA",
    "status": "active",
    "is_featured": true
  }'

# Actualizar stock rápidamente
curl -X POST https://tudominio.com/api/v1/products/mochila-tactica-45l/update_stock/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"stock": 75, "action": "adjustment", "notes": "Recepción de mercancía"}'
```

### Opción 3: Importar desde CSV

```bash
# Crear script de importación
docker compose exec backend python manage.py import_products products.csv
```

---

## 🔒 SEGURIDAD EN PRODUCCIÓN

Checklist:
- [ ] `DEBUG=False`
- [ ] `SECRET_KEY` única y segura (50+ chars)
- [ ] SSL/HTTPS activo
- [ ] Passwords de BD seguros
- [ ] Backups automáticos configurados
- [ ] Rate limiting en Nginx activo
- [ ] Variables de pago en `.env` (nunca en código)
- [ ] Webhook de Stripe verificado
- [ ] CORS configurado solo para tu dominio

---

## 📈 ESCALABILIDAD

Para mayor tráfico:

```yaml
# En docker-compose.yml, agregar:
backend:
  deploy:
    replicas: 4
    resources:
      limits:
        cpus: '0.5'
        memory: 512M
```

Para base de datos de alta disponibilidad:
- Usar RDS (AWS) o Cloud SQL (GCP)
- Cambiar `DB_HOST` al host externo
- Eliminar servicio `db` del compose

---

## 📞 SOPORTE

- Documentación Django: https://docs.djangoproject.com
- Documentación Stripe: https://stripe.com/docs
- Issues: github.com/tuusuario/franja-pixelada/issues
