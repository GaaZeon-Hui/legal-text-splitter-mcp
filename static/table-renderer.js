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
    let h = '<table class="pt-t"><colgroup>'
        + '<col style="width:48px"><col><col style="width:80px">'
        + '<col style="width:48px"><col style="width:80px">'
        + '</colgroup><thead><tr>'
        + '<th class="pt-c1">#</th><th class="pt-c2">内容</th>'
        + '<th class="pt-c3">类型</th><th class="pt-c4">层级</th>'
        + '<th class="pt-c5">序数</th></tr></thead><tbody>';
    for (const r of ROWS) {
        const fl = String(r[1]).split('\n')[0] || '';
        h += '<tr data-seq="' + esc(String(r[0])) + '">'
            + '<td class="pt-c1">' + esc(r[0]) + '</td>'
            + '<td class="pt-c2">' + esc(fl) + '</td>'
            + '<td class="pt-c3">' + esc(r[2]) + '</td>'
            + '<td class="pt-c4">' + esc(r[3]) + '</td>'
            + '<td class="pt-c5">' + esc(r[4]) + '</td>'
            + '</tr>';
    }
    h += '</tbody></table>';
    root.innerHTML = h;
    attachClick(root);
}

async function render(mod) {
    const ROWS = window.__ROWS || [];
    const DETAIL = window.__DETAIL || {};
    const root = document.getElementById('pt-root');
    if (!root) return;

    if (!mod) { fallback(root); return; }

    const { prepare, layout } = mod;
    // Measure fixed-column max widths + content width available
    const totalW = root.clientWidth - 24;
    const colW = _measureFixedCols(mod, ROWS);
    const cw = totalW - colW.seq - colW.type - colW.level - colW.ordinal;
    if (cw < 80) { fallback(root); return; }

    // Pre-measure all fragment texts via canvas for content column
    const pp = [];
    for (let i = 0; i < ROWS.length; i++) {
        pp.push({ i, prep: prepare(String(ROWS[i][1]), FONT) });
    }

    let h = '<table class="pt-t"><colgroup>'
        + '<col style="width:' + colW.seq + 'px">'
        + '<col style="width:' + cw + 'px">'
        + '<col style="width:' + colW.type + 'px">'
        + '<col style="width:' + colW.level + 'px">'
        + '<col style="width:' + colW.ordinal + 'px">'
        + '</colgroup><thead><tr>'
        + '<th class="pt-c1">#</th><th class="pt-c2">内容</th>'
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
            display = firstLine.substring(0, idx) + '…';
        }
        h += '<tr data-seq="' + esc(String(r[0])) + '">'
            + '<td class="pt-c1">' + esc(r[0]) + '</td>'
            + '<td class="pt-c2">' + esc(display) + '</td>'
            + '<td class="pt-c3">' + esc(r[2]) + '</td>'
            + '<td class="pt-c4">' + esc(r[3]) + '</td>'
            + '<td class="pt-c5">' + esc(r[4]) + '</td>'
            + '</tr>';
    }
    h += '</tbody></table>';
    root.innerHTML = h;
    attachClick(root);
}

// Measure fixed column widths based on max content pixel width + padding
function _measureFixedCols(mod, ROWS) {
    const { prepare, layout } = mod;
    const F = FONT;
    const pad = 28; // 12px padding each side + 2px border

    function maxPx(colIdx) {
        let maxW = 0;
        for (const r of ROWS) {
            const t = String(r[colIdx] != null ? r[colIdx] : '');
            const p = prepare(t, F);
            const lr = layout(p, 400, 23);
            // measureLineStats gives maxLineWidth
            const { maxLineWidth } = mod.measureLineStats(p, 400);
            if (maxLineWidth > maxW) maxW = maxLineWidth;
        }
        return Math.ceil(maxW + pad);
    }

    // Also measure header widths
    function headerPx(text) {
        const p = prepare(text, F);
        const lr = layout(p, 400, 23);
        const { maxLineWidth } = mod.measureLineStats(p, 400);
        return Math.ceil(maxLineWidth + pad);
    }

    return {
        seq: Math.max(maxPx(0), headerPx('序号'), 44),
        type: Math.max(maxPx(2), headerPx('类型'), 56),
        level: Math.max(maxPx(3), headerPx('层级'), 44),
        ordinal: Math.max(maxPx(4), headerPx('序数'), 56),
    };
}

function attachClick(root) {
    root.querySelector('tbody').addEventListener('click', function (ev) {
        const tr = ev.target.closest('tr');
        if (!tr) return;
        const d = (window.__DETAIL || {})[tr.dataset.seq];
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
