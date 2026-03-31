/**
 * Franja Pixelada — SplitDateWidget
 *
 * PATRÓN PORTAL: los paneles se mueven a <body> en el init, escapando
 * cualquier ancestor con transform/overflow que atrape position:fixed.
 * Posicionamiento inteligente: debajo si hay espacio, arriba si no.
 */
(function () {
  'use strict';

  /* Ancho de cada panel en px */
  var PANEL_W = { day: 360, month: 280 };

  function initAll() {
    document.querySelectorAll('.fp-split-date').forEach(initOne);

    document.addEventListener('click', function (e) {
      if (!e.target.closest('.fp-split-date') && !e.target.closest('.fp-sd-panel')) {
        closeAllPanels();
      }
    });

    window.addEventListener('resize', closeAllPanels);
    window.addEventListener('scroll', closeAllPanels, true);
  }

  function initOne(container) {
    var fieldName = container.dataset.field;
    if (!fieldName) return;

    /* ── PORTAL: mover panels al <body> ──────────────────────────────── */
    ['day', 'month'].forEach(function (part) {
      var panelId = 'fp-sd-' + fieldName + '-' + part + '-panel';
      var panel   = document.getElementById(panelId);
      if (panel && panel.parentNode !== document.body) {
        /* Guardar referencia al container en el panel */
        panel.dataset.fieldRef = fieldName;
        document.body.appendChild(panel);
      }
    });

    /* Limitar año al actual */
    var yearInput = container.querySelector('.fp-sd-year');
    if (yearInput) yearInput.setAttribute('max', new Date().getFullYear());

    /* ── Triggers (Día / Mes) ────────────────────────────────────────── */
    container.querySelectorAll('.fp-sd-trigger').forEach(function (trigger) {
      trigger.addEventListener('click', function (e) {
        e.stopPropagation();
        var part    = trigger.dataset.part;
        var panelId = 'fp-sd-' + fieldName + '-' + part + '-panel';
        var panel   = document.getElementById(panelId);
        if (!panel) return;

        var isOpen = !panel.hidden;
        closeAllPanels();

        if (!isOpen) {
          /* Mostrar invisible para medir altura real */
          panel.style.visibility = 'hidden';
          panel.hidden = false;

          positionPanel(container, panel, part);

          panel.style.visibility = '';
          trigger.setAttribute('aria-expanded', 'true');
          trigger.classList.add('fp-sd-trigger--open');
        }
      });
    });

    /* ── Chips ───────────────────────────────────────────────────────── */
    container.querySelectorAll('.fp-sd-chip').forEach(function (chip) {
      /* Los chips quedan en el panel (ahora en body) — delegar al panel */
    });
  }

  /* Delegación en body para chips (necesario porque los paneles están en body) */
  document.addEventListener('click', function (e) {
    var chip = e.target.closest('.fp-sd-chip');
    if (!chip) return;

    var panelEl   = chip.closest('.fp-sd-panel');
    if (!panelEl) return;

    var fieldName = panelEl.dataset.fieldRef;
    var part      = chip.dataset.part;
    var val       = chip.dataset.value;
    var label     = chip.dataset.label;

    if (!fieldName) return;

    /* Actualizar input oculto */
    var hidden = document.getElementById('fp-sd-' + fieldName + '-' + part + '-val');
    if (hidden) hidden.value = val;

    /* Actualizar etiqueta del trigger (el container sigue en el form) */
    var labelEl = document.getElementById('fp-sd-' + fieldName + '-' + part + '-lbl');
    if (labelEl) labelEl.textContent = label;

    /* Resaltar chip seleccionado */
    panelEl.querySelectorAll('.fp-sd-chip').forEach(function (c) {
      c.classList.toggle('fp-sd-chip--sel', c.dataset.value === val);
    });

    /* Actualizar estado del trigger */
    var container = document.querySelector('.fp-split-date[data-field="' + fieldName + '"]');
    if (container) {
      container.querySelectorAll('.fp-sd-trigger[data-part="' + part + '"]').forEach(function (t) {
        t.setAttribute('aria-expanded', 'false');
        t.classList.remove('fp-sd-trigger--open');
      });
    }

    panelEl.hidden = true;
  });

  /**
   * Calcula left/top del panel con position:fixed.
   * Centrado horizontal respecto al campo, inteligente arriba/abajo.
   */
  function positionPanel(container, panel, part) {
    var pw   = PANEL_W[part] || 320;
    var rect = container.getBoundingClientRect();
    var vw   = window.innerWidth;
    var vh   = window.innerHeight;
    var ph   = panel.offsetHeight;

    /* Ancho */
    panel.style.width = pw + 'px';

    /* Horizontal: centrado sobre el campo, clampeado a viewport */
    var left = rect.left + (rect.width / 2) - (pw / 2);
    left = Math.max(8, Math.min(left, vw - pw - 8));
    panel.style.left = left + 'px';

    /* Vertical: debajo si cabe, arriba si no */
    var spaceBelow = vh - rect.bottom - 8;
    if (spaceBelow >= ph + 6 || spaceBelow > vh / 2) {
      panel.style.top    = (rect.bottom + 6) + 'px';
    } else {
      panel.style.top    = Math.max(8, rect.top - ph - 6) + 'px';
    }
  }

  function closeAllPanels() {
    document.querySelectorAll('.fp-sd-panel').forEach(function (p) {
      p.hidden = true;
    });
    document.querySelectorAll('.fp-sd-trigger').forEach(function (t) {
      t.setAttribute('aria-expanded', 'false');
      t.classList.remove('fp-sd-trigger--open');
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAll);
  } else {
    initAll();
  }
})();
