/* fp_admin_products.js — Card grid para el changelist de Productos
 * Lee el JSON de data-product (ya generado por details_btn en admin.py),
 * construye tarjetas dark-neon y sincroniza checkboxes con el form original.
 * Solo actúa cuando #result_list está presente. */
'use strict';

(function () {

  /* ── Formato de precio COP ───────────────────────────────────────── */
  function fmtPrice(val) {
    var n = parseFloat(val);
    if (!val || isNaN(n)) return null;
    return '$' + Math.round(n).toLocaleString('es-CO');
  }

  /* ── Porcentaje de descuento ─────────────────────────────────────── */
  function discount(price, compare) {
    var p = parseFloat(price), c = parseFloat(compare);
    if (!c || c <= p) return null;
    return Math.round((1 - p / c) * 100) + '%';
  }

  /* ── Badge de estado ─────────────────────────────────────────────── */
  var STATUS_MAP = {
    active:       { label: 'Activo',        cls: 'fp-pc-s--active' },
    inactive:     { label: 'Inactivo',      cls: 'fp-pc-s--inactive' },
    out_of_stock: { label: 'Agotado',       cls: 'fp-pc-s--empty' },
    coming_soon:  { label: 'Próximamente',  cls: 'fp-pc-s--soon' },
  };

  /* ── Nivel de stock ──────────────────────────────────────────────── */
  function stockCls(n) {
    if (n === 0)  return 'fp-pc-stk--zero';
    if (n <= 5)   return 'fp-pc-stk--low';
    return 'fp-pc-stk--ok';
  }
  function stockLabel(n) {
    if (n === 0) return '⚠ Sin stock';
    if (n <= 5)  return '⚡ ' + n + ' (bajo)';
    return n + ' uds.';
  }

  /* ── Escape HTML ─────────────────────────────────────────────────── */
  function esc(s) {
    return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  /* ── Card seleccionada ───────────────────────────────────────────── */
  function setSelected(card, on) { card.classList.toggle('fp-pc--selected', on); }

  /* ════════════════════════════════════════════════════════════════════
     MAIN
     ════════════════════════════════════════════════════════════════════ */
  function buildGrid() {
    var table = document.getElementById('result_list');
    if (!table) return;
    var tbody = table.querySelector('tbody');
    if (!tbody) return;
    var rows = Array.from(tbody.querySelectorAll('tr'));
    if (!rows.length) return;

    var allOrigCbs = [];

    /* ── Contenedor raíz ─────────────────────────────────────────── */
    var root = document.createElement('div');
    root.id = 'fp-products-grid-root';

    /* ── Barra de selección ──────────────────────────────────────── */
    var selBar = document.createElement('div');
    selBar.id = 'fp-prod-selbar';
    selBar.innerHTML =
      '<label class="fp-psb-label" id="fp-psb-label">' +
        '<span class="fp-psb-chk" id="fp-psb-chk"></span>' +
        '<span class="fp-psb-txt">Seleccionar todos</span>' +
      '</label>' +
      '<span class="fp-psb-count" id="fp-psb-count"></span>';
    root.appendChild(selBar);

    /* ── Grid ────────────────────────────────────────────────────── */
    var grid = document.createElement('div');
    grid.id = 'fp-products-cards';
    root.appendChild(grid);

    /* ── Construir cada tarjeta ──────────────────────────────────── */
    rows.forEach(function (tr) {
      var tds     = tr.querySelectorAll('td');
      var origCb  = tds[0] ? tds[0].querySelector('input[type="checkbox"]') : null;
      var detBtn  = tr.querySelector('.fp-detail-btn');
      if (!detBtn) return;

      var data;
      try { data = JSON.parse(detBtn.dataset.product || '{}'); } catch (e) { return; }

      var status   = STATUS_MAP[data.status] || { label: data.status, cls: '' };
      var imgUrl   = data.images && data.images[0] ? data.images[0].url : null;
      var price    = fmtPrice(data.price);
      var compare  = fmtPrice(data.compare_at_price);
      var pct      = discount(data.price, data.compare_at_price);
      var stk      = parseInt(data.stock, 10) || 0;
      var editUrl  = data.edit_url || '#';

      var card = document.createElement('div');
      card.className = 'fp-prod-card';
      card.setAttribute('role', 'button');
      card.setAttribute('tabindex', '0');
      card.setAttribute('aria-label', 'Editar ' + data.name);
      if (data.is_featured) card.setAttribute('data-featured', 'true');

      card.innerHTML =
        /* ── Imagen ── */
        '<div class="fp-pc-img-wrap">' +
          (imgUrl
            ? '<img class="fp-pc-img" src="' + esc(imgUrl) + '" alt="" loading="lazy">'
            : '<div class="fp-pc-img-placeholder">📦</div>') +
          /* Badges sobre imagen */
          '<div class="fp-pc-img-badges">' +
            (pct ? '<span class="fp-pc-discount">-' + esc(pct) + '</span>' : '') +
            (data.is_featured ? '<span class="fp-pc-feat">⭐</span>' : '') +
            (data.is_new ? '<span class="fp-pc-new">Nuevo</span>' : '') +
          '</div>' +
          /* Checkbox flotante */
          '<label class="fp-pc-chk-wrap" onclick="event.stopPropagation()">' +
            '<input type="checkbox" class="fp-pc-cb">' +
            '<span class="fp-pc-chkbox"></span>' +
          '</label>' +
        '</div>' +

        /* ── Cuerpo ── */
        '<div class="fp-pc-body">' +
          /* Estado + Categoría */
          '<div class="fp-pc-meta">' +
            '<span class="fp-pc-status ' + status.cls + '">' + esc(status.label) + '</span>' +
            (data.category ? '<span class="fp-pc-cat">' + esc(data.category) + '</span>' : '') +
          '</div>' +
          /* Nombre */
          '<div class="fp-pc-name">' + esc(data.name) + '</div>' +
          /* SKU */
          (data.sku ? '<div class="fp-pc-sku">SKU: ' + esc(data.sku) + '</div>' : '') +
        '</div>' +

        /* ── Pie ── */
        '<div class="fp-pc-foot">' +
          '<div class="fp-pc-price-block">' +
            (price ? '<span class="fp-pc-price">' + price + '</span>' : '') +
            (compare ? '<span class="fp-pc-compare">' + compare + '</span>' : '') +
          '</div>' +
          '<div class="fp-pc-right">' +
            '<span class="fp-pc-stock ' + stockCls(stk) + '">' + stockLabel(stk) + '</span>' +
          '</div>' +
        '</div>';

      /* Navegación */
      card.addEventListener('click', function () { window.location.href = editUrl; });
      card.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); window.location.href = editUrl; }
      });

      /* Checkbox */
      var cardCb = card.querySelector('.fp-pc-cb');
      if (origCb) {
        allOrigCbs.push(origCb);
        cardCb.checked = origCb.checked;
        setSelected(card, cardCb.checked);

        cardCb.addEventListener('change', function (e) {
          e.stopPropagation();
          origCb.checked = cardCb.checked;
          origCb.dispatchEvent(new Event('change', { bubbles: true }));
          setSelected(card, cardCb.checked);
          refreshSel();
        });
        origCb.addEventListener('change', function () {
          cardCb.checked = origCb.checked;
          setSelected(card, origCb.checked);
          refreshSel();
        });
      }

      grid.appendChild(card);
    });

    /* ── Seleccionar todos ───────────────────────────────────────── */
    var psbLabel = document.getElementById('fp-psb-label');
    var psbChk   = document.getElementById('fp-psb-chk');
    var psbCount = document.getElementById('fp-psb-count');

    psbLabel.addEventListener('click', function () {
      var anyUnchecked = allOrigCbs.some(function (c) { return !c.checked; });
      allOrigCbs.forEach(function (c) {
        c.checked = anyUnchecked;
        c.dispatchEvent(new Event('change', { bubbles: true }));
      });
      grid.querySelectorAll('.fp-prod-card').forEach(function (card) {
        var cb = card.querySelector('.fp-pc-cb'); if (cb) cb.checked = anyUnchecked;
        setSelected(card, anyUnchecked);
      });
      refreshSel();
    });

    var djToggle = document.getElementById('action-toggle');
    if (djToggle) {
      djToggle.addEventListener('change', function () {
        var checked = djToggle.checked;
        allOrigCbs.forEach(function (c) { c.checked = checked; c.dispatchEvent(new Event('change', {bubbles:true})); });
        grid.querySelectorAll('.fp-prod-card').forEach(function (card) {
          var cb = card.querySelector('.fp-pc-cb'); if (cb) cb.checked = checked;
          setSelected(card, checked);
        });
        refreshSel();
      });
    }

    function refreshSel() {
      var n     = allOrigCbs.filter(function (c) { return c.checked; }).length;
      var total = allOrigCbs.length;
      var all   = total > 0 && n === total;
      var some  = n > 0 && n < total;
      if (psbCount) psbCount.textContent = n > 0 ? n + ' seleccionado' + (n !== 1 ? 's' : '') : '';
      if (psbChk) {
        psbChk.classList.toggle('fp-psb-chk--on', all);
        psbChk.classList.toggle('fp-psb-chk--partial', some);
      }
    }

    /* Ocultar tabla original e insertar grid */
    table.parentNode.insertBefore(root, table);
    table.style.cssText = 'display:none!important';
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', buildGrid);
  } else {
    buildGrid();
  }

})();
