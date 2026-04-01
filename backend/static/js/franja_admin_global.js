/**
 * Franja Pixelada — Admin Global JS
 *
 * Responsabilidades:
 * 1. Checkbox "seleccionar todos" — event delegation (sobrevive a PJAX)
 * 2. Contador dinámico de selección + botón deseleccionar todo
 * 3. Botones de acciones masivas — habilitar/deshabilitar + loading state
 * 4. Modal de confirmación para acciones destructivas
 * 5. Sistema de toasts globales
 */
(function () {
  'use strict';

  /* ── Selectores ──────────────────────────────────────────────────────────── */
  var SEL_CHILDREN = '#result_list tbody input[name="_selected_action"]';
  var SEL_CHECKED  = '#result_list tbody input[name="_selected_action"]:checked';
  var DEBOUNCE_MS  = 120;
  var _scheduleTimer = null;

  /* ── Helpers base ────────────────────────────────────────────────────────── */
  function getToggle()   { return document.getElementById('action-toggle'); }
  function getChildren() { return document.querySelectorAll(SEL_CHILDREN); }
  function getChecked()  { return document.querySelectorAll(SEL_CHECKED).length; }
  function getTotal()    { return getChildren().length; }

  /* ════════════════════════════════════════════════════════════════════════════
     1. CHECKBOX MASTER — sincronización completa
     ════════════════════════════════════════════════════════════════════════════ */
  function syncToggleState() {
    var toggle  = getToggle();
    if (!toggle) return;
    var total   = getTotal();
    var checked = getChecked();
    toggle.checked       = total > 0 && checked === total;
    toggle.indeterminate = checked > 0 && checked < total;
  }

  /* ════════════════════════════════════════════════════════════════════════════
     2. CONTADOR + BOTÓN DESELECCIONAR
     ════════════════════════════════════════════════════════════════════════════ */
  function getOrCreateCounter() {
    var bar = document.querySelector('.fp-action-bar:not(.fp-action-bar--mirror)');
    if (!bar) return null;
    var el = bar.querySelector('.fp-sel-counter');
    if (!el) {
      el = document.createElement('span');
      el.className = 'fp-sel-counter';
      var meta = bar.querySelector('.fp-action-meta');
      if (meta) meta.appendChild(el);
      else bar.appendChild(el);
    }
    return el;
  }

  function getOrCreateDeselectBtn() {
    var bar = document.querySelector('.fp-action-bar:not(.fp-action-bar--mirror)');
    if (!bar) return null;
    var btn = bar.querySelector('.fp-deselect-btn');
    if (!btn) {
      btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'fp-deselect-btn';
      btn.title = 'Limpiar selección';
      btn.innerHTML = '✕ Deseleccionar';
      btn.addEventListener('click', function () {
        getChildren().forEach(function (cb) { cb.checked = false; });
        var toggle = getToggle();
        if (toggle) { toggle.checked = false; toggle.indeterminate = false; }
        syncAll();
      });
      var meta = bar.querySelector('.fp-action-meta');
      if (meta) meta.insertBefore(btn, meta.firstChild);
      else bar.appendChild(btn);
    }
    return btn;
  }

  function updateCounter() {
    var checked = getChecked();
    var total   = getTotal();
    var counter = getOrCreateCounter();
    var deselBtn = getOrCreateDeselectBtn();

    if (counter) {
      if (checked === 0) {
        counter.textContent = total > 0 ? total + ' elemento' + (total !== 1 ? 's' : '') : '';
        counter.classList.remove('has-selection');
      } else {
        counter.textContent = checked + ' de ' + total + ' seleccionado' + (checked !== 1 ? 's' : '');
        counter.classList.add('has-selection');
      }
    }
    if (deselBtn) {
      deselBtn.classList.toggle('visible', checked > 0);
    }
  }

  /* ════════════════════════════════════════════════════════════════════════════
     3. BOTONES DE ACCIONES MASIVAS
     ════════════════════════════════════════════════════════════════════════════ */
  function refreshBulkActionButtons() {
    var checked = getChecked();
    var form    = document.getElementById('changelist-form');
    if (!form) return;
    form.querySelectorAll('.fp-action-btn').forEach(function (btn) {
      if (!btn.classList.contains('fp-loading')) {
        btn.disabled = checked === 0;
      }
    });
  }

  function setButtonLoading(btn, loading) {
    if (loading) {
      btn.classList.add('fp-loading');
      btn.dataset.originalText = btn.textContent;
    } else {
      btn.classList.remove('fp-loading');
      if (btn.dataset.originalText) btn.textContent = btn.dataset.originalText;
    }
  }

  /* ════════════════════════════════════════════════════════════════════════════
     4. MODAL DE CONFIRMACIÓN
     ════════════════════════════════════════════════════════════════════════════ */
  function getOrCreateConfirmModal() {
    var overlay = document.getElementById('fp-confirm-overlay');
    if (overlay) return overlay;

    overlay = document.createElement('div');
    overlay.id = 'fp-confirm-overlay';
    overlay.innerHTML =
      '<div id="fp-confirm-dialog">' +
        '<p id="fp-confirm-title"></p>' +
        '<p id="fp-confirm-body"></p>' +
        '<div class="fp-confirm-actions">' +
          '<button id="fp-confirm-cancel" type="button">Cancelar</button>' +
          '<button id="fp-confirm-ok" type="button">Confirmar</button>' +
        '</div>' +
      '</div>';
    document.body.appendChild(overlay);

    document.getElementById('fp-confirm-cancel').addEventListener('click', closeConfirm);
    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) closeConfirm();
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && overlay.classList.contains('open')) closeConfirm();
    });
    return overlay;
  }

  var _confirmCallback = null;

  function openConfirm(title, body, onOk) {
    var overlay = getOrCreateConfirmModal();
    document.getElementById('fp-confirm-title').textContent = title;
    document.getElementById('fp-confirm-body').textContent  = body;
    _confirmCallback = onOk;
    overlay.classList.add('open');
    document.getElementById('fp-confirm-ok').focus();
  }

  function closeConfirm() {
    var overlay = document.getElementById('fp-confirm-overlay');
    if (overlay) overlay.classList.remove('open');
    _confirmCallback = null;
  }

  document.addEventListener('click', function (e) {
    if (e.target && e.target.id === 'fp-confirm-ok' && _confirmCallback) {
      var cb = _confirmCallback;
      closeConfirm();
      cb();
    }
  });

  /* ════════════════════════════════════════════════════════════════════════════
     5. TOASTS GLOBALES
     ════════════════════════════════════════════════════════════════════════════ */
  function getOrCreateToastContainer() {
    var el = document.getElementById('fp-toast-container');
    if (!el) {
      el = document.createElement('div');
      el.id = 'fp-toast-container';
      document.body.appendChild(el);
    }
    return el;
  }

  function showToast(message, type, duration) {
    type     = type     || 'info';
    duration = duration || 4000;
    var icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };
    var container = getOrCreateToastContainer();
    var toast = document.createElement('div');
    toast.className = 'fp-toast fp-toast--' + type;
    toast.innerHTML =
      '<span class="fp-toast-icon">' + (icons[type] || 'ℹ️') + '</span>' +
      '<span>' + message + '</span>';
    container.appendChild(toast);
    setTimeout(function () {
      toast.classList.add('fp-toast--out');
      setTimeout(function () { toast.remove(); }, 350);
    }, duration);
  }

  /* ── Leer mensajes de Django (success / error) y convertirlos a toasts ── */
  function absorbDjangoMessages() {
    var alerts = document.querySelectorAll('.alert, .messages li, li.success, li.error, li.warning, li.info');
    alerts.forEach(function (el) {
      var text = el.textContent.trim();
      if (!text) return;
      var type = 'info';
      if (el.classList.contains('success')) type = 'success';
      else if (el.classList.contains('error')) type = 'error';
      else if (el.classList.contains('warning')) type = 'warning';
      else if (el.classList.contains('alert-success')) type = 'success';
      else if (el.classList.contains('alert-danger'))  type = 'error';
      else if (el.classList.contains('alert-warning')) type = 'warning';
      showToast(text, type, 5000);
      el.style.display = 'none';
    });
  }

  /* ════════════════════════════════════════════════════════════════════════════
     SINCRONIZACIÓN COMPLETA
     ════════════════════════════════════════════════════════════════════════════ */
  function syncAll() {
    syncToggleState();
    updateCounter();
    refreshBulkActionButtons();
  }

  /* ── Event delegation (document-level, sobrevive a PJAX) ───────────────── */
  document.addEventListener('change', function (e) {
    var t = e.target;
    if (!t) return;
    if (t.id === 'action-toggle') {
      var checked = t.checked;
      getChildren().forEach(function (cb) { cb.checked = checked; });
      syncAll();
    } else if (t.name === '_selected_action') {
      syncAll();
    }
  });

  document.addEventListener('click', function (e) {
    var t = e.target;
    if (!t) return;
    if (t.id === 'action-toggle' || t.name === '_selected_action') {
      setTimeout(syncAll, 0);
    }
  });

  /* ── Botones de acciones masivas — con confirmación para danger ─────────── */
  document.addEventListener('click', function (e) {
    var btn = e.target.closest('.fp-action-btn');
    if (!btn || btn.disabled || btn.classList.contains('fp-loading')) return;
    var form = document.getElementById('changelist-form');
    if (!form) return;
    var select = form.querySelector('select[name="action"]');
    if (!select) return;

    function executeAction() {
      setButtonLoading(btn, true);
      select.value = btn.dataset.action;
      var submitBtn = form.querySelector('button[type="submit"][name="index"]');
      if (submitBtn) submitBtn.click();
      else form.submit();
    }

    if (btn.classList.contains('fp-action-btn--danger')) {
      var count  = getChecked();
      var label  = btn.textContent.trim();
      openConfirm(
        '¿Confirmar acción?',
        'Vas a ejecutar "' + label + '" sobre ' + count + ' elemento' + (count !== 1 ? 's' : '') + '. Esta acción no se puede deshacer.',
        executeAction
      );
    } else {
      executeAction();
    }
  });

  /* ── Re-sincronizar tras PJAX / popstate ────────────────────────────────── */
  function scheduleSync() {
    clearTimeout(_scheduleTimer);
    _scheduleTimer = setTimeout(function () {
      _scheduleTimer = null;
      syncAll();
      absorbDjangoMessages();
      try {
        document.dispatchEvent(new CustomEvent('fp-admin:changelist-normalized'));
      } catch (e) { /* IE11 */ }
    }, DEBOUNCE_MS);
  }

  ['pjax:complete', 'pjax:success', 'pjax:end'].forEach(function (ev) {
    document.addEventListener(ev, scheduleSync);
  });
  window.addEventListener('popstate', scheduleSync);
  window.addEventListener('pageshow', function (event) {
    if (event.persisted) scheduleSync();
  });

  /* ── Popup mode: limpiar margin-left inline que AdminLTE inyecta por JS ── */
  function fixPopupLayout() {
    if (!document.body.classList.contains('popup')) return;
    var targets = document.querySelectorAll('.content-wrapper, .wrapper, #wrapper');
    targets.forEach(function (el) {
      el.style.removeProperty('margin-left');
      el.style.removeProperty('margin-right');
      el.style.setProperty('margin-left',  '0', 'important');
      el.style.setProperty('margin-right', '0', 'important');
      el.style.setProperty('width',       '100%', 'important');
    });
  }

  /* ── Boot ───────────────────────────────────────────────────────────────── */
  function boot() {
    fixPopupLayout();
    // AdminLTE puede re-inyectar el margin después del DOMContentLoaded
    if (document.body.classList.contains('popup')) {
      setTimeout(fixPopupLayout, 50);
      setTimeout(fixPopupLayout, 200);
      setTimeout(fixPopupLayout, 500);
    }
    scheduleSync();
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }

  /* ── API pública ────────────────────────────────────────────────────────── */
  window.FPAdmin = {
    toast:    showToast,
    confirm:  openConfirm,
    syncAll:  syncAll,
    schedule: scheduleSync,
    // retrocompatibilidad
    FPAdminChangelist: { schedule: scheduleSync, refresh: refreshBulkActionButtons, syncAll: syncAll, normalize: scheduleSync },
  };
  window.FPAdminChangelist = window.FPAdmin.FPAdminChangelist;
})();
