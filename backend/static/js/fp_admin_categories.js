/* fp_admin_categories.js — Card grid para el changelist de Categorías
 * Lee el <table id="result_list"> de Django, construye tarjetas
 * interactivas y sincroniza los checkboxes con el form original.
 * Solo actúa cuando #result_list está presente (changelist page).
 *
 * Columnas (list_display en admin.py):
 *   td[0]=checkbox  td[1]=icon_preview  td[2]=name  td[3]=parent
 *   td[4]=product_count  td[5]=is_active  td[6]=order
 */
'use strict';

(function () {

  var COL = { icon: 1, name: 2, parent: 3, count: 4, active: 5, order: 6 };

  function esc(s) {
    return String(s || '')
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function cell(tds, idx) {
    return tds[idx] ? tds[idx].textContent.trim() : '';
  }

  function setSelected(card, on) {
    card.classList.toggle('fp-cc--selected', on);
  }

  /* ── Detecta si is_active es verdadero ─────────────────────────
     Django admin renderiza booleans como <img alt="True/False">
     o texto "Sí"/"No" según la configuración.               */
  function isActiveTd(td) {
    if (!td) return false;
    var img = td.querySelector('img');
    if (img) {
      var alt = (img.getAttribute('alt') || '').toLowerCase();
      return alt === 'true' || img.src.indexOf('icon-yes') !== -1;
    }
    var icon = td.querySelector('i[class*="check"], i[class*="yes"], .fas.fa-check-circle, .far.fa-check-circle');
    if (icon) return true;
    var text = td.textContent.trim().toLowerCase();
    return text === 'sí' || text === 'si' || text === 'yes' || text === 'true' || text === '1';
  }

  /* ════════════════════════════════════════════════════════════════
     MAIN
     ════════════════════════════════════════════════════════════════ */
  function buildGrid() {
    var table = document.getElementById('result_list');
    if (!table) return;

    var tbody = table.querySelector('tbody');
    if (!tbody) return;
    var rows = Array.from(tbody.querySelectorAll('tr'));
    if (!rows.length) return;

    var allOrigCbs = [];

    /* ── Contenedor raíz ──────────────────────────────────────── */
    var root = document.createElement('div');
    root.id = 'fp-cats-grid';

    /* ── Barra de selección ───────────────────────────────────── */
    var selBar = document.createElement('div');
    selBar.id = 'fp-cats-selbar';
    selBar.innerHTML =
      '<label class="fp-csb-label" id="fp-csb-label">' +
        '<span class="fp-csb-chkbox" id="fp-csb-chkbox"></span>' +
        '<span class="fp-csb-txt">Seleccionar todas</span>' +
      '</label>' +
      '<span class="fp-csb-count" id="fp-csb-count"></span>';
    root.appendChild(selBar);

    /* ── Grid de tarjetas ─────────────────────────────────────── */
    var grid = document.createElement('div');
    grid.id = 'fp-cats-cards';
    root.appendChild(grid);

    /* ── Construir cada tarjeta ───────────────────────────────── */
    rows.forEach(function (tr) {
      var tds = tr.querySelectorAll('td');
      if (tds.length < 5) return;

      /* Datos */
      var origCb  = tds[0] ? tds[0].querySelector('input[type="checkbox"]') : null;
      var aLink   = tds[COL.name] ? tds[COL.name].querySelector('a') : null;
      var href    = aLink ? aLink.href : '#';
      var name    = cell(tds, COL.name);
      var parent  = cell(tds, COL.parent);
      var count   = cell(tds, COL.count);
      var active  = isActiveTd(tds[COL.active]);
      var order   = cell(tds, COL.order);

      /* Imagen / icono */
      var iconTd   = tds[COL.icon];
      var imgEl    = iconTd ? iconTd.querySelector('img') : null;
      var imgSrc   = imgEl ? imgEl.src : null;
      var iconTag  = iconTd ? iconTd.querySelector('i') : null;
      var iconCls  = iconTag ? iconTag.className : null;

      /* Zona imagen */
      var mediaHtml;
      if (imgSrc && imgSrc.indexOf('/static/admin/img/') === -1) {
        mediaHtml = '<img src="' + imgSrc + '" class="fp-cc-img" alt="">';
      } else if (iconCls) {
        mediaHtml = '<div class="fp-cc-img-placeholder"><i class="' + esc(iconCls) + '" style="font-size:3rem;opacity:.75"></i></div>';
      } else {
        mediaHtml = '<div class="fp-cc-img-placeholder">📁</div>';
      }

      /* Estado y clases */
      var activeCls   = active ? 'fp-cc--activa'   : 'fp-cc--inactiva';
      var activeLabel = active ? '● Activa' : '○ Inactiva';

      /* Contar productos */
      var countNum = parseInt(count, 10) || 0;
      var countCls = countNum > 0 ? '' : ' fp-cc-count--zero';
      var countLabel = countNum === 1 ? '1 producto' : countNum + ' productos';

      /* ── HTML de la tarjeta ── */
      var card = document.createElement('div');
      card.className = 'fp-cat-card';
      card.setAttribute('role', 'button');
      card.setAttribute('tabindex', '0');
      card.setAttribute('aria-label', 'Editar categoría: ' + name);

      card.innerHTML =
        /* Imagen */
        '<div class="fp-cc-img-wrap">' +
          mediaHtml +
          '<div class="fp-cc-img-overlay"></div>' +
          '<span class="fp-cc-estado-badge ' + activeCls + '">' + activeLabel + '</span>' +
          (order && order !== '0' ? '<span class="fp-cc-order-badge">#' + esc(order) + '</span>' : '') +
          /* Checkbox flotante */
          '<label class="fp-cc-chk-wrap" onclick="event.stopPropagation()">' +
            '<input type="checkbox" class="fp-cc-cb">' +
            '<span class="fp-cc-chkbox"></span>' +
          '</label>' +
        '</div>' +

        /* Cuerpo */
        '<div class="fp-cc-body">' +
          '<div class="fp-cc-name">' + esc(name) + '</div>' +
          (parent && parent !== '—' && parent !== '-' && parent !== ''
            ? '<span class="fp-cc-parent">↳ ' + esc(parent) + '</span>'
            : '') +
        '</div>' +

        /* Pie */
        '<div class="fp-cc-foot">' +
          '<span class="fp-cc-count' + countCls + '">' + esc(countLabel) + '</span>' +
          '<span class="fp-cc-arrow">Editar →</span>' +
        '</div>';

      /* Navegación al hacer click en la tarjeta */
      card.addEventListener('click', function () { window.location.href = href; });
      card.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); window.location.href = href; }
      });

      /* Sincronizar checkbox */
      var cardCb = card.querySelector('.fp-cc-cb');
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

    /* ── Seleccionar todas ────────────────────────────────────── */
    var csbLabel  = document.getElementById('fp-csb-label');
    var csbChkBox = document.getElementById('fp-csb-chkbox');
    var csbCount  = document.getElementById('fp-csb-count');

    csbLabel.addEventListener('click', function () {
      var anyUnchecked = allOrigCbs.some(function (c) { return !c.checked; });
      allOrigCbs.forEach(function (c) {
        c.checked = anyUnchecked;
        c.dispatchEvent(new Event('change', { bubbles: true }));
      });
      grid.querySelectorAll('.fp-cat-card').forEach(function (card) {
        var cb = card.querySelector('.fp-cc-cb');
        if (cb) cb.checked = anyUnchecked;
        setSelected(card, anyUnchecked);
      });
      refreshSel();
    });

    /* Sincronizar con #action-toggle de Django (oculto en thead) */
    var djToggle = document.getElementById('action-toggle');
    if (djToggle) {
      djToggle.addEventListener('change', function () {
        var checked = djToggle.checked;
        allOrigCbs.forEach(function (c) {
          c.checked = checked;
          c.dispatchEvent(new Event('change', { bubbles: true }));
        });
        grid.querySelectorAll('.fp-cat-card').forEach(function (card) {
          var cb = card.querySelector('.fp-cc-cb');
          if (cb) cb.checked = checked;
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
      if (csbCount)  csbCount.textContent = n > 0 ? n + ' seleccionada' + (n !== 1 ? 's' : '') : '';
      if (csbChkBox) {
        csbChkBox.classList.toggle('fp-csb-chk--on',      all);
        csbChkBox.classList.toggle('fp-csb-chk--partial', some);
      }
    }

    /* Insertar grid y ocultar tabla original */
    table.parentNode.insertBefore(root, table);
    table.style.cssText = 'display:none!important';
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', buildGrid);
  } else {
    buildGrid();
  }

})();
