/**
 * app.js — FinanGest
 * CRM.currency, CRM.parseMoney, CRM.parseDecimal, CRM.printSection
 * + Selector de cliente dinámico + Panel de pendientes
 */
window.CRM = (function () {

    function currency(v) {
        const n = Math.round(parseFloat(v) || 0);
        return 'Gs. ' + n.toString().replace(/\B(?=(\d{3})+(?!\d))/g, '.');
    }

    function parseMoney(v) {
        if (!v && v !== 0) return 0;
        return parseFloat(String(v).replace(/\./g, '').replace(',', '.')) || 0;
    }

    function parseDecimal(v) {
        if (!v && v !== 0) return 0;
        return parseFloat(String(v).replace(',', '.').replace('%', '').trim()) || 0;
    }

    function printSection(sectionId, titulo) {
        const el = document.getElementById(sectionId);
        if (!el) { window.print(); return; }
        const orig = document.body.innerHTML;
        document.body.innerHTML = '<div style="padding:24px;font-family:Inter,system-ui,sans-serif">' + el.innerHTML + '</div>';
        window.print();
        document.body.innerHTML = orig;
        window.location.reload();
    }

    // ── money-input via data-money="true" ──────────────────
    function initMoneyInputs() {
        document.querySelectorAll('[data-money="true"]').forEach(function (inp) {
            if (inp._moneyInited) return;
            inp._moneyInited = true;

            function fmt(v) {
                const n = parseInt(String(v).replace(/[^\d]/g, ''), 10) || 0;
                return n ? n.toString().replace(/\B(?=(\d{3})+(?!\d))/g, '.') : '';
            }

            const initial = parseInt(String(inp.value || inp.dataset.initial || '').replace(/[^\d]/g,''), 10) || 0;
            if (initial) { inp.dataset.raw = initial; inp.value = fmt(initial); }

            inp.addEventListener('input', function () {
                if (inp._upd) return;
                inp._upd = true;
                const pos = inp.selectionStart, before = inp.value.length;
                const raw = parseInt(inp.value.replace(/[^\d]/g, ''), 10) || 0;
                inp.dataset.raw = raw || '';
                inp.value = raw ? fmt(raw) : '';
                const after = inp.value.length;
                try { inp.setSelectionRange(Math.max(0, pos + after - before), Math.max(0, pos + after - before)); } catch(e){}
                inp._upd = false;
                inp.dispatchEvent(new Event('money-change', { bubbles: true }));
            });
        });

        // Hook forms: clean before submit
        document.querySelectorAll('form').forEach(function(form) {
            if (form._moneyHooked) return;
            form._moneyHooked = true;
            form.addEventListener('submit', function() {
                form.querySelectorAll('[data-money="true"]').forEach(function(inp) {
                    inp.value = inp.dataset.raw || String(inp.value).replace(/\./g, '') || '0';
                });
            }, true);
        });
    }

    // ── Cliente selector dinámico ───────────────────────────
    function norm(v) {
        return String(v || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').trim();
    }

    function initClienteSelector() {
        const inp = document.querySelector('[data-client-input="true"]');
        if (!inp) return;

        // clientesData contiene array de nombres ["Juan Perez", ...]
        const rawEl = document.getElementById('clientesData');
        let clienteNombres = [];
        try { clienteNombres = JSON.parse(rawEl ? rawEl.textContent || '[]' : '[]'); } catch(e) {}

        // pendientesData contiene array de operaciones pendientes
        const pendRawEl = document.getElementById('pendientesData');
        let pendientesTodos = [];
        try { pendientesTodos = JSON.parse(pendRawEl ? pendRawEl.textContent || '[]' : '[]'); } catch(e) {
            console.warn('pendientesData parse error:', e);
        }

        // Panel elementos
        const riskBox    = document.querySelector('[data-client-risk]');
        const riskTotal  = document.querySelector('[data-risk-total]');
        const riskPaid   = document.querySelector('[data-risk-paid]');
        const riskMargin = document.querySelector('[data-risk-margin]');
        const riskStatus = document.querySelector('[data-risk-status]');
        const pendCount  = document.querySelector('[data-pending-count]');
        const pendHelp   = document.querySelector('[data-pending-help]');
        const pendTable  = document.querySelector('[data-pending-table]');
        const pendBody   = document.querySelector('[data-pendientes-body]');
        const opSelect   = document.querySelector('[data-operacion-pendiente]') ||
                           document.getElementById('operacionPendiente');

        function actualizarPanel(texto) {
            const q = norm(texto);
            if (!q || q.length < 2) {
                if (riskBox) riskBox.classList.add('d-none');
                if (pendTable) pendTable.classList.add('d-none');
                if (pendHelp) pendHelp.classList.remove('d-none');
                if (pendCount) pendCount.textContent = '0 pendientes';
                if (opSelect) { opSelect.disabled = true; opSelect.innerHTML = '<option value="">Primero busque un cliente</option>'; }
                return;
            }

            // Encontrar cliente que coincida
            const nombreCliente = clienteNombres.find(n => norm(n) === q)
                || clienteNombres.find(n => norm(n).includes(q));

            // Filtrar pendientes por cliente
            const pends = pendientesTodos.filter(function(p) {
                const nc = norm(p.cliente || '');
                if (!nombreCliente) return nc.includes(q);
                return nc === norm(nombreCliente) || nc.includes(norm(nombreCliente));
            });

            if (pendCount) pendCount.textContent = pends.length + ' pendientes';

            if (riskBox) {
                riskBox.classList.remove('d-none');
                const totalRiesgo = pends.reduce(function(a, p) { return a + (p.saldo || 0); }, 0);
                const totalPagado = pends.reduce(function(a, p) { return a + (p.pagado || 0); }, 0);
                if (riskTotal)  riskTotal.textContent  = currency(totalRiesgo);
                if (riskPaid)   riskPaid.textContent   = currency(totalPagado);
                if (riskMargin) riskMargin.textContent = '—';
                if (riskStatus) {
                    riskStatus.textContent = pends.length === 0 ? 'Sin deudas activas ✓' : pends.length + ' operación(es) activa(s)';
                    riskStatus.style.color = pends.length === 0 ? '#22c55e' : '#f59e0b';
                }
            }

            if (pends.length > 0) {
                if (pendHelp)  pendHelp.classList.add('d-none');
                if (pendTable) pendTable.classList.remove('d-none');
                if (pendBody) {
                    pendBody.innerHTML = pends.map(function(p) {
                        return '<tr>' +
                            '<td><span class="badge-soft-primary">' + (p.tipo_label || p.tipo) + '</span></td>' +
                            '<td>' + (p.descripcion || '—') + '</td>' +
                            '<td class="fw-bold">' + (p.saldo_fmt || currency(p.saldo)) + '</td>' +
                            '<td>' + (p.pagado_fmt || currency(p.pagado)) + '</td>' +
                            '<td>' + (p.fecha || '—') + '</td>' +
                            '<td>' + (p.vencimiento || '—') + '</td>' +
                            '</tr>';
                    }).join('');
                }

                // Select de operaciones para refinanciaciones
                if (opSelect) {
                    opSelect.disabled = false;
                    const totalDeuda = Math.round(pends.reduce(function(a, p) { return a + (p.saldo || 0); }, 0));
                    // Opción "Toda la deuda" solo aparece si hay más de 1 operación
                    const todaOpt = pends.length > 1
                        ? '<option value="__TODA__" data-saldo="' + totalDeuda + '">' +
                          '★ Toda la deuda — ' + currency(totalDeuda) + ' (' + pends.length + ' operaciones)' +
                          '</option>'
                        : '';
                    opSelect.innerHTML = '<option value="">Seleccione operación a refinanciar</option>' +
                        todaOpt +
                        pends.map(function(p) {
                            return '<option value="' + p.id + '" data-saldo="' + Math.round(p.saldo || 0) + '">' +
                                (p.tipo_label || p.tipo) + ' · ' + (p.descripcion || '') +
                                ' · Saldo: ' + (p.saldo_fmt || currency(p.saldo)) + '</option>';
                        }).join('');

                    opSelect.onchange = function() {
                        const deudaInput = document.getElementById('deudaActual');
                        const deudaHelp  = document.getElementById('deudaHelp');
                        if (!deudaInput) return;
                        const selVal  = opSelect.value;
                        const selOpt  = opSelect.options[opSelect.selectedIndex];
                        const saldo   = parseInt((selOpt && selOpt.dataset.saldo) || 0, 10);

                        if (selVal === '__TODA__') {
                            // Refinanciar toda la deuda acumulada
                            deudaInput.dataset.raw = totalDeuda;
                            deudaInput.value = totalDeuda.toString().replace(/\B(?=(\d{3})+(?!\d))/g, '.');
                            deudaInput.removeAttribute('readonly');
                            if (deudaHelp) deudaHelp.style.display = '';
                        } else if (selVal && saldo > 0) {
                            const op = pends.find(function(p) { return p.id === selVal; });
                            const n = Math.round(op ? op.saldo : saldo);
                            deudaInput.dataset.raw = n;
                            deudaInput.value = n.toString().replace(/\B(?=(\d{3})+(?!\d))/g, '.');
                            deudaInput.removeAttribute('readonly');
                            if (deudaHelp) deudaHelp.style.display = '';
                        } else {
                            deudaInput.dataset.raw = '';
                            deudaInput.value = '';
                            deudaInput.setAttribute('readonly', 'readonly');
                            if (deudaHelp) deudaHelp.style.display = 'none';
                        }
                        deudaInput.dispatchEvent(new Event('input'));
                        deudaInput.dispatchEvent(new Event('money-change', { bubbles: true }));
                        document.dispatchEvent(new Event('crm:pending-operation-change'));
                    };
                }
            } else {
                if (pendHelp)  pendHelp.classList.remove('d-none');
                if (pendTable) pendTable.classList.add('d-none');
                if (opSelect) { opSelect.disabled = true; opSelect.innerHTML = '<option value="">Sin operaciones pendientes para este cliente</option>'; }
            }
        }

        let debounceTimer;
        inp.addEventListener('input', function() {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(function() { actualizarPanel(inp.value); }, 200);
        });
        inp.addEventListener('change', function() { actualizarPanel(inp.value); });
    }

    // ── Init ────────────────────────────────────────────────
    function init() {
        initMoneyInputs();
        initClienteSelector();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    return { currency, parseMoney, parseDecimal, printSection };
})();
