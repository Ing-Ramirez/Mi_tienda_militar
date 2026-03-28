# Diccionario oficial ES -> EN (datos/API)

Este documento define el mapeo oficial para estandarizar la capa de datos y API en ingles.

## Campos base

| Espanol | Ingles |
|---|---|
| usuario_id | user_id |
| nombre | name |
| correo | email |
| direccion | address |
| inventario | stock |
| creado_en | created_at |
| actualizado_en | updated_at |

## Productos

| Espanol | Ingles |
|---|---|
| producto_id | product_id |
| proveedor_id | supplier_id |
| precio_base | base_price |
| precio_final | final_price |
| talla | size |
| bordado | embroidery_text |
| rh | blood_type |
| en_stock | in_stock |
| es_bajo_stock | is_low_stock |
| colores_disponibles | available_colors |
| tallas_por_color | sizes_by_color |

## Proveedores

| Espanol | Ingles |
|---|---|
| proveedores | suppliers |
| credenciales | credentials |
| stock_proveedor | supplier_stock |
| stock_visible | visible_stock |
| proveedor_nombre | supplier_name |
| nombre_producto | product_name |
| estado | status |
| pendiente_envio | pending_dispatch |
| enviado | sent |
| confirmado | confirmed |
| en_transito | in_transit |
| entregado | delivered |
| error_proveedor | supplier_error |
| rechazado | rejected |

## Pagos

| Espanol | Ingles |
|---|---|
| metodo_pago | payment_method |
| nequi | nequi |
| estado_pago_manual | manual_payment_status |
| comprobante_pago | payment_proof |

## Reglas

- DB y API usan claves en ingles (`snake_case`).
- Frontend y admin muestran etiquetas en espanol.
- No se permiten claves nuevas en espanol en modelos, serializers ni respuestas API.
