"""
Franja Pixelada — Widgets personalizados para el admin de usuarios
"""
from django import forms
from django.utils.safestring import mark_safe


# (num, abrev, nombre completo)
MONTHS_ES = [
    (1, 'Ene', 'Enero'),    (2, 'Feb', 'Febrero'),  (3, 'Mar', 'Marzo'),
    (4, 'Abr', 'Abril'),    (5, 'May', 'Mayo'),      (6, 'Jun', 'Junio'),
    (7, 'Jul', 'Julio'),    (8, 'Ago', 'Agosto'),    (9, 'Sep', 'Septiembre'),
    (10, 'Oct', 'Octubre'), (11, 'Nov', 'Noviembre'), (12, 'Dic', 'Diciembre'),
]


class SplitDateWidget(forms.Widget):
    """
    Reemplaza el DatePicker nativo por un picker de chips horizontales:
      • Día   → fila scrollable de chips 01–31
      • Mes   → fila scrollable de chips Ene–Dic
      • Año   → input numérico editable (1900 – año actual)

    El JS en admin_split_date.js maneja la apertura/cierre de paneles.
    Los valores viajan como hidden inputs {name}_day y {name}_month,
    más el input visible {name}_year.
    """

    def _parse_value(self, value):
        """Devuelve (day, month, year) como enteros, o (None, None, None)."""
        if not value:
            return None, None, None
        if hasattr(value, 'day'):
            return value.day, value.month, value.year
        if isinstance(value, str) and len(value) == 10 and value[4] == '-':
            try:
                y, m, d = value.split('-')
                return int(d), int(m), int(y)
            except (ValueError, AttributeError):
                pass
        return None, None, None

    def render(self, name, value, attrs=None, renderer=None):
        sel_day, sel_month, sel_year = self._parse_value(value)

        # ID-safe prefix (sin guiones)
        cid = name.replace('-', '_').replace('.', '_')

        day_lbl   = f'{sel_day:02d}' if sel_day else 'Día'
        month_lbl = next((s for n, s, _ in MONTHS_ES if n == sel_month), 'Mes')
        year_val  = str(sel_year) if sel_year else ''

        # ── Chips de Día ──────────────────────────────────────────────────
        day_chips = ''
        for d in range(1, 32):
            cls = 'fp-sd-chip fp-sd-chip--sel' if d == sel_day else 'fp-sd-chip'
            day_chips += (
                f'<button type="button" class="{cls}"'
                f' data-part="day" data-value="{d}" data-label="{d:02d}">'
                f'{d:02d}</button>'
            )

        # ── Chips de Mes ──────────────────────────────────────────────────
        month_chips = ''
        for num, short, _ in MONTHS_ES:
            cls = 'fp-sd-chip fp-sd-chip--sel' if num == sel_month else 'fp-sd-chip'
            month_chips += (
                f'<button type="button" class="{cls}"'
                f' data-part="month" data-value="{num}" data-label="{short}">'
                f'{short}</button>'
            )

        html = (
            f'<div class="fp-split-date" data-field="{cid}">'

            # ── Trigger: Día ──
            f'<button type="button" class="fp-sd-trigger" data-part="day"'
            f' aria-haspopup="listbox" aria-expanded="false">'
            f'<span class="fp-sd-label" id="fp-sd-{cid}-day-lbl">{day_lbl}</span>'
            f'<span class="fp-sd-caret" aria-hidden="true">▾</span>'
            f'</button>'

            f'<span class="fp-sd-divider" aria-hidden="true"></span>'

            # ── Trigger: Mes ──
            f'<button type="button" class="fp-sd-trigger" data-part="month"'
            f' aria-haspopup="listbox" aria-expanded="false">'
            f'<span class="fp-sd-label" id="fp-sd-{cid}-month-lbl">{month_lbl}</span>'
            f'<span class="fp-sd-caret" aria-hidden="true">▾</span>'
            f'</button>'

            f'<span class="fp-sd-divider" aria-hidden="true"></span>'

            # ── Input: Año ──
            f'<input type="number" name="{name}_year" class="fp-sd-year"'
            f' placeholder="Año" min="1900" max="2099" value="{year_val}"'
            f' aria-label="Año">'

            # ── Inputs ocultos (valores reales) ──
            f'<input type="hidden" name="{name}_day"'
            f' id="fp-sd-{cid}-day-val" value="{sel_day or ""}">'
            f'<input type="hidden" name="{name}_month"'
            f' id="fp-sd-{cid}-month-val" value="{sel_month or ""}">'

            # ── Panel: Día ──
            f'<div class="fp-sd-panel fp-sd-panel--day" id="fp-sd-{cid}-day-panel"'
            f' role="listbox" aria-label="Día" hidden>'
            f'<div class="fp-sd-chips">{day_chips}</div>'
            f'</div>'

            # ── Panel: Mes ──
            f'<div class="fp-sd-panel fp-sd-panel--month" id="fp-sd-{cid}-month-panel"'
            f' role="listbox" aria-label="Mes" hidden>'
            f'<div class="fp-sd-chips">{month_chips}</div>'
            f'</div>'

            f'</div>'
        )
        return mark_safe(html)

    def value_from_datadict(self, data, files, name):
        day   = data.get(f'{name}_day', '').strip()
        month = data.get(f'{name}_month', '').strip()
        year  = data.get(f'{name}_year', '').strip()

        # Campo completamente vacío → válido para campos opcionales
        if not day and not month and not year:
            return ''

        # Los tres presentes → combinar
        if day and month and year:
            try:
                return f'{int(year):04d}-{int(month):02d}-{int(day):02d}'
            except (ValueError, TypeError):
                return ''

        # Selección incompleta → vacío
        return ''

    @property
    def media(self):
        return forms.Media(js=['js/admin_split_date.js'])
