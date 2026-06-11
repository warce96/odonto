// ── money_input.js — Formato automático de montos con puntos ──────────────
// Clase: money-input  → <input class="form-control money-input" type="text" ...>
// Lee el valor numérico de: input.dataset.raw
// Dispara: evento 'money-change' Y 'input' estándar al cambiar

(function () {
    function parseRaw(v) {
        if (!v) return 0;
        return parseInt(v.toString().replace(/[^\d]/g, ''), 10) || 0;
    }

    function formatGS(n) {
        if (!n) return '';
        return Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, '.');
    }

    function attachMoneyInput(input) {
        const initial = parseRaw(input.value || input.dataset.initial || '');
        input.dataset.raw = initial || '';
        if (initial) input.value = formatGS(initial);

        input.addEventListener('input', function (e) {
            // Evitar loop: si ya estamos actualizando, salir
            if (input._updating) return;
            input._updating = true;

            const pos    = this.selectionStart;
            const before = this.value.length;
            const digits = this.value.replace(/[^\d]/g, '');
            const raw    = parseInt(digits, 10) || 0;
            const formatted = raw ? formatGS(raw) : '';

            this.dataset.raw = raw || '';
            this.value = formatted;

            // Reposicionar cursor
            const after  = this.value.length;
            const newPos = Math.max(0, pos + (after - before));
            try { this.setSelectionRange(newPos, newPos); } catch(_) {}

            input._updating = false;

            // Notificar listeners del cuotero (tanto money-change como input nativo)
            this.dispatchEvent(new Event('money-change', { bubbles: true }));
            // NO redisparar 'input' aquí para no hacer loop — los listeners
            // de calcular() ya escuchan 'money-change'
        });
    }

    function hookForms() {
        document.querySelectorAll('form').forEach(function (form) {
            form.addEventListener('submit', function () {
                form.querySelectorAll('.money-input').forEach(function (inp) {
                    const raw = inp.dataset.raw || parseRaw(inp.value);
                    inp.value = raw || '0';
                });
            }, true); // capture phase para que sea antes de validación HTML
        });
    }

    function initAll() {
        document.querySelectorAll('.money-input').forEach(attachMoneyInput);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () {
            initAll();
            hookForms();
        });
    } else {
        initAll();
        hookForms();
    }
})();
