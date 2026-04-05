/* fp_admin_users.js — Card grid para el changelist de Usuarios
 * Lee el <table id="result_list"> de Django, construye tarjetas
 * interactivas y sincroniza los checkboxes con el form original.
 * Solo actúa cuando #result_list está presente (changelist page). */
'use strict';

(function () {

  /* ── Índices de columna (deben coincidir con list_display en admin.py) ─
     td[0]=checkbox  td[1]=email  td[2]=nombre  td[3]=apellido
     td[4]=phone     td[5]=rol    td[6]=estado  td[7]=created_at        */
  var COL = { email:1, nombre:2, apellido:3, phone:4, rol:5, estado:6, fecha:7 };

  /* ── Escape HTML básico para datos del DOM ─────────────────────────── */
  function esc(s) {
    return String(s || '')
      .replace(/&/g,'&amp;').replace(/</g,'&lt;')
      .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  /* ── Texto de una celda ─────────────────────────────────────────────── */
  function cell(tds, idx) {
    return tds[idx] ? tds[idx].textContent.trim() : '';
  }

  /* ── Acortar fecha larga ("X de Mes de YYYY a las HH:MM" → "X de Mes YYYY") */
  function shortDate(s) {
    var m = s.match(/(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})/i);
    return m ? m[1] + ' ' + m[2] + ' ' + m[3] : s;
  }

  /* ── Tarjeta selected ───────────────────────────────────────────────── */
  function setSelected(card, on) {
    card.classList.toggle('fp-uc--selected', on);
  }

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

    /* ── Contenedor raíz ──────────────────────────────────────────── */
    var root = document.createElement('div');
    root.id = 'fp-users-grid';

    /* ── Barra de selección ───────────────────────────────────────── */
    var selBar = document.createElement('div');
    selBar.id = 'fp-users-selbar';
    selBar.innerHTML =
      '<label class="fp-usb-label" id="fp-usb-label">' +
        '<span class="fp-usb-chkbox" id="fp-usb-chkbox"></span>' +
        '<span class="fp-usb-txt">Seleccionar todos</span>' +
      '</label>' +
      '<span class="fp-usb-count" id="fp-usb-count"></span>';
    root.appendChild(selBar);

    /* ── Grid de tarjetas ─────────────────────────────────────────── */
    var grid = document.createElement('div');
    grid.id = 'fp-users-cards';
    root.appendChild(grid);

    /* ── Construir cada tarjeta ───────────────────────────────────── */
    rows.forEach(function (tr) {
      var tds = tr.querySelectorAll('td');
      if (tds.length < 6) return;

      /* Datos */
      var origCb   = tds[0] ? tds[0].querySelector('input[type="checkbox"]') : null;
      var aLink    = tds[COL.email] ? tds[COL.email].querySelector('a') : null;
      var href     = aLink ? aLink.href : '#';
      var email    = cell(tds, COL.email);
      var nombre   = cell(tds, COL.nombre);
      var apellido = cell(tds, COL.apellido);
      var phone    = cell(tds, COL.phone);
      var rol      = cell(tds, COL.rol);
      var estado   = cell(tds, COL.estado);
      var fecha    = shortDate(cell(tds, COL.fecha));

      /* Rol */
      var isSuper  = rol.indexOf('Superadmin') !== -1;
      var isStaff  = !isSuper && rol.indexOf('Staff') !== -1;
      var rolCls   = isSuper ? 'fp-uc--super' : isStaff ? 'fp-uc--staff' : 'fp-uc--cliente';
      var rolClean = rol.replace(/^[^\w\s\u00C0-\u024F]*\s*/, '').trim();
      var rolEmoji = isSuper ? '🛡️' : isStaff ? '🔧' : '👤';

      /* Avatar */
      var initials = ((nombre[0]||'') + (apellido[0]||'')).toUpperCase()
                     || email.substring(0,2).toUpperCase();

      /* Estado */
      var activo = estado.toLowerCase().indexOf('activo') !== -1;

      /* HTML de la tarjeta */
      var card = document.createElement('div');
      card.className = 'fp-user-card ' + rolCls;
      card.setAttribute('role', 'button');
      card.setAttribute('tabindex', '0');
      card.setAttribute('aria-label', 'Editar ' + email);

      card.innerHTML =
        /* ── Cabecera ── */
        '<div class="fp-uc-head">' +
          '<label class="fp-uc-chk-wrap" onclick="event.stopPropagation()">' +
            '<input type="checkbox" class="fp-uc-cb">' +
            '<span class="fp-uc-chkbox"></span>' +
          '</label>' +
          '<span class="fp-uc-spacer"></span>' +
          '<span class="fp-uc-estado ' + (activo ? 'fp-uc--activo' : 'fp-uc--inactivo') + '">' +
            (activo ? '● Activo' : '○ Inactivo') +
          '</span>' +
        '</div>' +

        /* ── Cuerpo ── */
        '<div class="fp-uc-body">' +
          '<div class="fp-uc-avatar">' + esc(initials) + '</div>' +
          '<div class="fp-uc-info">' +
            '<div class="fp-uc-email">' + esc(email) + '</div>' +
            '<div class="fp-uc-name">' + esc((nombre + ' ' + apellido).trim() || '—') + '</div>' +
            '<div class="fp-uc-meta">' +
              (phone ? '<span>📱 ' + esc(phone) + '</span>' : '') +
              (fecha  ? '<span>📅 ' + esc(fecha)  + '</span>' : '') +
            '</div>' +
          '</div>' +
        '</div>' +

        /* ── Pie ── */
        '<div class="fp-uc-foot">' +
          '<span class="fp-uc-rol">' + rolEmoji + ' ' + esc(rolClean) + '</span>' +
          '<span class="fp-uc-arrow">Editar →</span>' +
        '</div>';

      /* Navegación */
      card.addEventListener('click', function () { window.location.href = href; });
      card.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); window.location.href = href; }
      });

      /* Sincronizar checkbox */
      var cardCb = card.querySelector('.fp-uc-cb');
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

    /* ── Seleccionar todos ────────────────────────────────────────── */
    var usbLabel = document.getElementById('fp-usb-label');
    var usbChkBox = document.getElementById('fp-usb-chkbox');
    var usbCount  = document.getElementById('fp-usb-count');

    usbLabel.addEventListener('click', function () {
      var anyUnchecked = allOrigCbs.some(function (c) { return !c.checked; });
      allOrigCbs.forEach(function (c) {
        c.checked = anyUnchecked;
        c.dispatchEvent(new Event('change', { bubbles: true }));
      });
      grid.querySelectorAll('.fp-user-card').forEach(function (card) {
        var cb = card.querySelector('.fp-uc-cb');
        if (cb) cb.checked = anyUnchecked;
        setSelected(card, anyUnchecked);
      });
      refreshSel();
    });

    /* Sincronizar con el #action-toggle de Django (oculto en thead) */
    var djToggle = document.getElementById('action-toggle');
    if (djToggle) {
      djToggle.addEventListener('change', function () {
        var checked = djToggle.checked;
        allOrigCbs.forEach(function (c) { c.checked = checked; c.dispatchEvent(new Event('change', {bubbles:true})); });
        grid.querySelectorAll('.fp-user-card').forEach(function (card) {
          var cb = card.querySelector('.fp-uc-cb'); if (cb) cb.checked = checked;
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
      if (usbCount)  usbCount.textContent = n > 0 ? n + ' seleccionado' + (n !== 1 ? 's' : '') : '';
      if (usbChkBox) {
        usbChkBox.classList.toggle('fp-usb-chk--on', all);
        usbChkBox.classList.toggle('fp-usb-chk--partial', some);
      }
    }

    /* Insertar grid y ocultar tabla */
    table.parentNode.insertBefore(root, table);
    table.style.cssText = 'display:none!important';
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', buildGrid);
  } else {
    buildGrid();
  }

})();
