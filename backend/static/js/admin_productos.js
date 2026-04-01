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
                    var badge = document.getElementById('fp-tallas-total-badge');
                    if (badge) { badge.textContent = '⚠ Sin stock'; badge.style.background = '#c9a227'; }
                }
            }
        });

        /* Mostrar notificación SOLO si Django guardó exitosamente.
           Django añade el mensaje "fue cambiado exitosamente" en .success-message o
           en el bloque .messagelist li.success tras un guardado real. */
        var djangoSuccess = document.querySelector('.messagelist .success, ul.messagelist li.success');
        if (djangoSuccess) {
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
       CONVERSOR USD → COP  (inyectado en la sección de precios)
       ══════════════════════════════════════════════════════════════════════ */
    var RATE_KEY     = 'fp_usd_cop_rate';
    var RATE_TS_KEY  = 'fp_usd_cop_ts';
    var RATE_CACHE_H = 4;   // horas antes de refrescar automáticamente
    var RATE_API     = 'https://open.er-api.com/v6/latest/USD';

    function savedRate() {
        var r  = parseFloat(localStorage.getItem(RATE_KEY) || '0');
        var ts = parseInt(localStorage.getItem(RATE_TS_KEY) || '0', 10);
        return r > 0 ? { rate: r, ts: ts } : null;
    }

    function storeRate(rate) {
        localStorage.setItem(RATE_KEY,    String(rate));
        localStorage.setItem(RATE_TS_KEY, String(Date.now()));
    }

    function fmtRate(r) { return r.toLocaleString('es-CO', { maximumFractionDigits: 2 }); }
    function fmtCOP(v)  { return Math.round(v).toLocaleString('es-CO'); }
    function fmtAge(ts) {
        var m = Math.round((Date.now() - ts) / 60000);
        return m < 2 ? 'hace un momento' : m < 60 ? 'hace ' + m + ' min' : 'hace ' + Math.round(m/60) + 'h';
    }

    function initPriceConverter() {
        var priceInput = document.getElementById('id_price');
        if (!priceInput) return;

        /* Encontrar el fieldset que contiene id_price */
        var priceFieldset = priceInput.closest('fieldset') ||
                            priceInput.closest('.fp-section-content') ||
                            priceInput.parentElement;
        if (!priceFieldset) return;

        /* ── Construir la tarjeta ── */
        var card = document.createElement('div');
        card.id = 'fp-converter-card';
        card.className = 'fp-converter-card';
        card.innerHTML =
            '<div class="fp-conv-header">' +
                '<span class="fp-conv-title">// CONVERSOR USD → COP</span>' +
                '<button type="button" id="fp-conv-fetch" class="fp-conv-fetch-btn" title="Obtener tasa online">' +
                    '↻ Obtener tasa online' +
                '</button>' +
            '</div>' +
            '<div class="fp-conv-rate-info" id="fp-conv-rate-info">Cargando tasa...</div>' +
            '<div class="fp-conv-body">' +
                '<label class="fp-conv-label">Convertir monto en USD</label>' +
                '<input type="number" id="fp-conv-amount" class="fp-conv-input" min="0" step="0.01" placeholder="Ej: 25.00">' +
                '<button type="button" id="fp-conv-go" class="fp-conv-go-btn">Convertir</button>' +
                '<div class="fp-conv-result" id="fp-conv-result"></div>' +
                '<div class="fp-conv-apply" id="fp-conv-apply-btns">' +
                    '<span class="fp-conv-apply-label">Aplicar al campo:</span>' +
                    '<button type="button" class="fp-conv-apply-btn" data-field="id_price">Precio venta</button>' +
                    '<button type="button" class="fp-conv-apply-btn" data-field="id_compare_at_price">Precio anterior</button>' +
                    '<button type="button" class="fp-conv-apply-btn" data-field="id_cost_price">Costo</button>' +
                '</div>' +
            '</div>';

        priceFieldset.appendChild(card);

        /* ── Estado interno ── */
        var currentRate = 0;
        var currentCOP  = 0;

        function showRateInfo(rate, ts, fromCache) {
            currentRate = rate;
            var info = document.getElementById('fp-conv-rate-info');
            if (!info) return;
            var tag = fromCache ? '⊙ Tasa guardada' : '✓ Tasa obtenida';
            info.innerHTML =
                '<span class="fp-conv-rate-tag">' + tag + ':</span> ' +
                '<strong>1 USD = ' + fmtRate(rate) + ' COP</strong>' +
                (ts ? ' <em>(' + fmtAge(ts) + ')</em>' : '');
            info.className = 'fp-conv-rate-info fp-conv-rate-ok';
        }

        function showRateError(msg) {
            var info = document.getElementById('fp-conv-rate-info');
            if (info) {
                info.textContent = '⚠ ' + msg;
                info.className = 'fp-conv-rate-info fp-conv-rate-err';
            }
        }

        function fetchRate() {
            var btn = document.getElementById('fp-conv-fetch');
            if (btn) btn.disabled = true;
            var info = document.getElementById('fp-conv-rate-info');
            if (info) { info.textContent = 'Consultando tasa...'; info.className = 'fp-conv-rate-info'; }

            fetch(RATE_API)
                .then(function (r) {
                    if (!r.ok) throw new Error('HTTP ' + r.status);
                    return r.json();
                })
                .then(function (d) {
                    var rate = d && d.rates && d.rates.COP;
                    if (!rate || rate <= 0) throw new Error('Tasa no disponible');
                    storeRate(rate);
                    showRateInfo(rate, Date.now(), false);
                    recalc();
                })
                .catch(function (e) {
                    var cached = savedRate();
                    if (cached) {
                        showRateInfo(cached.rate, cached.ts, true);
                        recalc();
                    } else {
                        showRateError('Sin conexión y sin tasa guardada.');
                    }
                })
                .finally(function () {
                    var btn = document.getElementById('fp-conv-fetch');
                    if (btn) btn.disabled = false;
                });
        }

        function recalc() {
            var amount = parseFloat(document.getElementById('fp-conv-amount').value || '0');
            var result = document.getElementById('fp-conv-result');
            var applyDiv = document.getElementById('fp-conv-apply-btns');
            if (!result) return;
            if (!currentRate || !amount || amount <= 0) {
                result.textContent = '';
                currentCOP = 0;
                if (applyDiv) applyDiv.style.display = 'none';
                return;
            }
            currentCOP = amount * currentRate;
            result.innerHTML =
                '<span class="fp-conv-eq">' +
                    fmtRate(amount) + ' USD × ' + fmtRate(currentRate) + ' = ' +
                    '<strong>' + fmtCOP(currentCOP) + ' COP</strong>' +
                '</span>';
            if (applyDiv) applyDiv.style.display = '';
        }

        /* ── Eventos ── */
        document.getElementById('fp-conv-fetch').addEventListener('click', fetchRate);

        document.getElementById('fp-conv-go').addEventListener('click', recalc);

        document.getElementById('fp-conv-amount').addEventListener('keydown', function (e) {
            if (e.key === 'Enter') { e.preventDefault(); recalc(); }
        });

        card.addEventListener('click', function (e) {
            var btn = e.target.closest('.fp-conv-apply-btn');
            if (!btn || !currentCOP) return;
            var fieldId = btn.dataset.field;
            var field   = document.getElementById(fieldId);
            if (!field) { return; }
            field.value = Math.round(currentCOP).toFixed(2);
            field.dispatchEvent(new Event('input', { bubbles: true }));
            field.dispatchEvent(new Event('change', { bubbles: true }));
            /* Feedback visual breve */
            btn.textContent = '✓ Aplicado';
            setTimeout(function () { btn.textContent = btn.dataset.originalLabel || btn.textContent; }, 1200);
        });
        /* Guardar etiquetas originales */
        card.querySelectorAll('.fp-conv-apply-btn').forEach(function (b) {
            b.dataset.originalLabel = b.textContent;
        });

        /* ── Ocultar sección "aplicar" hasta que haya resultado ── */
        var applyDiv = document.getElementById('fp-conv-apply-btns');
        if (applyDiv) applyDiv.style.display = 'none';

        /* ── Carga inicial: usar caché si es reciente, si no, fetch ── */
        var cached = savedRate();
        if (cached) {
            var ageH = (Date.now() - cached.ts) / 3600000;
            showRateInfo(cached.rate, cached.ts, true);
            if (ageH > RATE_CACHE_H) fetchRate();   // refrescar en background si es vieja
        } else {
            fetchRate();
        }
    }

    /* ══════════════════════════════════════════════════════════════════════
       MODAL DE DETALLE DE PRODUCTO (solo lectura)
       ══════════════════════════════════════════════════════════════════════ */
    function initDetailModal() {
        if (document.getElementById('fp-dm-overlay')) return;

        var overlay = document.createElement('div');
        overlay.id = 'fp-dm-overlay';
        overlay.innerHTML =
            '<div id="fp-dm-modal" role="dialog" aria-modal="true" aria-labelledby="fp-dm-name">' +
                '<div class="fp-dm-header">' +
                    '<button type="button" id="fp-dm-close" class="fp-dm-close-x" title="Cerrar">✕</button>' +
                    '<h2 id="fp-dm-name"></h2>' +
                    '<div class="fp-dm-meta-row">' +
                        '<span id="fp-dm-sku" class="fp-dm-sku-badge"></span>' +
                        '<span id="fp-dm-status" class="fp-dm-status-badge"></span>' +
                    '</div>' +
                '</div>' +
                '<div class="fp-dm-body" id="fp-dm-body"></div>' +
                '<div class="fp-dm-footer">' +
                    '<button type="button" id="fp-dm-close-footer" class="fp-dm-footer-close">Cerrar</button>' +
                    '<a id="fp-dm-edit-link" href="#" class="fp-dm-edit-btn">Editar producto</a>' +
                '</div>' +
            '</div>';
        document.body.appendChild(overlay);

        function closeModal() { overlay.classList.remove('fp-dm-open'); }

        document.getElementById('fp-dm-close').addEventListener('click', closeModal);
        document.getElementById('fp-dm-close-footer').addEventListener('click', closeModal);
        overlay.addEventListener('click', function (e) { if (e.target === overlay) closeModal(); });
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && overlay.classList.contains('fp-dm-open')) closeModal();
        });

        /* Event delegation — sobrevive a PJAX */
        document.addEventListener('click', function (e) {
            var btn = e.target.closest('.fp-detail-btn');
            if (!btn) return;
            var raw = btn.dataset.product;
            if (!raw) return;
            var p;
            try { p = JSON.parse(raw); } catch (ex) { return; }
            openModal(p);
        });

        /* ── Render del modal ── */
        function openModal(p) {
            document.getElementById('fp-dm-name').textContent = p.name || '—';

            var skuEl = document.getElementById('fp-dm-sku');
            skuEl.textContent = p.sku ? 'SKU: ' + p.sku : '';
            skuEl.style.display = p.sku ? '' : 'none';

            var statusMap = {
                active:       { label: 'Activo',        cls: 'fp-dm-s--active'   },
                inactive:     { label: 'Inactivo',       cls: 'fp-dm-s--inactive' },
                out_of_stock: { label: 'Agotado',        cls: 'fp-dm-s--out'      },
                coming_soon:  { label: 'Próximamente',   cls: 'fp-dm-s--soon'     },
            };
            var st = statusMap[p.status] || { label: p.status, cls: '' };
            var statusEl = document.getElementById('fp-dm-status');
            statusEl.textContent = st.label;
            statusEl.className = 'fp-dm-status-badge ' + st.cls;

            document.getElementById('fp-dm-edit-link').href = p.edit_url || '#';

            var body = document.getElementById('fp-dm-body');
            body.innerHTML = buildBody(p);
            body.scrollTop = 0;

            overlay.classList.add('fp-dm-open');
        }

        function buildBody(p) {
            var html = '';

            /* 1. Información General */
            html += mkSection('Información General', mkGrid([
                ['Categoría',        esc(p.category || '—')],
                ['Personalización',  esc(p.personalization || '—')],
                ['Destacado',        p.is_featured ? '<span class="fp-dm-tag fp-dm-tag--yes">Sí</span>' : '<span class="fp-dm-tag fp-dm-tag--no">No</span>'],
                ['Nuevo',            p.is_new      ? '<span class="fp-dm-tag fp-dm-tag--yes">Sí</span>' : '<span class="fp-dm-tag fp-dm-tag--no">No</span>'],
                ['Actualizado',      esc(p.updated_at || '—')],
            ]));

            /* 2. Información Comercial */
            var priceRows = [['Precio de venta', '<strong class="fp-dm-price">' + fmtModalCOP(p.price) + '</strong>']];
            if (p.compare_at_price) priceRows.push(['Precio anterior', '<s class="fp-dm-price-old">' + fmtModalCOP(p.compare_at_price) + '</s>']);
            if (p.cost_price)       priceRows.push(['Costo interno',   fmtModalCOP(p.cost_price)]);
            html += mkSection('Información Comercial', mkGrid(priceRows));

            /* 3. Inventario */
            var stockBadge = p.stock === 0
                ? '<span class="fp-dm-stock fp-dm-stock--empty">Sin stock</span>'
                : '<span class="fp-dm-stock fp-dm-stock--ok">' + p.stock + ' unidades</span>';
            html += mkSection('Inventario', mkGrid([
                ['Stock actual',    stockBadge],
                ['Disponibilidad',  p.stock > 0
                    ? '<span class="fp-dm-tag fp-dm-tag--yes">Disponible</span>'
                    : '<span class="fp-dm-tag fp-dm-tag--no">No disponible</span>'],
            ]));

            /* 4. Descripción */
            if (p.description) {
                html += mkSection('Descripción',
                    '<div class="fp-dm-desc">' +
                        esc(p.description).replace(/\n/g, '<br>') +
                    '</div>'
                );
            }

            /* 5. Imágenes */
            if (p.images && p.images.length) {
                var imgs = p.images.map(function (img) {
                    return '<figure class="fp-dm-img-item">' +
                        '<img src="' + esc(img.url) + '" alt="' + esc(img.alt || '') + '" loading="lazy">' +
                        '</figure>';
                }).join('');
                html += mkSection('Imágenes (' + p.images.length + ')',
                    '<div class="fp-dm-imgs">' + imgs + '</div>'
                );
            } else {
                html += mkSection('Imágenes', '<p class="fp-dm-empty">Sin imágenes registradas.</p>');
            }

            return html;
        }

        function mkSection(title, content) {
            return '<section class="fp-dm-section">' +
                '<h3 class="fp-dm-section-title">' + esc(title) + '</h3>' +
                content +
                '</section>';
        }

        function mkGrid(rows) {
            return '<dl class="fp-dm-grid">' +
                rows.map(function (r) {
                    return '<dt>' + esc(r[0]) + '</dt><dd>' + r[1] + '</dd>';
                }).join('') +
                '</dl>';
        }

        function fmtModalCOP(val) {
            if (!val) return '—';
            var n = parseFloat(val);
            if (isNaN(n)) return String(val);
            return '$' + n.toLocaleString('es-CO', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
        }

        function esc(s) { return escText(s); }
    }

    /* Barra de acciones del changelist: franja_admin_global.js (única fuente). */

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
        if (hasProductForm) initPriceConverter();
        initDetailModal();
        if (window.FPAdminChangelist && typeof window.FPAdminChangelist.schedule === 'function') {
            window.FPAdminChangelist.schedule();
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', run);
    } else {
        run();
    }

}());
