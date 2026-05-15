// pretext-powered table renderer. Expects window.__ROWS and window.__DETAIL
// to be set before this module is loaded.

const FONT = '15px Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", "Noto Sans SC", sans-serif';

function esc(text) {
    const el = document.createElement('span');
    el.textContent = String(text);
    return el.innerHTML;
}

function truncIdx(mod, text, font, maxW) {
    const { prepare, layout } = mod;
    let lo = 0;
    let hi = text.length;
    while (lo < hi) {
        const mid = Math.ceil((lo + hi) / 2);
        const p = prepare(text.substring(0, mid), font);
        const h = layout(p, maxW, 23).height;
        if (h <= 23) lo = mid;
        else hi = mid - 1;
    }
    return lo;
}

function fallback(root) {
    if (!root) return;
    const ROWS = window.__ROWS || [];
    const DETAIL = window.__DETAIL || {};
    let h = '<table class="pt-t"><thead><tr>'
        + '<th class="pt-c1">#</th><th>内容</th>'
        + '<th class="pt-c3">类型</th><th class="pt-c4">层级</th>'
        + '<th class="pt-c5">序数</th></tr></thead><tbody>';
    for (const r of ROWS) {
        const fl = String(r[1]).split('\n')[0] || '';
        h += '<tr data-seq="' + esc(String(r[0])) + '">'
            + '<td class="pt-c1">' + esc(r[0]) + '</td>'
            + '<td>' + esc(fl) + '</td>'
            + '<td class="pt-c3">' + esc(r[2]) + '</td>'
            + '<td class="pt-c4">' + esc(r[3]) + '</td>'
            + '<td class="pt-c5">' + esc(r[4]) + '</td>'
            + '</tr>';
    }
    h += '</tbody></table>';
    root.innerHTML = h;
}

async function render(mod) {
    const ROWS = window.__ROWS || [];
    const DETAIL = window.__DETAIL || {};
    const root = document.getElementById('pt-root');
    if (!root) return;

    const cw = root.clientWidth - 44 - 72 - 56 - 88 - 24;
    if (!mod || cw < 80) {
        fallback(root);
        return;
    }

    const { prepare, layout } = mod;

    // Pre-measure all fragment texts via canvas
    const pp = [];
    for (let i = 0; i < ROWS.length; i++) {
        pp.push({ i, prep: prepare(String(ROWS[i][1]), FONT) });
    }

    // Render table
    let h = '<table class="pt-t"><thead><tr>'
        + '<th class="pt-c1">#</th><th>内容</th>'
        + '<th class="pt-c3">类型</th><th class="pt-c4">层级</th>'
        + '<th class="pt-c5">序数</th></tr></thead><tbody>';

    for (let i = 0; i < ROWS.length; i++) {
        const r = ROWS[i];
        const pm = pp[i];
        const lr = layout(pm.prep, cw, 23);
        let display;
        if (lr.lineCount <= 1 && lr.height <= 23) {
            display = r[1];
        } else {
            const firstLine = String(r[1]).split('\n')[0];
            const idx = truncIdx(mod, firstLine, FONT, cw);
            display = firstLine.substring(0, idx) + '…';  // ellipsis
        }
        h += '<tr data-seq="' + esc(String(r[0])) + '">'
            + '<td class="pt-c1">' + esc(r[0]) + '</td>'
            + '<td>' + esc(display) + '</td>'
            + '<td class="pt-c3">' + esc(r[2]) + '</td>'
            + '<td class="pt-c4">' + esc(r[3]) + '</td>'
            + '<td class="pt-c5">' + esc(r[4]) + '</td>'
            + '</tr>';
    }
    h += '</tbody></table>';
    root.innerHTML = h;

    // Click → detail dialog
    root.querySelector('tbody').addEventListener('click', function (ev) {
        const tr = ev.target.closest('tr');
        if (!tr) return;
        const d = DETAIL[tr.dataset.seq];
        if (d) window.__pd = d;
    });
}

// Main: try to import pretext, fall back to CSS-only table
import('/static/pretext-layout.js')
    .then(mod => render(mod))
    .catch(e => {
        console.warn('pretext load failed, using fallback', e);
        fallback(document.getElementById('pt-root'));
    });
