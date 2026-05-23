import { SC_COLORS } from '../core/constants.js?v=99';
import { UI_STATE } from '../core/state.js?v=99';
import { MD_TOP } from '../charts/plugins.js?v=99';

// FIX: Aligned perfectly with your CSV headers
const SVCS = ['Metrics','Preflight','Tests','Docs','Dashboard','Config','Scripts','Proxy','Critical'];
const SVC_KEYS = ['touches_metrics','touches_preflight','touches_tests','touches_docs','touches_dashboard','touches_config','touches_scripts','touches_proxy','touches_critical'];

export function renderHeatmap(commits) {
    const svgEl = document.getElementById('cm-heat-svg');
    const container = document.getElementById('cm-heat-body');
    if (!svgEl || !container || !commits.length) return;
    while(svgEl.firstChild) svgEl.removeChild(svgEl.firstChild);
    
    const W = container.clientWidth || 600, H = container.clientHeight || 200;
    if (W === 0) return;
    
    const isLin = UI_STATE.heat;
    const PAD_L = 62, PAD_R = 20, PAD_T = isLin ? MD_TOP : 0, PAD_B = 16;
    const plotW = W - PAD_L - PAD_R, plotH = H - PAD_T - PAD_B, rowH = plotH / SVCS.length;

    let xPos = [];
    if (isLin) {
        const t0 = commits[0].ts, tN = commits[commits.length-1].ts;
        const pad = (tN === t0) ? 86400 : (tN - t0) * 0.05; 
        xPos = commits.map(c => PAD_L + ((c.ts - (t0 - pad)) / ((tN + pad) - (t0 - pad))) * plotW);
    } else {
        const step = plotW / commits.length; xPos = commits.map((_, i) => PAD_L + (i * step) + (step / 2));
    }

    const colW = isLin ? 6 : Math.max(2, (plotW / commits.length) - 1.5);
    const ns = 'http://www.w3.org/2000/svg';
    svgEl.setAttribute('viewBox', `0 0 ${W} ${H}`); svgEl.setAttribute('preserveAspectRatio', 'none');

    SVCS.forEach((lbl, row) => {
        const t = document.createElementNS(ns, 'text');
        t.setAttribute('x', PAD_L - 6); t.setAttribute('y', PAD_T + row * rowH + rowH / 2 + 3.5);
        t.setAttribute('text-anchor', 'end'); t.setAttribute('font-family', 'Satoshi, sans-serif'); t.setAttribute('font-size', '9.5'); t.setAttribute('fill', '#7a7874'); t.textContent = lbl;
        svgEl.appendChild(t);
    });

    commits.forEach((c, col) => {
        SVCS.forEach((svc, row) => {
            // Because the keys now match the CSV, this hit check will pass!
            const hit = c[SVC_KEYS[row]] === true || c[SVC_KEYS[row]] === "True";
            const rect = document.createElementNS(ns, 'rect');
            rect.setAttribute('x', xPos[col] - (colW / 2)); rect.setAttribute('y', PAD_T + row * rowH + 1);
            rect.setAttribute('width', colW); rect.setAttribute('height', rowH - 2); rect.setAttribute('rx', 2);
            rect.setAttribute('fill', hit ? SC_COLORS[SVC_KEYS[row]] || '#4f98a3' : 'rgba(255,255,255,.04)'); rect.setAttribute('opacity', hit ? '0.85' : '1');
            svgEl.appendChild(rect);
        });
    });
}
