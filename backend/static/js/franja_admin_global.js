/**
 * Franja Pixelada — Admin Global JS
 *
 * Capa única de normalización del changelist:
 *  - Una función idempotente (`normalizeChangelistUI`) siempre reconstruye la barra.
 *  - Se ejecuta en carga inicial, pjax, popstate, pageshow y tras mutaciones relevantes.
 *  - Elimina cualquier #fp-action-bar previo (evita duplicados con módulos legacy).
 *
 * Acciones masivas:
 *  - El <select name="action"> permanece en el DOM (oculto) para Jazzmin/Select2.
 *  - body.fp-bar-active + CSS oculta .actions de forma persistente.
 */
(function () {
  'use strict';

  var SEL_ALL = '#result_list tbody input[name="_selected_action"]';
  var SEL_CHKD = '#result_list tbody input[name="_selected_action"]:checked';
  var DEBOUNCE_MS = 120;
  var _scheduleTimer = null;
  var _running = false;

  var LABEL_MAP = {
    'action_importar_variantes': 'Importar variantes',
    'action_importar_a_tienda': 'Importar a mi tienda',
    'action_sincronizar_catalogo': 'Sincronizar catálogo',
    'recalcular_stock_seleccionados': 'Recalcular stock',
  };

  function shortLabel(value, text) {
    if (LABEL_MAP[value]) return LABEL_MAP[value];
    return text
      .replace(/\s+\([^)]*\)/g, '')
      .replace(/\s*[—–]\s*.*/g, '')
      .replace(/\s+ahora\b/gi, '')
      .replace(/\s+seleccionado[s/]?[as]*/gi, '')
      .replace(/\s+selected.*/i, '')
      .trim();
  }

  function getChecked() {
    return document.querySelectorAll(SEL_CHKD).length;
  }
  function getTotal() {
    return document.querySelectorAll(SEL_ALL).length;
  }

  function syncToggle() {
    var toggle = document.getElementById('action-toggle');
    if (!toggle) return;
    var total = getTotal();
    var checked = getChecked();
    if (total === 0) {
      toggle.checked = false;
      toggle.indeterminate = false;
    } else if (checked === total) {
      toggle.checked = true;
      toggle.indeterminate = false;
    } else if (checked === 0) {
      toggle.checked = false;
      toggle.indeterminate = false;
    } else {
      toggle.checked = false;
      toggle.indeterminate = true;
    }
  }

  function refreshBar() {
    var checked = getChecked();
    var total = getTotal();
    var counter = document.getElementById('fp-action-counter');
    if (counter) counter.textContent = checked + ' de ' + total + ' seleccionados';
    document.querySelectorAll('.fp-action-btn').forEach(function (btn) {
      btn.disabled = checked === 0;
    });
  }

  function onSelectionChange() {
    syncToggle();
    refreshBar();
  }

  function teardownChangelistChrome() {
    document.body.classList.remove('fp-bar-active');
    document.querySelectorAll('#fp-action-bar').forEach(function (node) {
      if (node.parentNode) node.parentNode.removeChild(node);
    });
  }

  /**
   * Reconstruye siempre la barra desde el <select> actual (fuente única de verdad).
   */
  function normalizeChangelistUI() {
    if (_running) return;
    _running = true;
    try {
      teardownChangelistChrome();

      var form = document.getElementById('changelist-form');
      if (!form) return;

      var actionsDiv = form.querySelector('.actions');
      if (!actionsDiv) return;

      var select = actionsDiv.querySelector('select[name="action"]');
      if (!select) return;

      var actions = Array.from(select.options).filter(function (o) {
        return o.value !== '';
      });
      if (actions.length === 0) {
        document.body.classList.remove('fp-bar-active');
        actionsDiv.style.display = '';
        actionsDiv.removeAttribute('aria-hidden');
        return;
      }

      actionsDiv.style.display = 'none';
      actionsDiv.setAttribute('aria-hidden', 'true');
      document.body.classList.add('fp-bar-active');

      form.querySelectorAll('.actions button, .actions input[type="submit"]').forEach(function (el) {
        el.style.cssText =
          'position:absolute!important;width:1px!important;height:1px!important;' +
          'opacity:0!important;pointer-events:none!important;overflow:hidden!important;';
        el.setAttribute('tabindex', '-1');
        el.setAttribute('aria-hidden', 'true');
      });

      var bar = document.createElement('div');
      bar.id = 'fp-action-bar';
      bar.className = 'fp-action-bar';
      bar.setAttribute('data-fp-ui', 'changelist-actions');

      var btnsWrap = document.createElement('div');
      btnsWrap.className = 'fp-action-btns';

      actions.forEach(function (opt) {
        var btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'fp-action-btn';
        btn.textContent = shortLabel(opt.value, opt.text);
        btn.title = opt.text;
        btn.dataset.action = opt.value;
        btn.disabled = true;
        var lc = opt.value.toLowerCase() + opt.text.toLowerCase();
        if (lc.includes('delete') || lc.includes('elimin')) {
          btn.classList.add('fp-action-btn--danger');
        }
        btnsWrap.appendChild(btn);
      });

      bar.appendChild(btnsWrap);

      var counter = document.createElement('span');
      counter.id = 'fp-action-counter';
      counter.className = 'fp-action-counter';
      bar.appendChild(counter);

      /* Siempre arriba del formulario: primer render estable en todos los módulos */
      if (form.firstChild) {
        form.insertBefore(bar, form.firstChild);
      } else {
        form.appendChild(bar);
      }

      onSelectionChange();
    } finally {
      _running = false;
    }
  }

  function scheduleNormalizeChangelist() {
    clearTimeout(_scheduleTimer);
    _scheduleTimer = setTimeout(function () {
      _scheduleTimer = null;
      normalizeChangelistUI();
      try {
        document.dispatchEvent(new CustomEvent('fp-admin:changelist-normalized'));
      } catch (e) { /* IE11 */ }
    }, DEBOUNCE_MS);
  }

  document.addEventListener('click', function (e) {
    if (!e.target || e.target.id !== 'action-toggle') return;
    var checked = e.target.checked;
    document.querySelectorAll(SEL_ALL).forEach(function (cb) {
      cb.checked = checked;
    });
    onSelectionChange();
  });

  document.addEventListener('change', function (e) {
    if (!e.target || e.target.name !== '_selected_action') return;
    onSelectionChange();
  });

  document.addEventListener('click', function (e) {
    var btn = e.target.closest('.fp-action-btn');
    if (!btn || btn.disabled) return;
    var form = document.getElementById('changelist-form');
    if (!form) return;
    var select = form.querySelector('select[name="action"]');
    if (!select) return;
    select.value = btn.dataset.action;
    form.submit();
  });

  /* ── Ciclo de vida SPA / PJAX (AdminLTE + Jazzmin) ───────────────────────── */
  document.addEventListener('pjax:send', function () {
    teardownChangelistChrome();
  });

  ['pjax:complete', 'pjax:success', 'pjax:end'].forEach(function (ev) {
    document.addEventListener(ev, scheduleNormalizeChangelist);
  });

  window.addEventListener('popstate', scheduleNormalizeChangelist);

  window.addEventListener('pageshow', function (event) {
    if (event.persisted) scheduleNormalizeChangelist();
  });

  /* Boot inicial */
  function boot() {
    scheduleNormalizeChangelist();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }

  /* Fall back: contenido reemplazado sin evento pjax (filtros, algunos POST) */
  var obsTimer = null;
  var observer = new MutationObserver(function (mutations) {
    var interesting = false;
    for (var i = 0; i < mutations.length; i++) {
      var m = mutations[i];
      for (var j = 0; j < m.addedNodes.length; j++) {
        var n = m.addedNodes[j];
        if (n.nodeType !== 1) continue;
        if (n.id === 'changelist-form' || (n.querySelector && n.querySelector('#changelist-form'))) {
          interesting = true;
          break;
        }
        if (n.classList && n.classList.contains('actions')) interesting = true;
      }
      if (interesting) break;
    }
    if (interesting) {
      clearTimeout(obsTimer);
      obsTimer = setTimeout(scheduleNormalizeChangelist, DEBOUNCE_MS);
    }
  });

  function attachObserver() {
    var target = document.querySelector('.content-wrapper') || document.body;
    observer.observe(target, { childList: true, subtree: true });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', attachObserver);
  } else {
    attachObserver();
  }

  window.FPAdminChangelist = {
    normalize: normalizeChangelistUI,
    schedule: scheduleNormalizeChangelist,
  };
})();
