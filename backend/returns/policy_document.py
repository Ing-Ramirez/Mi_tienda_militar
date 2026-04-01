"""
Texto estructurado de políticas de devolución para API y UI (es-CO).
Los números de plazo se toman de los mismos valores que el modelo/servicio.
"""
from __future__ import annotations

from typing import Any


def build_return_policy_document(
    *,
    window_days_new: int,
    window_days_used: int,
    shipment_window_days: int,
    excluded_category_slugs: list[str],
    digital_exclusion_enabled: bool,
    special_sku_prefixes: list[str],
) -> dict[str, Any]:
    ex_cat = ', '.join(excluded_category_slugs) if excluded_category_slugs else 'ninguna categoría excluida por configuración'
    sku_prev = ', '.join(special_sku_prefixes) if special_sku_prefixes else 'ninguno'
    dig = (
        'Los productos marcados como digitales o excluidos por prefijo de SKU no aplican a devolución estándar.'
        if digital_exclusion_enabled
        else 'La exclusión de productos digitales está desactivada en esta tienda; consulta cada caso con soporte.'
    )
    return {
        'introduction': (
            'Estas políticas regulan el derecho de retracto, cambios y devoluciones en Franja Pixelada. '
            'Al solicitar una devolución declaras que has leído y aceptas las condiciones siguientes, '
            'sin perjuicio de tus derechos como consumidor conforme a la normativa colombiana aplicable.'
        ),
        'sections': [
            {
                'id': 'deadlines',
                'title': 'Plazos',
                'paragraphs': [
                    f'Producto nuevo sin uso (empaque y etiquetas originales cuando corresponda): '
                    f'hasta {window_days_new} días calendario desde la entrega del pedido.',
                    f'Producto usado o sin empaque original: hasta {window_days_used} días calendario desde la entrega, '
                    f'sujeto a evaluación y a categorías no excluidas.',
                    f'Tras la aprobación de la devolución, dispones de hasta {shipment_window_days} días para '
                    f'enviar el artículo con la guía o instrucciones que te indiquemos.',
                ],
            },
            {
                'id': 'conditions',
                'title': 'Condiciones generales',
                'paragraphs': [
                    'La solicitud debe hacerse desde tu cuenta, asociada al mismo pedido y usuario que realizó la compra.',
                    'El producto debe enviarse en condiciones que permitan verificar su estado; daños atribuibles '
                    'al mal uso posterior a la entrega pueden impedir el reembolso.',
                    'Artículos personalizados (bordados, grabados, tallajes especiales u otros hechos a medida) '
                    'solo aplican a devolución si hay error de fabricación o incumplimiento de lo ofertado.',
                ],
            },
            {
                'id': 'exclusions',
                'title': 'Exclusiones y casos especiales',
                'paragraphs': [
                    dig,
                    f'Categorías con slugs excluidos por la tienda: {ex_cat}.',
                    f'Prefijos de SKU tratados como especiales (no reembolsables o con flujo distinto): {sku_prev}.',
                    'Cupones o descuentos aplicados al pedido se revierten según las reglas del cupón y el valor '
                    'neto pagado.',
                ],
            },
            {
                'id': 'refunds',
                'title': 'Reembolsos',
                'paragraphs': [
                    'El reembolso, cuando proceda, se realizará preferentemente por el mismo medio de pago utilizado '
                    'en la compra, salvo imposibilidad técnica o normativa.',
                    'Los tiempos de acreditación dependen del banco o pasarela de pago; te notificaremos cuando '
                    'el reembolso quede tramitado.',
                ],
            },
            {
                'id': 'shipping_costs',
                'title': 'Costos de envío',
                'paragraphs': [
                    'Si la devolución es por arrepentimiento o preferencia, el costo del envío de vuelta puede '
                    'correr por cuenta del cliente, salvo que indiquemos lo contrario en la autorización.',
                    'Si el motivo es producto defectuoso, error nuestro o incumplimiento, asumiremos o reembolsaremos '
                    'el envío según el caso, conforme a lo acordado en la gestión.',
                ],
            },
        ],
        'closing_note': (
            'Franja Pixelada podrá rechazar solicitudes que incumplan estas políticas, presenten inconsistencias '
            'en la evidencia o excedan los plazos. Cualquier decisión se comunicará por los canales registrados en tu cuenta.'
        ),
    }
