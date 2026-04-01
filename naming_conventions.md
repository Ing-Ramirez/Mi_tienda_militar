# Convenciones de Nombres — Franja Pixelada

## Reglas generales

- Solo letras minúsculas en carpetas y archivos
- Sin espacios — usar guion bajo `_` como separador
- Sin tildes ni caracteres especiales (`á é í ó ú ñ ç # % & / ( )`)
- Sin guiones (`-`) — reemplazar por guion bajo `_`

---

## Carpetas

```
backend/
  franja_pixelada/  # paquete de configuración del proyecto Django
  core/             # app de seguridad y auditoría
  users/            # app de usuarios
  products/         # app de productos
  orders/           # app de pedidos
  payments/         # app de pagos
imagenes/           # imágenes del proyecto (logos, referencias)
documentacion/      # documentación técnica y reglamentos
scripts/            # shell scripts y SQL
files/              # uploads/media (vacío en repo)
```

**No permitido:**
```
Imagenes/           # inicial mayúscula
Documentacion/      # inicial mayúscula
archivos-temp/      # guion medio
```

---

## Archivos Python

Convención: **snake_case** — todo minúsculas, palabras separadas por `_`

```python
# Correcto
product_model.py
inventory_service.py
create_product.py

# Incorrecto
ProductModel.py
CrearProducto.py
InventarioGeneral.py
```

**Archivos Django que NO se renombran (convención del framework):**
```
manage.py    settings.py   urls.py     wsgi.py
asgi.py      admin.py      models.py   views.py
apps.py      tests.py      signals.py  middleware.py
serializers.py   validators.py   permissions.py
```

---

## Clases (PascalCase)

```python
# Correcto
class Product:
class ProductCategory:
class ProductVariant:
class InventoryLog:
class AdminAuditLog:

# Incorrecto
class product:
class product_category:
class productCategory:
```

---

## Variables y funciones (snake_case)

```python
# Correcto
product_price = 0
inventory_count = 0
created_at = models.DateTimeField()
def calculate_total():

# Incorrecto
ProductPrice = 0
productPrice = 0
product-price = 0
```

---

## Archivos HTML / CSS / JS

```
# HTML
product_list.html
product_detail.html
cart_summary.html
checkout_page.html
admin_dashboard.html

# CSS
main_styles.css
product_cards.css
admin_panel.css

# JavaScript
cart_manager.js
product_search.js
notification_system.js
admin_controls.js
```

*Excepción: `index.html` es el SPA completo y se mantiene como nombre único.*

---

## Imágenes

```
# Correcto
logo_franja_pixelada.svg
logo_patch.svg
bota_tactica_negra.jpg
parche_apellido_verde.png
banner_tienda_inicio.webp
chatgpt_imagen_tienda.png
whatsapp_referencia_1.jpeg

# Incorrecto
logo-patch.svg              # guion
ChatGPT Image 2026.png      # espacios y mayúsculas
WhatsApp Image PM.jpeg      # espacios y mayúsculas
Foto Producto.JPG           # espacios y extensión en mayúscula
```

**Extensiones permitidas para imágenes de producto:** `.jpg` `.jpeg` `.png` `.webp`
**Tamaño máximo:** 5 MB

---

## Documentos

```
# Correcto
rge_reglamento_uniformes.pdf
manual_operaciones_2026.pdf
politica_devoluciones.pdf

# Incorrecto
RGE 4-20.1 REGLAMENTO.pdf.pdf    # espacios + doble extensión
Manual Operaciones v2.0.docx      # espacios + mayúsculas
```

---

## Archivos de configuración

```
.env.example          # plantilla de variables de entorno
docker-compose.yml    # stack Docker (guion es estándar en YAML)
CLAUDE.md             # instrucciones para Claude Code (mayúsculas: convención)
README.md             # documentación raíz (mayúsculas: convención)
DEPLOYMENT.md         # guía de despliegue (mayúsculas: convención)
naming_conventions.md # este documento
```

*Los archivos `.md` en raíz de proyecto pueden usar MAYÚSCULAS cuando son documentos
de proyecto estándar (`README`, `CHANGELOG`, `LICENSE`, `DEPLOYMENT`, `CLAUDE`).*

---

## Advertencias activas

| Archivo | Estado | Acción recomendada |
|---------|--------|--------------------|
| `admin.py` (raíz) | Fuera de proyecto Django | Verificar si es duplicado y eliminar |
| `models.py` (raíz) | Fuera de proyecto Django | Verificar si es duplicado y eliminar |
| `settings.py` (raíz) | Fuera de proyecto Django | Verificar si es duplicado y eliminar |
| `views.py` (raíz) | Fuera de proyecto Django | Verificar si es duplicado y eliminar |
| `mnt/user-data/outputs/` | Copias generadas | No son fuente — no editar directamente |

---

*Última actualización: 2026-03-12*
