/* ═══════════════════════════════════════════════════════════════════
   fp_product_images.js — Galería visual de imágenes de producto
   FP Dark Neon Admin · Franja Pixelada
   ═══════════════════════════════════════════════════════════════════ */
(function () {
    'use strict';

    /* ── Constantes ──────────────────────────────────────────────── */
    /* El FK ProductImage.product tiene related_name='images',
       por lo que Django genera prefix='images' → group id='images-group' */
    var PREFIX   = 'images';
    var GROUP_ID = PREFIX + '-group';  /* 'images-group' */

    /* ══════════════════════════════════════════════════════════════
       PUNTO DE ENTRADA
       ══════════════════════════════════════════════════════════════ */
    function init() {
        if (!document.querySelector('#content-main form')) return;
        if (document.getElementById('result_list'))       return;

        var group = locateGroup();
        if (!group) return;

        /* Revelar si Jazzmin lo ocultó dentro de un tab-pane */
        revealAncestors(group);

        buildGallery(group);
        installPageDropzone(group);
    }

    /* Localiza el inline-group de imágenes */
    function locateGroup() {
        var g = document.getElementById(GROUP_ID);
        if (g) return g;
        /* Fallback: buscar cualquier inline-group cuyo ID contenga 'image' */
        var all = document.querySelectorAll('.inline-group[id]');
        for (var i = 0; i < all.length; i++) {
            if (all[i].id.indexOf('image') >= 0) return all[i];
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

    /* ══════════════════════════════════════════════════════════════
       CONSTRUCCIÓN PRINCIPAL
       ══════════════════════════════════════════════════════════════ */
    function buildGallery(group) {
        /* Idempotencia */
        if (group.querySelector('#fp-gallery')) return;

        var table = group.querySelector('table');
        if (!table) return;

        /* Ocultar tabla (incluye tr.add-row y el template row) */
        table.style.display = 'none';

        /* ── Wrapper principal ── */
        var wrap = document.createElement('div');
        wrap.id = 'fp-gallery';

        /* ── Zona de drop global (página entera) ── */
        var dropBanner = document.createElement('div');
        dropBanner.id = 'fp-gallery-drop-banner';
        dropBanner.innerHTML =
            '<div class="fp-gallery-drop-inner">' +
                '<span class="fp-gallery-drop-icon">📂</span>' +
                '<p>Suelta aquí para agregar imágenes</p>' +
            '</div>';
        document.body.appendChild(dropBanner);

        /* ── Header ── */
        var header = document.createElement('div');
        header.className = 'fp-gallery-header';
        header.innerHTML =
            '<div class="fp-gallery-meta">' +
                '<span class="fp-gallery-title-icon">🖼</span>' +
                '<span class="fp-gallery-title-text">Galería de imágenes</span>' +
                '<span id="fp-gallery-count" class="fp-gallery-badge">0 fotos</span>' +
            '</div>' +
            '<div class="fp-gallery-actions">' +
                '<span class="fp-gallery-hint">Arrastra para reordenar · Clic en zona para elegir archivo</span>' +
                '<button type="button" id="fp-gallery-add" class="fp-gallery-add-btn">' +
                    '<span>＋</span> Nueva imagen' +
                '</button>' +
            '</div>';
        wrap.appendChild(header);

        /* ── Estado vacío (se muestra cuando no hay fotos) ── */
        var empty = document.createElement('div');
        empty.id = 'fp-gallery-empty';
        empty.innerHTML =
            '<div class="fp-gallery-empty-icon">🌄</div>' +
            '<p class="fp-gallery-empty-title">Sin imágenes aún</p>' +
            '<p class="fp-gallery-empty-sub">Haz clic en <strong>Nueva imagen</strong> o arrastra archivos sobre esta zona.</p>';
        wrap.appendChild(empty);

        /* ── Grid ── */
        var grid = document.createElement('div');
        grid.id = 'fp-gallery-grid';
        wrap.appendChild(grid);

        /* Insertar en el DOM */
        table.parentNode.insertBefore(wrap, table);

        /* ── Botón añadir ── */
        document.getElementById('fp-gallery-add').addEventListener('click', function () {
            addRow(group, grid);
        });

        /* ── Procesar filas existentes ── */
        var tbody = table.querySelector('tbody');
        if (tbody) {
            tbody.querySelectorAll('tr.form-row').forEach(function (row) {
                if (isEmptyTemplateRow(row)) return;
                var card = buildCard(row, grid);
                if (card) grid.appendChild(card);
            });

            /* MutationObserver: Django añade filas dinámicamente */
            new MutationObserver(function (muts) {
                muts.forEach(function (m) {
                    m.addedNodes.forEach(function (node) {
                        if (node.nodeType !== 1) return;
                        if (isEmptyTemplateRow(node)) return;
                        if (node.classList.contains('dynamic-' + PREFIX) ||
                            node.classList.contains('form-row')) {
                            var card = buildCard(node, grid);
                            if (card) {
                                grid.appendChild(card);
                                requestAnimationFrame(function () {
                                    card.classList.add('fp-card--appear');
                                });
                                syncAll(grid);
                            }
                        }
                    });
                });
            }).observe(tbody, { childList: true });
        }

        syncAll(grid);
    }

    function isEmptyTemplateRow(row) {
        if (!row.id) return true;
        if (row.id.indexOf('__prefix__') >= 0) return true;
        if (row.id.indexOf('-empty') >= 0)     return true;
        return false;
    }

    /* ══════════════════════════════════════════════════════════════
       CONSTRUIR TARJETA DESDE <tr>
       ══════════════════════════════════════════════════════════════ */
    function buildCard(row, grid) {
        if (!row.id) return null;

        /* Campos ocultos del formulario Django */
        var fileInput  = row.querySelector('input[type="file"]');
        var altInput   = row.querySelector('input[name*="-alt_text"], td.field-alt_text input');
        var primaryChk = row.querySelector('input[name*="-is_primary"]');
        var orderInput = row.querySelector('input[name*="-order"]');
        var deleteChk  = row.querySelector('input[name*="-DELETE"]');

        /* Imagen ya guardada */
        var thumbImg = row.querySelector('td.field-thumbnail img');
        var imgSrc   = thumbImg ? thumbImg.src : null;
        if (!imgSrc) {
            var anyImg = row.querySelector('img:not(.fp-gallery-img)');
            if (anyImg && anyImg.src && anyImg.src.indexOf('data:') !== 0) imgSrc = anyImg.src;
        }

        var isPrimary = primaryChk && primaryChk.checked;

        /* ── Card ── */
        var card = mk('div', 'fp-gallery-card' + (isPrimary ? ' fp-card--primary' : ''));
        card.dataset.rowId = row.id;
        card.setAttribute('draggable', 'true');

        /* Número de orden flotante */
        var orderBadge = mk('div', 'fp-card-order-badge', '1');
        card.appendChild(orderBadge);

        /* ── Zona de imagen ── */
        var zone = mk('div', 'fp-card-zone');

        /* Imagen */
        var imgEl = mk('img', 'fp-gallery-img');
        imgEl.alt = '';
        if (imgSrc) {
            imgEl.src = imgSrc;
            card.classList.add('fp-card--has-img');
        } else {
            imgEl.style.display = 'none';
        }
        zone.appendChild(imgEl);

        /* Placeholder */
        var ph = mk('div', 'fp-card-ph' + (imgSrc ? ' fp-card-ph--hidden' : ''));
        ph.innerHTML =
            '<span class="fp-card-ph-icon">📷</span>' +
            '<span class="fp-card-ph-line1">Clic para elegir</span>' +
            '<span class="fp-card-ph-line2">o arrastra un archivo aquí</span>';
        zone.appendChild(ph);

        /* Badge PRINCIPAL */
        var primBadge = mk('div', 'fp-card-prime' + (isPrimary ? '' : ' fp-hidden'));
        primBadge.innerHTML = '⭐ Principal';
        zone.appendChild(primBadge);

        /* Barra de progreso (upload fake) */
        var progBar = mk('div', 'fp-card-prog fp-hidden');
        progBar.innerHTML = '<div class="fp-card-prog-inner"></div>';
        zone.appendChild(progBar);

        /* Overlay */
        var overlay = mk('div', 'fp-card-overlay');

        var starBtn = mk('button', 'fp-card-btn fp-card-btn--star' + (isPrimary ? ' active' : ''));
        starBtn.type    = 'button';
        starBtn.title   = 'Marcar como imagen principal';
        starBtn.innerHTML = isPrimary ? '★' : '☆';
        overlay.appendChild(starBtn);

        var delBtn = mk('button', 'fp-card-btn fp-card-btn--del');
        delBtn.type     = 'button';
        delBtn.title    = 'Eliminar imagen';
        delBtn.innerHTML = '🗑';
        overlay.appendChild(delBtn);

        zone.appendChild(overlay);

        /* Fallback si la imagen ya guardada no carga */
        if (imgSrc) {
            imgEl.onerror = function () {
                imgEl.style.display = 'none';
                ph.classList.remove('fp-card-ph--hidden');
                card.classList.remove('fp-card--has-img');
            };
        }

        /* Drag handle */
        var handle = mk('div', 'fp-card-handle', '⠿');
        handle.title = 'Arrastrar para reordenar';
        zone.appendChild(handle);

        card.appendChild(zone);

        /* ── Pie de tarjeta ── */
        var footer = mk('div', 'fp-card-footer');

        /* Info de archivo */
        var fileInfo = mk('div', 'fp-card-file-info');
        if (imgSrc) {
            var fname = imgSrc.split('/').pop().split('?')[0];
            try { fname = decodeURIComponent(fname); } catch (e) {}
            fileInfo.textContent = fname.length > 28 ? fname.substr(0, 26) + '…' : fname;
        } else {
            fileInfo.textContent = 'Sin imagen';
            fileInfo.classList.add('fp-card-file-info--empty');
        }
        footer.appendChild(fileInfo);

        /* Texto alternativo */
        var altWrap = mk('div', 'fp-card-alt-wrap');
        var altLbl  = mk('label', 'fp-card-alt-lbl', 'Alt');
        var altFld  = mk('input', 'fp-card-alt-input');
        altFld.type        = 'text';
        altFld.placeholder = 'Descripción accesible…';
        if (altInput) {
            altFld.value = altInput.value || '';
            altFld.addEventListener('input', function () { altInput.value = altFld.value; });
        }
        altWrap.appendChild(altLbl);
        altWrap.appendChild(altFld);
        footer.appendChild(altWrap);

        card.appendChild(footer);

        /* ── Ocultar file input nativo ── */
        if (fileInput) {
            fileInput.style.display = 'none';

            /* Preview al seleccionar archivo */
            fileInput.addEventListener('change', function () {
                if (fileInput.files && fileInput.files[0]) {
                    showUploadProgress(card, progBar, function () {
                        renderPreview(fileInput.files[0], card, imgEl, ph, fileInfo);
                    });
                }
            });
        }

        /* ── Eventos zona ── */
        zone.addEventListener('click', function (e) {
            if (overlay.contains(e.target) || handle.contains(e.target)) return;
            if (fileInput) fileInput.click();
        });

        zone.addEventListener('dragover', function (e) {
            if (e.dataTransfer.types.indexOf('Files') >= 0) {
                e.preventDefault();
                zone.classList.add('fp-card-zone--over');
            }
        });
        zone.addEventListener('dragleave', function () {
            zone.classList.remove('fp-card-zone--over');
        });
        zone.addEventListener('drop', function (e) {
            zone.classList.remove('fp-card-zone--over');
            if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                e.preventDefault();
                assignFile(fileInput, e.dataTransfer.files[0]);
                showUploadProgress(card, progBar, function () {
                    renderPreview(e.dataTransfer.files[0], card, imgEl, ph, fileInfo);
                });
            }
        });

        /* ── Botón estrella ── */
        starBtn.addEventListener('click', function (e) {
            e.stopPropagation();
            setPrimary(card, grid);
        });

        /* ── Botón eliminar ── */
        delBtn.addEventListener('click', function (e) {
            e.stopPropagation();
            removeCard(card, deleteChk, grid);
        });

        /* ── Drag & drop reordenamiento ── */
        bindSort(card, grid);

        return card;
    }

    /* ══════════════════════════════════════════════════════════════
       INTERACCIONES
       ══════════════════════════════════════════════════════════════ */

    /* Animación de progreso falsa (visual, no bloquea) */
    function showUploadProgress(card, progBar, cb) {
        progBar.classList.remove('fp-hidden');
        var inner = progBar.querySelector('.fp-card-prog-inner');
        if (inner) { inner.style.width = '0%'; }
        var pct = 0;
        var iv = setInterval(function () {
            pct += Math.random() * 35;
            if (pct >= 100) { pct = 100; clearInterval(iv); }
            if (inner) inner.style.width = pct + '%';
            if (pct >= 100) {
                setTimeout(function () {
                    progBar.classList.add('fp-hidden');
                    if (cb) cb();
                }, 200);
            }
        }, 60);
    }

    function renderPreview(file, card, imgEl, ph, fileInfo) {
        var reader = new FileReader();
        reader.onload = function (ev) {
            imgEl.src = ev.target.result;
            imgEl.style.display = '';
            ph.classList.add('fp-card-ph--hidden');
            card.classList.add('fp-card--has-img');
            if (fileInfo) {
                fileInfo.textContent = file.name.length > 28
                    ? file.name.substr(0, 26) + '…'
                    : file.name;
                fileInfo.classList.remove('fp-card-file-info--empty');
                /* Mostrar tamaño */
                var sizeEl = card.querySelector('.fp-card-file-size');
                if (!sizeEl) {
                    sizeEl = mk('span', 'fp-card-file-size');
                    fileInfo.parentNode.insertBefore(sizeEl, fileInfo.nextSibling);
                }
                sizeEl.textContent = formatBytes(file.size);
            }
        };
        reader.readAsDataURL(file);
    }

    function assignFile(fileInput, file) {
        if (!fileInput) return;
        try {
            var dt = new DataTransfer();
            dt.items.add(file);
            fileInput.files = dt.files;
        } catch (e) { /* Safari ignora esto; el drop ya lo tiene */ }
    }

    function formatBytes(b) {
        if (b < 1024)       return b + ' B';
        if (b < 1048576)    return (b / 1024).toFixed(1) + ' KB';
        return (b / 1048576).toFixed(1) + ' MB';
    }

    /* ── Marcar como principal ── */
    function setPrimary(activeCard, grid) {
        grid.querySelectorAll('.fp-gallery-card').forEach(function (c) {
            c.classList.remove('fp-card--primary');
            var chk = getChk(c, '-is_primary');
            if (chk) chk.checked = false;
            var btn = c.querySelector('.fp-card-btn--star');
            if (btn) { btn.innerHTML = '☆'; btn.classList.remove('active'); }
            var badge = c.querySelector('.fp-card-prime');
            if (badge) badge.classList.add('fp-hidden');
        });

        activeCard.classList.add('fp-card--primary');
        var chk = getChk(activeCard, '-is_primary');
        if (chk) chk.checked = true;
        var btn = activeCard.querySelector('.fp-card-btn--star');
        if (btn) { btn.innerHTML = '★'; btn.classList.add('active'); }
        var badge = activeCard.querySelector('.fp-card-prime');
        if (badge) badge.classList.remove('fp-hidden');
    }

    function getChk(card, suffix) {
        var row = document.getElementById(card.dataset.rowId);
        return row ? row.querySelector('input[name*="' + suffix + '"]') : null;
    }

    /* ── Eliminar tarjeta ── */
    function removeCard(card, deleteChk, grid) {
        if (deleteChk) deleteChk.checked = true;
        card.classList.add('fp-card--removing');
        setTimeout(function () {
            card.style.display = 'none';
            syncAll(grid);
        }, 350);
    }

    /* ── Añadir nueva fila ── */
    function addRow(group, grid) {
        /* Django genera: <tr class="add-row"><td><a href="#">...</a></td></tr>
           El <a> NO tiene class="add-row"; el <tr> sí. */
        var addLink = group.querySelector('tr.add-row a') ||
                      group.querySelector('.add-row a')   ||
                      group.querySelector('a.add-row');

        if (addLink) {
            addLink.click();
            /* MutationObserver detecta la nueva fila en tbody */
            return;
        }

        /* ── Fallback manual: replica lo que hace inlines.js de Django ── */
        var template   = document.getElementById(PREFIX + '-empty');
        var totalInput = document.querySelector('#id_' + PREFIX + '-TOTAL_FORMS');
        if (!template || !totalInput) return;

        var idx    = parseInt(totalInput.value, 10);
        /* Clonar y reemplazar __prefix__ por el índice real en todo el HTML */
        var tmp    = document.createElement('tbody');
        tmp.innerHTML = template.outerHTML.replace(/__prefix__/g, String(idx));
        var newRow = tmp.firstChild;

        newRow.id = PREFIX + '-' + idx;
        newRow.classList.remove('empty-form', 'empty-row');
        newRow.classList.add('form-row', 'dynamic-' + PREFIX);
        newRow.style.display = '';

        /* Insertar antes del template (igual que hace Django) */
        template.parentNode.insertBefore(newRow, template);

        /* Actualizar contador del formset */
        totalInput.value = idx + 1;
        /* MutationObserver lo detectará y llamará buildCard */
    }

    /* ── Dropzone de página entera ── */
    var pageDropActive = false;
    var pageDropTimer  = null;

    function installPageDropzone(group) {
        var banner = document.getElementById('fp-gallery-drop-banner');
        if (!banner) return;

        document.addEventListener('dragenter', function (e) {
            if (e.dataTransfer.types.indexOf('Files') < 0) return;
            clearTimeout(pageDropTimer);
            if (!pageDropActive) {
                pageDropActive = true;
                banner.classList.add('fp-drop-banner--active');
            }
        });
        document.addEventListener('dragleave', function () {
            clearTimeout(pageDropTimer);
            pageDropTimer = setTimeout(function () {
                pageDropActive = false;
                banner.classList.remove('fp-drop-banner--active');
            }, 100);
        });
        document.addEventListener('dragover', function (e) {
            if (e.dataTransfer.types.indexOf('Files') >= 0) e.preventDefault();
        });
        document.addEventListener('drop', function (e) {
            banner.classList.remove('fp-drop-banner--active');
            pageDropActive = false;
            var files = e.dataTransfer.files;
            if (!files || !files.length) return;

            /* Solo si el drop NO fue en una zona de tarjeta concreta */
            var onCard = e.target.closest('.fp-card-zone');
            if (onCard) return;

            e.preventDefault();
            var grid = document.getElementById('fp-gallery-grid');
            if (!grid) return;

            Array.prototype.forEach.call(files, function (file) {
                if (!file.type.startsWith('image/')) return;
                addRow(group, grid);
                /* Esperar a que MutationObserver cree la tarjeta */
                setTimeout(function () {
                    var cards = grid.querySelectorAll('.fp-gallery-card');
                    var last  = cards[cards.length - 1];
                    if (!last) return;
                    var rowId = last.dataset.rowId;
                    var row   = rowId ? document.getElementById(rowId) : null;
                    if (!row) return;
                    var fi = row.querySelector('input[type="file"]');
                    assignFile(fi, file);
                    var imgEl    = last.querySelector('.fp-gallery-img');
                    var ph       = last.querySelector('.fp-card-ph');
                    var fileInfo = last.querySelector('.fp-card-file-info');
                    var progBar  = last.querySelector('.fp-card-prog');
                    showUploadProgress(last, progBar, function () {
                        renderPreview(file, last, imgEl, ph, fileInfo);
                    });
                }, 250);
            });
        });
    }

    /* ══════════════════════════════════════════════════════════════
       SYNC — orden y conteo
       ══════════════════════════════════════════════════════════════ */
    function syncAll(grid) {
        if (!grid) return;
        var visible = Array.prototype.slice.call(
            grid.querySelectorAll('.fp-gallery-card')
        ).filter(function (c) {
            return c.style.display !== 'none' && !c.classList.contains('fp-card--removing');
        });

        visible.forEach(function (card, i) {
            /* Orden numérico */
            var ob = card.querySelector('.fp-card-order-badge');
            if (ob) ob.textContent = i + 1;

            /* Actualizar input de orden en el form Django */
            var row = card.dataset.rowId ? document.getElementById(card.dataset.rowId) : null;
            if (row) {
                var orderInput = row.querySelector('input[name*="-order"]');
                if (orderInput) orderInput.value = i + 1;
            }
        });

        /* Contador del header */
        var badge = document.getElementById('fp-gallery-count');
        if (badge) {
            badge.textContent = visible.length + (visible.length === 1 ? ' foto' : ' fotos');
        }

        /* Estado vacío */
        var empty = document.getElementById('fp-gallery-empty');
        if (empty) {
            empty.style.display = visible.length === 0 ? 'flex' : 'none';
        }
    }

    /* ══════════════════════════════════════════════════════════════
       DRAG & DROP — reordenamiento entre tarjetas
       ══════════════════════════════════════════════════════════════ */
    var dragSrc = null;

    function bindSort(card, grid) {
        card.addEventListener('dragstart', function (e) {
            /* No iniciar drag-sort si viene del handle o del file input */
            var handle = card.querySelector('.fp-card-handle');
            if (!handle || !handle.contains(e.target)) {
                /* Permitir drag-sort desde cualquier parte de la tarjeta */
            }
            dragSrc = card;
            card.classList.add('fp-card--dragging');
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/plain', card.dataset.rowId || '');
        });

        card.addEventListener('dragend', function () {
            card.classList.remove('fp-card--dragging');
            grid.querySelectorAll('.fp-card--drop-target').forEach(function (c) {
                c.classList.remove('fp-card--drop-target');
            });
            syncAll(grid);
            dragSrc = null;
        });

        card.addEventListener('dragover', function (e) {
            if (!dragSrc || dragSrc === card) return;
            if (e.dataTransfer.types.indexOf('Files') >= 0) return;
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
            grid.querySelectorAll('.fp-card--drop-target').forEach(function (c) {
                c.classList.remove('fp-card--drop-target');
            });
            card.classList.add('fp-card--drop-target');
        });

        card.addEventListener('dragleave', function (e) {
            if (!card.contains(e.relatedTarget)) {
                card.classList.remove('fp-card--drop-target');
            }
        });

        card.addEventListener('drop', function (e) {
            if (!dragSrc || dragSrc === card) return;
            if (e.dataTransfer.types.indexOf('Files') >= 0) return;
            e.preventDefault();
            card.classList.remove('fp-card--drop-target');

            var cards   = Array.prototype.slice.call(grid.children);
            var srcIdx  = cards.indexOf(dragSrc);
            var dstIdx  = cards.indexOf(card);
            if (srcIdx < dstIdx) grid.insertBefore(dragSrc, card.nextSibling);
            else                 grid.insertBefore(dragSrc, card);
            syncAll(grid);
        });
    }

    /* ── Utilidad — crear elemento ── */
    function mk(tag, cls, text) {
        var el = document.createElement(tag);
        if (cls)  el.className   = cls;
        if (text) el.textContent = text;
        return el;
    }

    /* ══════════════════════════════════════════════════════════════
       ARRANQUE
       ══════════════════════════════════════════════════════════════ */
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        setTimeout(init, 0);
    }

})();
