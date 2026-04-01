"""Filtros de presentación para el admin (etiquetas de acciones masivas)."""
import re

from django import template

register = template.Library()

_LABEL_MAP = {
    'action_importar_variantes': 'Importar variantes',
    'action_importar_a_tienda': 'Importar a mi tienda',
    'action_sincronizar_catalogo': 'Sincronizar catálogo',
    'recalcular_stock_seleccionados': 'Recalcular stock',
}


@register.filter
def fp_action_button_label(action_value, verbose_label):
    """Texto corto para botones de acción masiva (paridad con franja_admin_global.js)."""
    key = str(action_value) if action_value is not None else ''
    if key in _LABEL_MAP:
        return _LABEL_MAP[key]
    s = str(verbose_label)
    s = re.sub(r'\s+\([^)]*\)', '', s)
    s = re.sub(r'\s*[—–]\s*.*', '', s)
    s = re.sub(r'\s+ahora\b', '', s, flags=re.I)
    s = re.sub(r'\s+seleccionado[s/]?[as]*', '', s, flags=re.I)
    s = re.sub(r'\s+selected.*', '', s, flags=re.I)
    return s.strip()


@register.filter
def fp_action_is_danger(action_value):
    v = str(action_value).lower()
    return 'delete' in v or 'elimin' in v
