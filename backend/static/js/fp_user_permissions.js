/* fp_user_permissions.js — UI innovadora de permisos de usuario
 * Los <select> originales se conservan ocultos para la serialización
 * del formulario Django. SelectFilter2.js de Django crea id_groups_from/to
 * en window.load, por eso iniciamos en ese evento con retry. */
'use strict';

(function () {

  /* ── Metadatos ──────────────────────────────────────────────── */
  var GROUP_META = {
    superadministrador:  { icon: '🛡️', desc: 'Control total del sistema. Todos los permisos sin restricción.', danger: true },
    administradortienda: { icon: '🏪', desc: 'Gestión de productos, categorías, órdenes y cupones.' },
    gestorinventario:    { icon: '📦', desc: 'Control de stock, variantes e inventario del catálogo.' },
  };
  var BOOL_META = {
    is_active:          { icon: '✅', title: 'Usuario activo',        desc: 'El usuario puede iniciar sesión y usar la tienda.',                                cls: '' },
    is_staff:           { icon: '🔧', title: 'Acceso al panel',       desc: 'Permite entrar al panel de administración con permisos asignados.',                cls: 'fp-staff' },
    is_superuser:       { icon: '🛡️', title: 'Superusuario',          desc: 'Todos los permisos sin restricciones. Solo para cuentas de máxima confianza.',    cls: 'fp-super' },
    two_factor_enabled: { icon: '🔐', title: '2FA activo',            desc: 'Verificación en dos pasos vía SMS. Recomendado para cuentas con acceso al panel.', cls: 'fp-security' },
    accepts_marketing:  { icon: '📣', title: 'Acepta comunicaciones', desc: 'El usuario acepta recibir correos y notificaciones de marketing.',                 cls: 'fp-marketing' },
  };

  /* ── Utilidades de selección (sincronizan el <select> original) ── */
  function moveToChosen(fromSel, toSel, value) {
    var opt = fromSel.querySelector('option[value="' + value + '"]');
    if (opt) { opt.selected = true; toSel.appendChild(opt); }
  }
  function moveToAvail(fromSel, toSel, value) {
    var opt = toSel.querySelector('option[value="' + value + '"]');
    if (opt) { opt.selected = false; fromSel.appendChild(opt); }
  }

  /* ── Espera con retry hasta que aparezca un elemento ─────────── */
  function whenReady(id, cb, limit) {
    limit = limit || 3000;
    var started = Date.now();
    (function poll() {
      var el = document.getElementById(id);
      if (el) { cb(el); return; }
      if (Date.now() - started < limit) setTimeout(poll, 80);
    })();
  }

  /* ══════════════════════════════════════════════════════════════
     TOGGLE CARDS — is_active / is_staff / is_superuser
     ══════════════════════════════════════════════════════════════ */
  function initBoolCards() {
    Object.keys(BOOL_META).forEach(function (field) {
      var row = document.querySelector('.field-' + field);
      if (!row) return;
      var cb = row.querySelector('input[type="checkbox"]');
      if (!cb) return;
      var meta = BOOL_META[field];
      var on   = cb.checked;

      var card = document.createElement('div');
      card.className = 'fp-bool-card' + (meta.cls ? ' ' + meta.cls : '') + (on ? ' fp-on' : '');
      card.innerHTML =
        '<span class="fp-bool-ico">' + meta.icon + '</span>' +
        '<div class="fp-bool-body">' +
          '<div class="fp-bool-title">' + meta.title + '</div>' +
          '<div class="fp-bool-desc">' + meta.desc + '</div>' +
          '<span class="fp-bool-badge">' + (on ? 'Habilitado' : 'Deshabilitado') + '</span>' +
        '</div>' +
        '<div class="fp-bool-switch">' +
          '<span class="fp-sw-track"><span class="fp-sw-thumb"></span></span>' +
          '<span class="fp-sw-lbl">' + (on ? 'ON' : 'OFF') + '</span>' +
        '</div>';

      card.addEventListener('click', function () {
        var active = card.classList.contains('fp-on');
        active ? card.classList.remove('fp-on') : card.classList.add('fp-on');
        active = !active;
        cb.checked = active;
        card.querySelector('.fp-bool-badge').textContent = active ? 'Habilitado' : 'Deshabilitado';
        card.querySelector('.fp-sw-lbl').textContent = active ? 'ON' : 'OFF';
      });

      row.style.cssText = 'display:none!important';
      row.insertAdjacentElement('afterend', card);
    });
  }

  /* ══════════════════════════════════════════════════════════════
     GROUP CARDS
     ══════════════════════════════════════════════════════════════ */
  function buildGroupCards() {
    var fromSel = document.getElementById('id_groups_from');
    var toSel   = document.getElementById('id_groups_to');
    if (!fromSel || !toSel) return false;

    /* Recopilar todas las opciones */
    var chosen = new Set(Array.from(toSel.options).map(function (o) { return o.value; }));
    var all = [];
    Array.from(toSel.options).forEach(function (o) { all.push({ v: o.value, t: o.text, on: true }); });
    Array.from(fromSel.options).forEach(function (o) { all.push({ v: o.value, t: o.text, on: false }); });
    all.sort(function (a, b) { return a.t.localeCompare(b.t); });

    /* Construir UI */
    var wrap = document.createElement('div');
    wrap.className = 'fp-groups-ui';

    var lbl = document.createElement('div');
    lbl.className = 'fp-groups-label';
    lbl.textContent = 'Grupos del usuario';
    wrap.appendChild(lbl);

    var grid = document.createElement('div');
    grid.className = 'fp-groups-grid';

    all.forEach(function (opt) {
      var key  = opt.t.toLowerCase().replace(/[\s_\-]+/g, '');
      var meta = null;
      Object.keys(GROUP_META).forEach(function (k) { if (key.indexOf(k) !== -1) meta = GROUP_META[k]; });
      if (!meta) meta = { icon: '👥', desc: 'Grupo de permisos de usuario.' };

      var card = document.createElement('div');
      card.className = 'fp-group-card' + (meta.danger ? ' fp-group-super' : '') + (opt.on ? ' fp-group-on' : '');
      card.dataset.val = opt.v;
      card.innerHTML =
        '<span class="fp-group-ico">' + meta.icon + '</span>' +
        '<div class="fp-group-info">' +
          '<span class="fp-group-name">' + opt.t + '</span>' +
          '<span class="fp-group-desc">' + meta.desc + '</span>' +
        '</div>' +
        '<div class="fp-group-tog">' +
          '<span class="fp-gt-track"><span class="fp-gt-thumb"></span></span>' +
          '<span class="fp-gt-lbl">' + (opt.on ? 'Activo' : 'Inactivo') + '</span>' +
        '</div>';

      card.addEventListener('click', function () {
        var active = card.classList.contains('fp-group-on');
        if (active) {
          card.classList.remove('fp-group-on');
          card.querySelector('.fp-gt-lbl').textContent = 'Inactivo';
          moveToAvail(fromSel, toSel, opt.v);
        } else {
          card.classList.add('fp-group-on');
          card.querySelector('.fp-gt-lbl').textContent = 'Activo';
          moveToChosen(fromSel, toSel, opt.v);
        }
      });
      grid.appendChild(card);
    });

    wrap.appendChild(grid);

    /* Ocultar selector original e insertar UI */
    var selectorWrap = fromSel.closest('.selector');
    if (selectorWrap) selectorWrap.style.cssText = 'display:none!important';
    var fieldRow = document.querySelector('.field-groups');
    if (fieldRow) {
      var lbl2 = fieldRow.querySelector('label');
      if (lbl2) lbl2.style.cssText = 'display:none!important';
      fieldRow.style.cssText = 'display:block!important;padding:0!important';
      fieldRow.appendChild(wrap);
    } else if (selectorWrap) {
      selectorWrap.insertAdjacentElement('afterend', wrap);
    }
    return true;
  }

  /* ══════════════════════════════════════════════════════════════
     PERMISSIONS ACCORDION
     ══════════════════════════════════════════════════════════════ */
  function buildPermsAccordion() {
    var fromSel = document.getElementById('id_user_permissions_from');
    var toSel   = document.getElementById('id_user_permissions_to');
    if (!fromSel || !toSel) return false;

    var chosen = new Set(Array.from(toSel.options).map(function (o) { return o.value; }));
    var all = [];
    Array.from(fromSel.options).forEach(function (o) { all.push({ v: o.value, t: o.text, on: false }); });
    Array.from(toSel.options).forEach(function (o) { all.push({ v: o.value, t: o.text, on: true }); });

    /* Agrupar por app ("App | Modelo | Acción") */
    var appMap = {};
    all.forEach(function (opt) {
      var parts  = opt.t.split(' | ');
      var app    = (parts[0] || 'General').trim();
      var model  = (parts[1] || '').trim();
      var action = (parts[2] || opt.t).trim();
      if (!appMap[app]) appMap[app] = [];
      appMap[app].push({ v: opt.v, action: action, model: model, on: opt.on });
    });

    var apps = Object.keys(appMap).sort(function (a, b) { return a.localeCompare(b); });
    var totalOn = chosen.size;

    /* Contenedor raíz */
    var wrap = document.createElement('div');
    wrap.className = 'fp-perms-ui';

    /* Toolbar */
    var toolbar = document.createElement('div');
    toolbar.className = 'fp-perms-toolbar';
    var counter = document.createElement('span');
    counter.className = 'fp-perms-counter';
    counter.textContent = totalOn + ' seleccionados';
    toolbar.innerHTML =
      '<input type="text" class="fp-perms-search" placeholder="🔍  Buscar permiso...">';
    toolbar.appendChild(counter);
    var clearBtn = document.createElement('button');
    clearBtn.type = 'button';
    clearBtn.className = 'fp-perms-clear-btn';
    clearBtn.textContent = '✕ Limpiar todo';
    toolbar.appendChild(clearBtn);
    wrap.appendChild(toolbar);

    var searchInput = toolbar.querySelector('.fp-perms-search');

    function refreshCounter() {
      var n = toSel.options.length;
      counter.textContent = n + ' seleccionado' + (n !== 1 ? 's' : '');
    }
    function refreshBadge(section) {
      var total = section.querySelectorAll('.fp-perm-item').length;
      var on    = section.querySelectorAll('.fp-perm-item--on').length;
      section.querySelector('.fp-perm-sec-badge').textContent = on + ' / ' + total;
    }

    /* Secciones */
    apps.forEach(function (appName) {
      var perms = appMap[appName];
      var selN  = perms.filter(function (p) { return p.on; }).length;

      var section = document.createElement('div');
      section.className = 'fp-perm-section';

      /* Header */
      var hdr = document.createElement('div');
      hdr.className = 'fp-perm-sec-hdr';
      hdr.innerHTML =
        '<span class="fp-perm-sec-arrow">▶</span>' +
        '<span class="fp-perm-sec-name">' + appName + '</span>' +
        '<span class="fp-perm-sec-badge">' + selN + ' / ' + perms.length + '</span>' +
        '<button type="button" class="fp-perm-sec-all">Todos</button>' +
        '<button type="button" class="fp-perm-sec-none">Ninguno</button>';

      /* Body */
      var body = document.createElement('div');
      body.className = 'fp-perm-sec-body';

      perms.forEach(function (perm) {
        var item = document.createElement('label');
        item.className = 'fp-perm-item' + (perm.on ? ' fp-perm-item--on' : '');
        item.innerHTML =
          '<input type="checkbox" class="fp-perm-cb" data-val="' + perm.v + '"' + (perm.on ? ' checked' : '') + '>' +
          '<div><div class="fp-perm-txt">' + perm.action + '</div>' +
          (perm.model ? '<div class="fp-perm-model">' + perm.model + '</div>' : '') +
          '</div>';

        var cb = item.querySelector('.fp-perm-cb');
        cb.addEventListener('change', function (e) {
          e.stopPropagation();
          if (cb.checked) {
            item.classList.add('fp-perm-item--on');
            moveToChosen(fromSel, toSel, perm.v);
          } else {
            item.classList.remove('fp-perm-item--on');
            moveToAvail(fromSel, toSel, perm.v);
          }
          refreshBadge(section);
          refreshCounter();
        });
        body.appendChild(item);
      });

      /* Toggle acordeón */
      hdr.addEventListener('click', function (e) {
        if (e.target.tagName === 'BUTTON') return;
        var open = section.classList.toggle('fp-open');
        hdr.querySelector('.fp-perm-sec-arrow').textContent = open ? '▼' : '▶';
      });

      /* Todos / Ninguno */
      hdr.querySelector('.fp-perm-sec-all').addEventListener('click', function (e) {
        e.stopPropagation();
        body.querySelectorAll('.fp-perm-item:not(.fp-perm-item--hidden)').forEach(function (it) {
          var c = it.querySelector('.fp-perm-cb');
          if (!c.checked) { c.checked = true; it.classList.add('fp-perm-item--on'); moveToChosen(fromSel, toSel, c.dataset.val); }
        });
        refreshBadge(section); refreshCounter();
      });
      hdr.querySelector('.fp-perm-sec-none').addEventListener('click', function (e) {
        e.stopPropagation();
        body.querySelectorAll('.fp-perm-item:not(.fp-perm-item--hidden)').forEach(function (it) {
          var c = it.querySelector('.fp-perm-cb');
          if (c.checked) { c.checked = false; it.classList.remove('fp-perm-item--on'); moveToAvail(fromSel, toSel, c.dataset.val); }
        });
        refreshBadge(section); refreshCounter();
      });

      section.appendChild(hdr);
      section.appendChild(body);
      wrap.appendChild(section);
    });

    /* Búsqueda */
    searchInput.addEventListener('input', function () {
      var q = searchInput.value.trim().toLowerCase();
      wrap.querySelectorAll('.fp-perm-section').forEach(function (sec) {
        var anyVis = false;
        sec.querySelectorAll('.fp-perm-item').forEach(function (it) {
          var txt = it.querySelector('.fp-perm-txt').textContent.toLowerCase();
          var mdl = (it.querySelector('.fp-perm-model') || { textContent: '' }).textContent.toLowerCase();
          var show = !q || txt.includes(q) || mdl.includes(q);
          it.classList.toggle('fp-perm-item--hidden', !show);
          if (show) anyVis = true;
        });
        if (q) {
          if (anyVis) { sec.classList.add('fp-open'); sec.querySelector('.fp-perm-sec-arrow').textContent = '▼'; }
          else         { sec.classList.remove('fp-open'); sec.querySelector('.fp-perm-sec-arrow').textContent = '▶'; }
        }
      });
    });

    /* Limpiar todo */
    clearBtn.addEventListener('click', function () {
      wrap.querySelectorAll('.fp-perm-item').forEach(function (it) {
        var c = it.querySelector('.fp-perm-cb');
        if (c.checked) { c.checked = false; it.classList.remove('fp-perm-item--on'); moveToAvail(fromSel, toSel, c.dataset.val); }
      });
      wrap.querySelectorAll('.fp-perm-section').forEach(function (s) { refreshBadge(s); });
      refreshCounter();
    });

    /* Insertar UI */
    var selectorWrap = fromSel.closest('.selector');
    if (selectorWrap) selectorWrap.style.cssText = 'display:none!important';
    var fieldRow = document.querySelector('.field-user_permissions');
    if (fieldRow) {
      var lbl = fieldRow.querySelector('label');
      if (lbl) lbl.style.cssText = 'display:none!important';
      fieldRow.style.cssText = 'display:block!important;padding:0!important';
      fieldRow.appendChild(wrap);
    } else if (selectorWrap) {
      selectorWrap.insertAdjacentElement('afterend', wrap);
    }
    return true;
  }

  /* ══════════════════════════════════════════════════════════════
     TARJETAS DE CAMPOS — Credenciales, Info personal, Documento
     Mismo patrón visual que las bool cards de Permisos.
     ══════════════════════════════════════════════════════════════ */
  function initCredentialsSection() {

    var FIELD_CARDS = [
      /* Credenciales */
      { field: 'email',           icon: '✉️', tag: 'input'  },
      { field: 'username',        icon: '👤', tag: 'input'  },
      /* Información personal */
      { field: 'first_name',      icon: '🪪', tag: 'input'  },
      { field: 'last_name',       icon: '🪪', tag: 'input'  },
      { field: 'phone',           icon: '📱', tag: 'input'  },
      /* birth_date se maneja por separado (SelectDateWidget = 3 selects) */
      /* Documento de identidad */
      { field: 'document_type',   icon: '📋', tag: 'select' },
      { field: 'document_number', icon: '🔢', tag: 'input'  },
      /* Seguridad */
      { field: 'phone_2fa',       icon: '🔐', tag: 'input'  },
      /* Formulario de alta y cambio de contraseña */
      { field: 'password1',       icon: '🔑', tag: 'input'  },
      { field: 'password2',       icon: '🔑', tag: 'input'  },
    ];

    /* Helper: construye una tarjeta genérica dado un row y un array de elementos */
    function buildFieldCard(row, icon, elements) {
      var labelEl   = row.querySelector('label');
      var labelText = labelEl ? labelEl.textContent.replace(/\s*:?\s*\*?\s*$/, '').trim() : '';
      var helpEl    = row.querySelector('.help, p.help, .helptext');
      var helpText  = helpEl ? helpEl.textContent.trim() : '';
      var required  = !!row.querySelector('[required], .required');

      var card = document.createElement('div');
      card.className = 'fp-field-card';

      var icoSpan = document.createElement('span');
      icoSpan.className = 'fp-field-ico';
      icoSpan.textContent = icon;

      var body = document.createElement('div');
      body.className = 'fp-field-body';

      var lbl = document.createElement('div');
      lbl.className = 'fp-field-label';
      lbl.innerHTML = labelText + (required ? ' <span class="fp-field-req">*</span>' : '');
      body.appendChild(lbl);

      var inputsWrap = document.createElement('div');
      inputsWrap.className = 'fp-field-inputs-row';
      elements.forEach(function (el) {
        el.classList.add('fp-field-input');
        inputsWrap.appendChild(el);
        el.addEventListener('focus', function () { card.classList.add('fp-field-card--focus'); });
        el.addEventListener('blur',  function () { card.classList.remove('fp-field-card--focus'); });
      });
      body.appendChild(inputsWrap);

      if (helpText) {
        var help = document.createElement('div');
        help.className = 'fp-field-help';
        help.textContent = helpText;
        body.appendChild(help);
      }

      card.appendChild(icoSpan);
      card.appendChild(body);
      row.style.cssText = 'display:none!important';
      row.insertAdjacentElement('afterend', card);
    }

    FIELD_CARDS.forEach(function (m) {
      var row = document.querySelector('.field-' + m.field);
      if (!row) return;
      var el = row.querySelector(m.tag);
      if (!el) return;
      buildFieldCard(row, m.icon, [el]);
    });

    /* ── Fecha de nacimiento: SelectDateWidget → 3 selects (día/mes/año) ── */
    var bdRow = document.querySelector('.field-birth_date');
    if (bdRow) {
      var bdSelects = Array.from(bdRow.querySelectorAll('select'));
      if (bdSelects.length) buildFieldCard(bdRow, '🎂', bdSelects);
    }

    /* ── Contraseña — tarjeta especial sin input editable ─────── */
    var pwRow = document.querySelector('.field-password');
    if (!pwRow) return;
    var pwLink = pwRow.querySelector('a[href]');
    var pwHref = pwLink ? pwLink.href : null;

    var pwCard = document.createElement('div');
    pwCard.className = 'fp-field-card fp-field-card--pw';
    pwCard.innerHTML =
      '<span class="fp-field-ico">🔑</span>' +
      '<div class="fp-field-body">' +
        '<div class="fp-field-label">Contraseña</div>' +
        '<div class="fp-pw-desc">Cifrada con <strong>argon2id</strong>. No se almacena en texto plano.</div>' +
        (pwHref ? '<a href="' + pwHref + '" class="fp-pw-btn">🔄 Cambiar contraseña</a>' : '') +
      '</div>';

    pwRow.style.cssText = 'display:none!important';
    pwRow.insertAdjacentElement('afterend', pwCard);
  }

  /* ══════════════════════════════════════════════════════════════
     FECHAS — tarjetas de solo lectura para la sección Fechas
     ══════════════════════════════════════════════════════════════ */
  function initDatesCards() {
    var DATE_META = [
      { field: 'last_login',  icon: '🕐', label: 'Último acceso' },
      { field: 'date_joined', icon: '📅', label: 'Fecha de alta' },
      { field: 'created_at',  icon: '🗓️', label: 'Fecha de creación' },
      { field: 'updated_at',  icon: '✏️', label: 'Última actualización' },
    ];

    var rows = [];
    DATE_META.forEach(function (m) {
      var row = document.querySelector('.field-' + m.field);
      if (row) rows.push({ meta: m, row: row });
    });
    if (!rows.length) return;

    var wrap = document.createElement('div');
    wrap.className = 'fp-dates-grid';

    rows.forEach(function (r) {
      var valueEl = r.row.querySelector('.readonly') || r.row.querySelector('p');
      var value   = valueEl ? valueEl.textContent.trim() : '';
      if (!value || value === '-' || value === '(None)' || value === 'None') value = '—';

      var card = document.createElement('div');
      card.className = 'fp-date-card';
      card.innerHTML =
        '<span class="fp-date-ico">' + r.meta.icon + '</span>' +
        '<div class="fp-date-body">' +
          '<div class="fp-date-label">' + r.meta.label + '</div>' +
          '<div class="fp-date-value">' + value + '</div>' +
        '</div>';
      wrap.appendChild(card);
      r.row.style.cssText = 'display:none!important';
    });

    rows[0].row.insertAdjacentElement('beforebegin', wrap);
  }

  /* ══════════════════════════════════════════════════════════════
     BARRA DE ACCIONES INFERIOR
     Renderizada en el servidor vía template override:
       backend/templates/admin/users/user/change_form.html
     Esta función no necesita hacer nada; se conserva como
     punto de extensión para casos edge (popups, etc.).
     ══════════════════════════════════════════════════════════════ */
  function initSubmitBar() {
    /* No-op: el template override ya inyecta #fp-submit-bar en el DOM. */
  }

  /* ── Entry points ───────────────────────────────────────────── */

  /* Bool cards + Submit bar: no dependen de SelectFilter, corren en DOMContentLoaded */
  function onDOMReady() {
    /* Solo actuar en formularios, nunca en el changelist */
    if (document.getElementById('result_list')) return;
    /* Tampoco en el formulario de cambio de contraseña (tiene su propio template) */
    if (window.location.pathname.indexOf('/password/') !== -1) return;
    initCredentialsSection();
    initBoolCards();
    initDatesCards();
    initSubmitBar();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', onDOMReady);
  } else {
    onDOMReady();
  }

  /* Groups + Permissions: SelectFilter2.js de Django crea los from/to
     en window.load. Usamos retry para tolerar variaciones de orden. */
  window.addEventListener('load', function () {
    var attempts = 0;
    var maxMs    = 4000;
    var interval = 120;

    (function tryInit() {
      attempts++;
      var fromGroups = document.getElementById('id_groups_from');
      var fromPerms  = document.getElementById('id_user_permissions_from');

      var doneGroups = fromGroups ? buildGroupCards() : false;
      var donePerms  = fromPerms  ? buildPermsAccordion() : false;

      /* Reintentar si alguno no está listo y no se agotó el tiempo */
      if ((!doneGroups || !donePerms) && attempts * interval < maxMs) {
        setTimeout(tryInit, interval);
      }
    })();
  });

})();
