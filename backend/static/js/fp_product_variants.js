/* ═══════════════════════════════════════════════════════════════════════════
   fp_product_variants.js — Galería de tarjetas para variantes de producto
   FP Dark Neon Admin · Franja Pixelada
   ═══════════════════════════════════════════════════════════════════════════ */
(function () {
    'use strict';

    /* ── Constantes ──────────────────────────────────────────────────────── */
    /* ProductVariant.product tiene related_name='variants'
       → Django genera prefix='variants' → group id='variants-group'      */
    var PREFIX   = 'variants';
    var GROUP_ID = PREFIX + '-group';

    var TYPE_LABELS = {
        talla:  'Talla',
        color:  'Color',
        fondo:  'Fondo',
        modelo: 'Modelo',
        otro:   'Otro'
    };
    var TYPE_COLORS = {
        talla:  '#00a878',
        color:  '#2563eb',
        fondo:  '#7c3aed',
        modelo: '#d97706',
        otro:   '#6b7280'
    };

    /* ══════════════════════════════════════════════════════════════════════
       PUNTO DE ENTRADA
       ══════════════════════════════════════════════════════════════════════ */
    function init() {
        if (!document.querySelector('#content-main form')) return;
        if (document.getElementById('result_list'))        return;

        var group = locateGroup();
        if (!group) return;

        revealAncestors(group);
        buildVariantCards(group);
    }

    function locateGroup() {
        var g = document.getElementById(GROUP_ID);
        if (g) return g;
        var all = document.querySelectorAll('.inline-group[id]');
        for (var i = 0; i < all.length; i++) {
            if (all[i].id.indexOf('variant') >= 0) return all[i];
        }
        return null;
    }

    function revealAncestors(el) {
        var cur = el.parentElement;
        while (cur && cur !== document.body) {
            if (cur.classList.contains('tab-pane')) {
                cur.style.cssText += ';display:block!important;opacity:1!important;visibility:visible!important;';
            }
            cur = cur.parentElement;
        }
    }

    /* ══════════════════════════════════════════════════════════════════════
       CONSTRUCCIÓN PRINCIPAL
       ══════════════════════════════════════════════════════════════════════ */
    function buildVariantCards(group) {
        if (group.querySelector('#fp-variant-gallery')) return;

        var table = group.querySelector('table');
        if (!table) return;

        /* Ocultar tabla nativa — mantener en DOM para Django's inlines.js */
        table.style.display = 'none';

        /* Ocultar h2 nativo para evitar título duplicado */
        var h2 = group.querySelector('h2');
        if (h2) h2.style.display = 'none';

        /* ── Wrapper principal ── */
        var gallery = mk('div', '');
        gallery.id = 'fp-variant-gallery';

        /* ── Header ── */
        var header = mk('div', 'fp-variant-header');
        header.innerHTML =
            '<div class="fp-variant-header-left">' +
                '<span class="fp-variant-title-icon">\u26d3</span>' +
                '<span class="fp-variant-title-text">Variantes del producto</span>' +
                '<span id="fp-variant-count" class="fp-variant-badge">0 variantes</span>' +
            '</div>' +
            '<button type="button" id="fp-variant-add" class="fp-variant-add-btn">' +
                '<span>\uff0b</span> Nueva variante' +
            '</button>';
        gallery.appendChild(header);

        /* ── Estado vacío ── */
        var emptyEl = mk('div', '');
        emptyEl.id = 'fp-variant-empty';
        emptyEl.innerHTML =
            '<div class="fp-variant-empty-icon">\u26d3</div>' +
            '<p class="fp-variant-empty-title">Sin variantes</p>' +
            '<p class="fp-variant-empty-sub">Haz clic en <strong>Nueva variante</strong> ' +
            'para agregar tallas, colores u otros tipos.</p>';
        gallery.appendChild(emptyEl);

        /* ── Grid ── */
        var grid = mk('div', '');
        grid.id = 'fp-variant-grid';
        gallery.appendChild(grid);

        table.parentNode.insertBefore(gallery, table);

        /* ── Procesar filas existentes ── */
        var tbody = table.querySelector('tbody');
        if (tbody) {
            Array.prototype.forEach.call(
                tbody.querySelectorAll('tr.form-row'),
                function (row) {
                    if (isTemplateRow(row)) return;
                    var card = buildCard(row, grid);
                    if (card) grid.appendChild(card);
                }
            );

            /* MutationObserver: detecta filas que Django añade dinámicamente */
            new MutationObserver(function (muts) {
                muts.forEach(function (m) {
                    m.addedNodes.forEach(function (node) {
                        if (node.nodeType !== 1) return;
                        if (isTemplateRow(node))  return;
                        if (node.classList.contains('dynamic-' + PREFIX) ||
                            node.classList.contains('form-row')) {
                            var card = buildCard(node, grid);
                            if (card) {
                                grid.appendChild(card);
                                requestAnimationFrame(function () {
                                    card.classList.add('fp-variant-card--appear');
                                });
                                syncCount(grid);
                            }
                        }
                    });
                });
            }).observe(tbody, { childList: true });
        }

        document.getElementById('fp-variant-add').addEventListener('click', function () {
            addVariantRow(group);
        });

        syncCount(grid);
    }

    function isTemplateRow(row) {
        if (!row.id) return true;
        if (row.id.indexOf('__prefix__') >= 0) return true;
        if (row.id.indexOf('-empty')     >= 0) return true;
        return false;
    }

    /* ══════════════════════════════════════════════════════════════════════
       CONSTRUIR TARJETA DESDE <tr>
       ══════════════════════════════════════════════════════════════════════ */
    function buildCard(row, grid) {
        if (!row.id) return null;

        /* ── Inputs ocultos del formset Django ── */
        var typeSelect  = row.querySelector('select[name*="-variant_type"]');
        var nameInput   = row.querySelector('input[name*="-name"]');
        var skuInput    = row.querySelector('input[name*="-sku"]');
        var priceInput  = row.querySelector('input[name*="-price_adjustment"]');
        var stockInput  = row.querySelector('input[name*="-stock"]');
        var activeChk   = row.querySelector('input[name*="-is_active"]');
        var sizeInput   = row.querySelector('input[name*="-size"]');
        var colorInput  = row.querySelector('input[name*="-color"]');
        var hexInput    = row.querySelector('input[name*="-color_hex"]');
        var deleteChk   = row.querySelector('input[name*="-DELETE"]');
        var hasOriginal = row.classList.contains('has_original');

        var currentType = typeSelect ? typeSelect.value : 'otro';
        var currentName = nameInput  ? nameInput.value  : '';

        /* ── Card ── */
        var card = mk('div', 'fp-variant-card' + (hasOriginal ? '' : ' fp-variant-card--new'));
        card.dataset.rowId = row.id;

        /* ── Cabecera ── */
        var cardHeader = mk('div', 'fp-variant-card-header');

        var chip = mk('span', 'fp-variant-type-chip');
        chip.textContent      = TYPE_LABELS[currentType] || currentType;
        chip.style.background = TYPE_COLORS[currentType] || '#6b7280';
        cardHeader.appendChild(chip);

        var cardTitle = mk('span', 'fp-variant-card-title');
        cardTitle.textContent = currentName || 'Nueva variante';
        cardHeader.appendChild(cardTitle);

        var delBtn = mk('button', 'fp-variant-del-btn');
        delBtn.type      = 'button';
        delBtn.title     = 'Eliminar variante';
        delBtn.innerHTML = '\u2715';
        cardHeader.appendChild(delBtn);

        card.appendChild(cardHeader);

        /* ── Bloques ── */
        var blocks = mk('div', 'fp-variant-blocks');

        /* ─ Bloque 1: Identidad ─ */
        var blockId = mk('div', 'fp-variant-block fp-variant-block--identity');
        blockId.appendChild(mk('div', 'fp-variant-block-label', 'Identidad'));

        var typeVis = buildSelect(typeSelect);
        blockId.appendChild(buildField('Tipo', typeVis));

        var nameVis = buildInput('text', nameInput  ? nameInput.value  : '', 'Ej: Talla M \u2014 Fondo Verde\u2026');
        blockId.appendChild(buildField('Nombre', nameVis));

        var skuVis  = buildInput('text', skuInput   ? skuInput.value   : '', 'C\u00f3digo SKU\u2026');
        blockId.appendChild(buildField('SKU', skuVis));

        blocks.appendChild(blockId);

        /* ─ Bloque 2: Comercial ─ */
        var blockCom = mk('div', 'fp-variant-block fp-variant-block--commercial');
        blockCom.appendChild(mk('div', 'fp-variant-block-label', 'Comercial'));

        var priceVis = buildInput('number', priceInput ? priceInput.value : '0', '+/- COP');
        priceVis.step = 'any';
        blockCom.appendChild(buildField('Ajuste precio', priceVis));

        var stockVis = buildInput('number', stockInput ? stockInput.value : '0', 'Unidades');
        stockVis.min  = '0';
        stockVis.step = '1';
        blockCom.appendChild(buildField('Stock', stockVis));

        var isActive = activeChk ? activeChk.checked : true;
        var pill = mk('button', 'fp-active-pill ' + (isActive ? 'fp-active-pill--on' : 'fp-active-pill--off'));
        pill.type        = 'button';
        pill.textContent = isActive ? '\u25cf Activa' : '\u25cb Inactiva';
        blockCom.appendChild(buildField('Estado', pill));

        blocks.appendChild(blockCom);

        /* ─ Bloque 3: Presentación ─ */
        var blockPres = mk('div', 'fp-variant-block fp-variant-block--presentation');
        blockPres.appendChild(mk('div', 'fp-variant-block-label', 'Presentaci\u00f3n'));

        var sizeVis  = buildInput('text', sizeInput  ? sizeInput.value  : '', 'Ej: M, 42, L/XL\u2026');
        blockPres.appendChild(buildField('Talla', sizeVis));

        var colorVis = buildInput('text', colorInput ? colorInput.value : '', 'Nombre del color\u2026');
        blockPres.appendChild(buildField('Color', colorVis));

        var hexRow  = mk('div', 'fp-variant-hex-row');
        var hexVis  = buildInput('text', hexInput ? hexInput.value : '', '#RRGGBB');
        hexVis.maxLength = 7;
        var swatch  = mk('span', 'fp-color-swatch');
        if (hexInput && hexInput.value) swatch.style.background = hexInput.value;
        hexRow.appendChild(hexVis);
        hexRow.appendChild(swatch);
        blockPres.appendChild(buildField('Color hex', hexRow));

        blocks.appendChild(blockPres);
        card.appendChild(blocks);

        /* ── Errores Django ── */
        var errCells = row.querySelectorAll('.errorlist');
        if (errCells.length) {
            var errDiv = mk('div', 'fp-variant-errors');
            Array.prototype.forEach.call(errCells, function (e) {
                errDiv.appendChild(e.cloneNode(true));
            });
            card.appendChild(errDiv);
        }

        /* ══ SINCRONIZACIÓN DE INPUTS ══════════════════════════════════════ */

        typeVis.addEventListener('change', function () {
            if (typeSelect) typeSelect.value = typeVis.value;
            chip.textContent      = TYPE_LABELS[typeVis.value] || typeVis.value;
            chip.style.background = TYPE_COLORS[typeVis.value] || '#6b7280';
        });

        nameVis.addEventListener('input', function () {
            if (nameInput) nameInput.value = nameVis.value;
            cardTitle.textContent = nameVis.value || 'Nueva variante';
        });

        skuVis.addEventListener('input',   function () { if (skuInput)   skuInput.value   = skuVis.value; });
        priceVis.addEventListener('input', function () { if (priceInput) priceInput.value = priceVis.value; });
        stockVis.addEventListener('input', function () { if (stockInput) stockInput.value = stockVis.value; });

        pill.addEventListener('click', function () {
            var on = !pill.classList.contains('fp-active-pill--on');
            pill.classList.toggle('fp-active-pill--on',  on);
            pill.classList.toggle('fp-active-pill--off', !on);
            pill.textContent = on ? '\u25cf Activa' : '\u25cb Inactiva';
            if (activeChk) activeChk.checked = on;
        });

        sizeVis.addEventListener('input',  function () { if (sizeInput)  sizeInput.value  = sizeVis.value; });
        colorVis.addEventListener('input', function () { if (colorInput) colorInput.value = colorVis.value; });

        hexVis.addEventListener('input', function () {
            var v = hexVis.value.trim();
            if (hexInput) hexInput.value = v;
            swatch.style.background = (v.length >= 4) ? v : 'transparent';
        });

        /* ── Botón eliminar ── */
        delBtn.addEventListener('click', function () {
            removeCard(card, row, deleteChk, delBtn, grid);
        });

        return card;
    }

    /* ══════════════════════════════════════════════════════════════════════
       AÑADIR FILA
       ══════════════════════════════════════════════════════════════════════ */
    function addVariantRow(group) {
        /* Django's inlines.js genera: <tr class="add-row"><td><a>…</a></td></tr>
           La clase add-row está en el <tr>, no en el <a>                        */
        var addLink = group.querySelector('tr.add-row a') ||
                      group.querySelector('.add-row a')   ||
                      group.querySelector('a.add-row');

        if (addLink) {
            addLink.click();
            return;
        }

        /* Fallback manual — replica la lógica de inlines.js de Django */
        var template   = document.getElementById(PREFIX + '-empty');
        var totalInput = document.querySelector('#id_' + PREFIX + '-TOTAL_FORMS');
        if (!template || !totalInput) return;

        var idx = parseInt(totalInput.value, 10);
        var tmp = document.createElement('tbody');
        tmp.innerHTML = template.outerHTML.replace(/__prefix__/g, String(idx));
        var newRow = tmp.firstChild;

        newRow.id = PREFIX + '-' + idx;
        newRow.classList.remove('empty-form', 'empty-row');
        newRow.classList.add('form-row', 'dynamic-' + PREFIX);
        newRow.style.display = '';

        template.parentNode.insertBefore(newRow, template);
        totalInput.value = idx + 1;
        /* MutationObserver detecta el nodo nuevo y llama buildCard */
    }

    /* ══════════════════════════════════════════════════════════════════════
       ELIMINAR / RESTAURAR TARJETA
       ══════════════════════════════════════════════════════════════════════ */
    function removeCard(card, row, deleteChk, delBtn, grid) {
        if (deleteChk) {
            /* Variante guardada: marcar DELETE y mostrar estado "eliminada" */
            deleteChk.checked = true;
            card.classList.add('fp-variant-card--deleted');
            delBtn.innerHTML  = '\u21a9';
            delBtn.title      = 'Restaurar variante';
            delBtn.style.pointerEvents = 'auto';

            /* Reemplazar handler para restaurar */
            var newBtn = delBtn.cloneNode(true);
            delBtn.parentNode.replaceChild(newBtn, delBtn);
            newBtn.addEventListener('click', function () {
                deleteChk.checked = false;
                card.classList.remove('fp-variant-card--deleted');
                newBtn.innerHTML = '\u2715';
                newBtn.title     = 'Eliminar variante';
                /* Restaurar handler original */
                var restored = newBtn.cloneNode(true);
                newBtn.parentNode.replaceChild(restored, newBtn);
                restored.addEventListener('click', function () {
                    removeCard(card, row, deleteChk, restored, grid);
                });
            });
        } else {
            /* Variante nueva: eliminar via inline-deletelink de Django */
            var djangoLink = row.querySelector('.inline-deletelink');
            if (djangoLink) djangoLink.click();
            card.style.transition = 'opacity .3s, transform .3s';
            card.style.opacity    = '0';
            card.style.transform  = 'scale(0.92)';
            setTimeout(function () {
                card.style.display = 'none';
                syncCount(grid);
            }, 320);
        }
        syncCount(grid);
    }

    /* ══════════════════════════════════════════════════════════════════════
       SYNC CONTADOR
       ══════════════════════════════════════════════════════════════════════ */
    function syncCount(grid) {
        var visible = Array.prototype.slice.call(
            grid.querySelectorAll('.fp-variant-card')
        ).filter(function (c) {
            return c.style.display !== 'none' &&
                   !c.classList.contains('fp-variant-card--deleted');
        });

        var badge = document.getElementById('fp-variant-count');
        if (badge) {
            badge.textContent = visible.length + (visible.length === 1 ? ' variante' : ' variantes');
        }

        var emptyEl = document.getElementById('fp-variant-empty');
        if (emptyEl) {
            emptyEl.style.display = visible.length === 0 ? 'flex' : 'none';
        }
    }

    /* ══════════════════════════════════════════════════════════════════════
       UTILIDADES DOM
       ══════════════════════════════════════════════════════════════════════ */
    function mk(tag, cls, text) {
        var el = document.createElement(tag);
        if (cls)              el.className   = cls;
        if (text !== undefined) el.textContent = text;
        return el;
    }

    function buildInput(type, value, placeholder) {
        var inp       = mk('input', 'fp-variant-input');
        inp.type        = type;
        inp.value       = value || '';
        inp.placeholder = placeholder || '';
        return inp;
    }

    function buildSelect(original) {
        if (!original) return mk('select', 'fp-variant-input');
        var sel   = original.cloneNode(true);
        sel.className = 'fp-variant-input';
        sel.removeAttribute('id');
        sel.removeAttribute('name');
        return sel;
    }

    function buildField(labelText, inputEl) {
        var wrap = mk('div', 'fp-variant-field');
        wrap.appendChild(mk('label', 'fp-variant-field-label', labelText));
        wrap.appendChild(inputEl);
        return wrap;
    }

    /* ══════════════════════════════════════════════════════════════════════
       ARRANQUE
       ══════════════════════════════════════════════════════════════════════ */
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        setTimeout(init, 0);
    }

})();
