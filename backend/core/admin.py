from django.contrib import admin
from django.utils.html import format_html
from .models import LoginAttempt, AdminAuditLog, ExchangeRate
from .admin_site import admin_site


@admin.register(LoginAttempt, site=admin_site)
class LoginAttemptAdmin(admin.ModelAdmin):
    list_display = ('username', 'ip_address', 'resultado', 'agente_corto', 'timestamp')
    list_filter = ('was_successful',)
    search_fields = ('username', 'ip_address')
    readonly_fields = ('id', 'username', 'ip_address', 'was_successful', 'user_agent', 'timestamp')
    ordering = ('-timestamp',)
    date_hierarchy = 'timestamp'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def resultado(self, obj):
        if obj.was_successful:
            return '✅ Exitoso'
        return '❌ Fallido'
    resultado.short_description = 'Resultado'

    def agente_corto(self, obj):
        try:
            ua = obj.user_agent or ''
            return ua[:60] + '…' if len(ua) > 60 else ua or '—'
        except Exception:
            return '—'
    agente_corto.short_description = 'Navegador / Agente'


@admin.register(AdminAuditLog, site=admin_site)
class AdminAuditLogAdmin(admin.ModelAdmin):
    list_display = ('admin_username', 'accion', 'model_name', 'object_repr', 'ip_address', 'timestamp')
    list_filter = ('action', 'model_name')
    search_fields = ('admin_username', 'object_repr', 'ip_address')
    readonly_fields = (
        'id', 'admin', 'admin_username', 'action', 'model_name',
        'object_id', 'object_repr', 'changes', 'ip_address', 'timestamp'
    )
    ordering = ('-timestamp',)
    date_hierarchy = 'timestamp'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def accion(self, obj):
        icons = {'create': '➕ Crear', 'update': '✏️ Editar', 'delete': '🗑️ Eliminar'}
        return icons.get(obj.action, obj.action)
    accion.short_description = 'Acción'


# ── Tasa de Cambio USD → COP ─────────────────────────────────────────────────

@admin.register(ExchangeRate, site=admin_site)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display = ('rate_display', 'rate_date', 'notes', 'created_by', 'created_at')
    readonly_fields = ('id', 'created_by', 'created_at', 'conversor_widget')
    ordering = ('-rate_date', '-created_at')
    date_hierarchy = 'rate_date'

    fieldsets = (
        ('Tasa de cambio', {
            'fields': ('rate', 'rate_date', 'notes'),
            'description': 'Define 1 USD = X COP. Esta tasa se usa para convertir precios de proveedores.',
        }),
        ('Conversor rápido', {
            'fields': ('conversor_widget',),
        }),
        ('Registro', {
            'fields': ('id', 'created_by', 'created_at'),
            'classes': ('collapse',),
        }),
    )

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def rate_display(self, obj):
        rate_str = f'{float(obj.rate):,.2f}' if obj.rate else '—'
        return format_html(
            '<strong style="color:#c9a227">1 USD = {} COP</strong>',
            rate_str
        )
    rate_display.short_description = 'Tasa'

    def conversor_widget(self, obj):
        rate = float(obj.rate) if obj.rate is not None else 0
        rate_str = f'{rate:,.2f}'
        return format_html('''
        <div style="background:#1e2a1e;border:1px solid #4a7c3f;border-radius:8px;
                    padding:1.5rem;max-width:520px;font-family:monospace">

          <!-- Fila: tasa actual + botón obtener online -->
          <div style="display:flex;align-items:center;gap:1rem;margin-bottom:1rem;flex-wrap:wrap">
            <div style="color:#c9a227;font-weight:bold;font-size:0.9rem">
              // CONVERSOR USD → COP &nbsp;·&nbsp; Tasa guardada: <span id="conv-tasa-display">{}</span>
            </div>
            <button type="button" id="btn-obtener-tasa"
              style="background:#1a3a5c;color:#7ec8e3;border:1px solid #2a5a8c;
                     padding:0.35rem 0.9rem;border-radius:4px;cursor:pointer;
                     font-size:0.78rem;font-weight:bold"
              onclick="(function(){{
                var btn = document.getElementById('btn-obtener-tasa');
                btn.textContent = 'Consultando...'; btn.disabled = true;
                fetch('/api/v1/core/exchange-rate/live/')
                  .then(function(r){{ return r.json(); }})
                  .then(function(d){{
                    if (d.error) {{ alert('Error: ' + d.error); btn.textContent = '↻ Obtener tasa online'; btn.disabled=false; return; }}
                    var r = d.rate;
                    document.getElementById('conv-tasa-display').textContent = r.toLocaleString('es-CO', {{minimumFractionDigits:2}});
                    document.getElementById('id_rate').value = r.toFixed(2);
                    var hoy = new Date();
                    var y=hoy.getFullYear(), m=String(hoy.getMonth()+1).padStart(2,'0'), dia=String(hoy.getDate()).padStart(2,'0');
                    var dateField = document.getElementById('id_rate_date');
                    if (dateField) dateField.value = y+'-'+m+'-'+dia;
                    document.getElementById('conv-live-info').textContent =
                      '✔ Tasa obtenida: 1 USD = ' + r.toLocaleString('es-CO',{{minimumFractionDigits:2}}) +
                      ' COP  (' + (d.time_last_update || '') + ')';
                    btn.textContent = '↻ Obtener tasa online'; btn.disabled=false;
                  }})
                  .catch(function(e){{ alert('Sin conexión: ' + e); btn.textContent='↻ Obtener tasa online'; btn.disabled=false; }});
              }})()">
              ↻ Obtener tasa online
            </button>
          </div>

          <div id="conv-live-info"
               style="color:#4fc870;font-size:0.78rem;margin-bottom:0.75rem;min-height:1rem"></div>

          <!-- Conversor manual -->
          <div style="display:grid;gap:0.75rem">
            <label style="color:#aaa;font-size:0.8rem">Convertir monto en USD</label>
            <input id="conv-usd" type="number" min="0" step="0.01" placeholder="Ej: 25.00"
                   style="background:#0d1a0d;border:1px solid #4a7c3f;color:#fff;
                          padding:0.6rem 0.8rem;border-radius:4px;font-size:1rem;width:100%">
            <button type="button" onclick="(function(){{
                var usd = parseFloat(document.getElementById('conv-usd').value) || 0;
                var tasa = parseFloat(document.getElementById('id_rate').value) || {};
                if (usd <= 0) {{ document.getElementById('conv-result').textContent = '— ingresa un valor mayor a 0'; return; }}
                var cop = usd * tasa;
                var redondeado = Math.round(cop / 100) * 100;
                document.getElementById('conv-result').innerHTML =
                  usd.toLocaleString('es-CO') + ' USD &times; ' +
                  tasa.toLocaleString('es-CO',{{minimumFractionDigits:2}}) + ' = <strong style=color:#4fc870>' +
                  redondeado.toLocaleString('es-CO',{{minimumFractionDigits:0}}) + ' COP</strong>';
            }})();"
            style="background:#4a7c3f;color:#fff;border:none;padding:0.6rem 1.2rem;
                   border-radius:4px;cursor:pointer;font-weight:bold;font-size:0.9rem;width:fit-content">
              Convertir
            </button>
            <div id="conv-result"
                 style="color:#aaa;font-size:0.95rem;padding:0.5rem 0;min-height:1.5rem">
            </div>
          </div>
        </div>
        ''', rate_str, rate)
    conversor_widget.short_description = 'Conversor rápido'
