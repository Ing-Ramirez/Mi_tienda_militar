/* Franja Pixelada — Admin: Layout plano de productos + tallas dinámicas */
(function () {
    'use strict';

    /* ── Tallas predefinidas ─────────────────────────────────────────────── */
    var TALLAS_GRUPOS = [
        { label: 'Ropa / Uniformes',          items: ['XS', 'S', 'M', 'L', 'XL', 'XXL'] },
        { label: 'Calzado',                   items: ['37', '38', '39', '40', '41', '42'] },
        { label: 'Sin talla / Talla única',   items: ['ÚNICA'] },
    ];
    var ALL_TALLAS = TALLAS_GRUPOS.reduce(function (a, g) { return a.concat(g.items); }, []);

    /* ══════════════════════════════════════════════════════════════════════
       LAYOUT PLANO VERTICAL
       ══════════════════════════════════════════════════════════════════════ */
    function initFlatLayout() {
        var form = document.querySelector('#content-main form');
        if (!form) return;

        /* Con errores: solo mostrar todo sin reorganizar */
        if (form.querySelector('.errorlist')) {
            revealAll(form);
            buildSubmitBar(form);
            return;
        }

        /* 1. Neutralizar tabs de jazzmin */
        form.querySelectorAll('.nav-tabs, .nav.nav-tabs').forEach(function (n) {
            n.style.display = 'none';
        });
        form.querySelectorAll('.card-header').forEach(function (ch) {
            if (ch.querySelector('.nav-tabs, .nav-link')) ch.style.display = 'none';
        });
        form.querySelectorAll('.tab-pane').forEach(function (tp) {
            tp.style.cssText += ';display:block!important;opacity:1!important;';
        });

        /* 2. Recolectar secciones */
        var sections = [];
        var tabContent = form.querySelector('.tab-content');
        if (tabContent) {
            tabContent.querySelectorAll('.tab-pane').forEach(function (tp) {
                var fs = tp.querySelector('fieldset');
                if (fs) {
                    var h2 = fs.querySelector('h2');
                    sections.push({ el: tp, title: h2 ? h2.textContent.trim() : '' });
                } else if (tp.children.length) {
                    sections.push({ el: tp, title: '' });
                }
            });
        }
        if (sections.length === 0) {
            form.querySelectorAll('fieldset.module').forEach(function (fs) {
                var h2 = fs.querySelector('h2');
                sections.push({ el: fs, title: h2 ? h2.textContent.trim() : '' });
            });
        }

        /* 3. Construir contenedor plano */
        var wrapper = document.createElement('div');
        wrapper.id = 'fp-flat-layout';

        sections.forEach(function (sec) {
            if (sec.title) {
                var lbl = document.createElement('div');
                lbl.className   = 'fp-section-label';
                lbl.textContent = sec.title;
                wrapper.appendChild(lbl);
            }
            var box = document.createElement('div');
            box.className = 'fp-section-content';
            box.appendChild(sec.el);
            wrapper.appendChild(box);
        });

        /* Inline groups (imágenes, variantes) */
        form.querySelectorAll('.inline-group').forEach(function (g) {
            var h = g.querySelector('h2, h3');
            if (h) {
                var lbl = document.createElement('div');
                lbl.className   = 'fp-section-label';
                lbl.textContent = h.textContent.trim();
                wrapper.appendChild(lbl);
            }
            var box = document.createElement('div');
            box.className = 'fp-section-content';
            box.appendChild(g);
            wrapper.appendChild(box);
        });

        /* 4. Insertar antes del submit row */
        var submitRow = form.querySelector('.submit-row');
        if (submitRow) {
            form.insertBefore(wrapper, submitRow);
        } else {
            var card = tabContent ? tabContent.closest('.card') : null;
            if (card) {
                card.parentNode.insertBefore(wrapper, card.nextSibling);
                card.style.display = 'none';
            } else {
                form.appendChild(wrapper);
            }
        }

        /* Ocultar la card vacía de jazzmin */
        var card = tabContent ? tabContent.closest('.card') : null;
        if (card) card.style.display = 'none';

        /* 5. UI de tallas */
        buildTallasUI();

        /* 6. Lógica dinámica requiere_talla */
        initRequiereTalla();

        /* 7. Barra de 3 botones */
        buildSubmitBar(form);

        /* 8. Aviso visual (no bloqueante) al guardar con stock 0 */
        form.addEventListener('submit', function () {
            var requiresSize = document.getElementById('id_requires_size');
            if (requiresSize && requiresSize.checked) {
                var ta = document.getElementById('id_stock_by_size');
                var data = {};
                try { data = JSON.parse((ta && ta.value) || '{}'); } catch (ex) {}
                var total = Object.keys(data).reduce(function (s, k) {
                    return s + (parseInt(data[k], 10) || 0);
                }, 0);
                if (total === 0) {
                    /* Aviso visual — el formulario SÍ se envía */
                    var badge = document.getElementById('fp-tallas-total-badge');
                    if (badge) { badge.textContent = '⚠ Sin stock'; badge.style.background = '#c9a227'; }
                }
            }
            /* El formulario siempre se envía — solo marcamos el flag aquí */
            localStorage.setItem('fp_saved', '1');
        });

        /* Mostrar notificación de guardado si viene de un save anterior */
        if (localStorage.getItem('fp_saved') === '1') {
            localStorage.removeItem('fp_saved');
            showAdminNotif('saved');
        }
    }

    function revealAll(form) {
        form.querySelectorAll('.tab-pane').forEach(function (tp) {
            tp.style.cssText += ';display:block!important;opacity:1!important;';
        });
        form.querySelectorAll('.nav-tabs, .card-header').forEach(function (el) {
            el.style.display = 'none';
        });
    }

    /* ══════════════════════════════════════════════════════════════════════
       MÓDULO DE TALLAS
       ══════════════════════════════════════════════════════════════════════ */
    function buildTallasUI() {
        var textarea = document.getElementById('id_stock_by_size');
        if (!textarea) return;

        var current = {};
        try { current = JSON.parse(textarea.value || '{}'); } catch (e) {}

        var row = textarea.closest('.form-row') ||
                  textarea.closest('.field-stock_por_talla') ||
                  textarea.parentElement;
        if (row) row.style.display = 'none';

        var ui = document.createElement('div');
        ui.id = 'fp-tallas-ui';

        ui.innerHTML =
            '<div class="fp-tallas-header">' +
                '<span class="fp-tallas-title">Tallas disponibles y stock por talla</span>' +
                '<span id="fp-tallas-total-badge" class="fp-tallas-badge">0 uds.</span>' +
            '</div>';

        var applyBar = document.createElement('div');
        applyBar.className = 'fp-apply-bar';
        applyBar.innerHTML =
            '<span class="fp-apply-label">Aplicar stock a marcadas:</span>' +
            '<input type="number" id="fp-apply-val" class="fp-apply-input" min="0" value="1">' +
            '<button type="button" id="fp-apply-all" class="fp-apply-btn">Aplicar</button>' +
            '<button type="button" id="fp-clear-all" class="fp-apply-btn fp-apply-btn-clear">Limpiar</button>';
        ui.appendChild(applyBar);

        TALLAS_GRUPOS.forEach(function (grupo) {
            var section = document.createElement('div');
            section.className = 'fp-tallas-section';
            section.innerHTML = '<div class="fp-tallas-section-label">' + grupo.label + '</div>';
            var grid = document.createElement('div');
            grid.className = 'fp-tallas-grid';

            grupo.items.forEach(function (talla) {
                var val     = current[talla] !== undefined ? parseInt(current[talla], 10) : 0;
                var checked = val > 0;
                var item    = document.createElement('div');
                item.className = 'fp-talla-item' + (checked ? ' checked' : '');
                item.innerHTML =
                    '<label class="fp-talla-row">' +
                        '<input type="checkbox" class="fp-talla-chk" data-talla="' + talla + '"' +
                            (checked ? ' checked' : '') + '>' +
                        '<span class="fp-talla-name">' + talla + '</span>' +
                    '</label>' +
                    '<input type="number" class="fp-talla-qty" data-talla="' + talla + '"' +
                        ' min="0" value="' + (val || 0) + '"' +
                        (checked ? '' : ' disabled') + '>';
                grid.appendChild(item);
            });

            section.appendChild(grid);
            ui.appendChild(section);
        });

        var totalEl = document.createElement('div');
        totalEl.id = 'fp-tallas-total';
        totalEl.className = 'fp-tallas-total';
        totalEl.textContent = 'Stock total: 0 unidades';
        ui.appendChild(totalEl);

        var parentFieldset = textarea.closest('fieldset');
        if (parentFieldset) {
            var firstRow = parentFieldset.querySelector('.form-row, p');
            parentFieldset.insertBefore(ui, firstRow || parentFieldset.firstChild);
        } else if (row && row.parentElement) {
            row.parentElement.insertBefore(ui, row.nextSibling);
        }

        ui.addEventListener('change', function (e) {
            var t = e.target;
            if (t.classList.contains('fp-talla-chk')) {
                var talla = t.dataset.talla;
                var qty   = ui.querySelector('.fp-talla-qty[data-talla="' + talla + '"]');
                var itm   = t.closest('.fp-talla-item');
                if (qty) { qty.disabled = !t.checked; if (!t.checked) qty.value = 0; }
                if (itm) itm.classList.toggle('checked', t.checked);
            }
            syncTallas();
        });

        document.getElementById('fp-apply-all').addEventListener('click', function () {
            var val = parseInt(document.getElementById('fp-apply-val').value, 10) || 0;
            ui.querySelectorAll('.fp-talla-chk:checked').forEach(function (cb) {
                var qty = ui.querySelector('.fp-talla-qty[data-talla="' + cb.dataset.talla + '"]');
                if (qty) qty.value = val;
            });
            syncTallas();
        });

        document.getElementById('fp-clear-all').addEventListener('click', function () {
            ui.querySelectorAll('.fp-talla-chk').forEach(function (cb) {
                cb.checked = false;
                var itm = cb.closest('.fp-talla-item');
                if (itm) itm.classList.remove('checked');
            });
            ui.querySelectorAll('.fp-talla-qty').forEach(function (qty) {
                qty.value = 0; qty.disabled = true;
            });
            syncTallas();
        });

        syncTallas();
    }

    function syncTallas() {
        var data = {}, total = 0;
        ALL_TALLAS.forEach(function (talla) {
            var cb  = document.querySelector('.fp-talla-chk[data-talla="' + talla + '"]');
            var qty = document.querySelector('.fp-talla-qty[data-talla="' + talla + '"]');
            if (cb && cb.checked && qty) {
                var v = Math.max(0, parseInt(qty.value, 10) || 0);
                if (v > 0) { data[talla] = v; total += v; }
            }
        });
        var ta = document.getElementById('id_stock_by_size');
        if (ta) ta.value = JSON.stringify(data);
        var sf = document.getElementById('id_stock');
        if (sf && total > 0) sf.value = total;
        var badge = document.getElementById('fp-tallas-total-badge');
        if (badge) badge.textContent = total + ' uds.';
        var totalEl = document.getElementById('fp-tallas-total');
        if (totalEl) {
            totalEl.textContent = 'Stock total calculado: ' + total + ' unidades';
            totalEl.className   = 'fp-tallas-total' + (total > 0 ? ' has-stock' : '');
        }
    }

    /* ══════════════════════════════════════════════════════════════════════
       LÓGICA DINÁMICA: REQUIERE TALLA
       ══════════════════════════════════════════════════════════════════════ */
    function initRequiereTalla() {
        var chk        = document.getElementById('id_requires_size');
        if (!chk) return;
        var stockInput = document.getElementById('id_stock');
        var stockRow   = stockInput
            ? (stockInput.closest('.form-row') || stockInput.closest('.field-stock') || stockInput.parentElement)
            : null;

        if (stockRow && !document.getElementById('fp-stock-hint')) {
            var hint = document.createElement('p');
            hint.id = 'fp-stock-hint'; hint.className = 'help'; hint.style.marginTop = '4px';
            stockRow.appendChild(hint);
        }

        function applyMode(conTalla) {
            var tallasUI = document.getElementById('fp-tallas-ui');
            if (conTalla) {
                if (tallasUI)  tallasUI.style.display = '';
                if (stockRow)  stockRow.style.display = 'none';
                if (stockInput) stockInput.value = '0';
                var hint = document.getElementById('fp-stock-hint');
                if (hint) hint.textContent = '';
            } else {
                if (tallasUI)  tallasUI.style.display = 'none';
                if (stockRow)  stockRow.style.display = '';
                var ta = document.getElementById('id_stock_by_size');
                if (ta) ta.value = '{}';
                if (stockInput) stockInput.style.borderColor = '';
            }
        }

        applyMode(chk.checked);
        chk.addEventListener('change', function () { applyMode(chk.checked); });
    }

    /* ══════════════════════════════════════════════════════════════════════
       BARRA DE 3 BOTONES
       ══════════════════════════════════════════════════════════════════════ */
    function buildSubmitBar(form) {
        if (document.getElementById('fp-submit-bar')) return;

        var bar = document.createElement('div');
        bar.id = 'fp-submit-bar';

        /* ── Guardar ── */
        var btnSave = document.createElement('button');
        btnSave.type      = 'submit';
        btnSave.name      = '_continue';
        btnSave.className = 'fp-save-btn fp-btn-save';
        btnSave.innerHTML = '✔ Guardar';
        /* localStorage se marca en el evento submit, no en click */
        bar.appendChild(btnSave);

        /* ── Nuevo producto ── */
        var btnNew = document.createElement('button');
        btnNew.type      = 'button';
        btnNew.className = 'fp-save-btn fp-btn-new';
        btnNew.innerHTML = '＋ Nuevo producto';
        btnNew.addEventListener('click', function () {
            var path    = window.location.pathname;
            var addUrl  = path.replace(/\/[^/]+\/change\/$/, '/add/');
            if (addUrl === path) addUrl = path.replace(/\/change\/$/, '') + '/add/';
            window.location.href = addUrl;
        });
        bar.appendChild(btnNew);

        /* ── Eliminar ── */
        var btnDelete = document.createElement('button');
        btnDelete.type      = 'button';
        btnDelete.className = 'fp-save-btn fp-btn-delete';
        btnDelete.innerHTML = '✕ Eliminar';
        btnDelete.addEventListener('click', function () {
            /* Ocultar si estamos en modo "add" (sin PK) */
            if (/\/add\/$/.test(window.location.pathname)) {
                showAdminNotif('no-delete');
                return;
            }
            showAdminNotif('delete');
        });
        bar.appendChild(btnDelete);

        form.appendChild(bar);
    }

    /* ══════════════════════════════════════════════════════════════════════
       NOTIFICACIONES CENTRALES
       ══════════════════════════════════════════════════════════════════════ */
    function showAdminNotif(type) {
        /* Evitar duplicados */
        var existing = document.getElementById('fp-notif-overlay');
        if (existing) existing.parentNode.removeChild(existing);

        var overlay = document.createElement('div');
        overlay.id = 'fp-notif-overlay';

        if (type === 'saved') {
            /* Confirmación de guardado — se auto-cierra */
            overlay.innerHTML =
                '<div class="fp-notif-box fp-notif-save">' +
                    '<div class="fp-notif-icon">✔</div>' +
                    '<div class="fp-notif-msg">Producto guardado</div>' +
                '</div>';
            document.body.appendChild(overlay);
            setTimeout(function () {
                if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
            }, 1800);

        } else if (type === 'delete') {
            /* Confirmación de eliminación */
            overlay.innerHTML =
                '<div class="fp-notif-box fp-notif-delete">' +
                    '<div class="fp-notif-icon">✕</div>' +
                    '<div class="fp-notif-msg">¿Eliminar este producto?</div>' +
                    '<p style="font-size:.82rem;color:#6c757d;margin:.4rem 0 0">Esta acción no se puede deshacer.</p>' +
                    '<div class="fp-notif-actions">' +
                        '<button class="fp-notif-btn fp-notif-cancel">Cancelar</button>' +
                        '<button class="fp-notif-btn fp-notif-confirm">Sí, eliminar</button>' +
                    '</div>' +
                '</div>';
            document.body.appendChild(overlay);

            overlay.querySelector('.fp-notif-cancel').addEventListener('click', function () {
                if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
            });
            overlay.querySelector('.fp-notif-confirm').addEventListener('click', function () {
                var deleteUrl = window.location.pathname.replace('/change/', '/delete/');
                window.location.href = deleteUrl;
            });

        } else if (type === 'no-delete') {
            overlay.innerHTML =
                '<div class="fp-notif-box fp-notif-save">' +
                    '<div class="fp-notif-icon" style="color:#c9a227">⚠</div>' +
                    '<div class="fp-notif-msg">Guarda el producto primero para poder eliminarlo.</div>' +
                    '<div class="fp-notif-actions">' +
                        '<button class="fp-notif-btn fp-notif-cancel">Entendido</button>' +
                    '</div>' +
                '</div>';
            document.body.appendChild(overlay);
            overlay.querySelector('.fp-notif-cancel').addEventListener('click', function () {
                if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
            });
        }

        /* Cerrar al hacer clic en el fondo */
        overlay.addEventListener('click', function (e) {
            if (e.target === overlay) {
                if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
            }
        });
    }

    /* ══════════════════════════════════════════════════════════════════════
       BARRA DE ACCIONES RÁPIDAS (página de lista)
       ══════════════════════════════════════════════════════════════════════ */
    function initActionBar() {
        var ACTION_STYLES = {
            activate_products:    'fp-btn-activate',
            deactivate_products:  'fp-btn-deactivate',
            export_inventory_csv: 'fp-btn-export',
        };
        var form   = document.getElementById('changelist-form');
        var select = form && form.querySelector('select[name="action"]');
        if (!select) return;

        var bar = document.createElement('div');
        bar.id = 'fp-action-bar';
        var lbl = document.createElement('span');
        lbl.className = 'fp-action-label'; lbl.textContent = 'Acciones:';
        bar.appendChild(lbl);

        var buttons = [];
        select.querySelectorAll('option').forEach(function (opt) {
            if (!opt.value) return;
            var btn = document.createElement('button');
            btn.type              = 'button';
            btn.textContent       = opt.textContent.trim();
            btn.dataset.actionValue = opt.value;
            btn.disabled          = true;
            btn.className         = 'fp-action-btn ' + (ACTION_STYLES[opt.value] || 'fp-btn-default');
            btn.addEventListener('click', function () {
                select.value = this.dataset.actionValue;
                var go = form.querySelector('.button[name="index"], button[name="index"], input[name="index"]');
                if (go) { go.click(); } else {
                    var h = document.createElement('input');
                    h.type = 'hidden'; h.name = 'index'; h.value = '0';
                    form.appendChild(h); form.submit();
                }
            });
            bar.appendChild(btn);
            buttons.push(btn);
        });

        var counter = document.createElement('span');
        counter.id = 'fp-selection-count';
        bar.appendChild(counter);

        var rl = document.getElementById('result_list');
        if (rl) rl.parentNode.insertBefore(bar, rl);
        else { var ab = form.querySelector('.actions'); if (ab) ab.after(bar); }

        function refresh() {
            var n = form.querySelectorAll('#result_list tbody input[type="checkbox"]:checked').length;
            buttons.forEach(function (b) { b.disabled = n === 0; });
            counter.textContent = n > 0 ? n + ' seleccionado' + (n > 1 ? 's' : '') : '';
        }
        form.addEventListener('change', function (e) { if (e.target.type === 'checkbox') refresh(); });
        refresh();
    }

    /* ── Utilidades ──────────────────────────────────────────────────────── */
    function escText(s) {
        var d = document.createElement('div');
        d.textContent = String(s || '');
        return d.innerHTML;
    }

    /* ══════════════════════════════════════════════════════════════════════
       PUNTO DE ENTRADA
       ══════════════════════════════════════════════════════════════════════ */
    function run() {
        var hasProductForm = document.getElementById('id_sku') !== null &&
                             document.getElementById('id_price') !== null;
        if (hasProductForm) initFlatLayout();
        initActionBar();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', run);
    } else {
        run();
    }

}());
