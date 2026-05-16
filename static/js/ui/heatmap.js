import { SC_COLORS } from '../core/constants.js';

const SVCS = ['Metrics','Preflight','Tests','Docs','Dashboard','Config','Scripts','Proxy','Core'];
const SVC_KEYS = ['t_metrics','t_preflight','t_tests','t_docs','t_dashboard','t_config','t_scripts','t_proxy','t_core'];

export function renderHeatmap(commits) {
    const svgEl = document.getElementById('cm-heat-svg');
    const container = document.getElementById('cm-heat-body');
    if (!svgEl || !container || !commits.length) return;
    
    while(svgEl.firstChild) svgEl.removeChild(svgEl.firstChild);

    const W = container.clientWidth || 600;
    const H = container.clientHeight || 200;
    const PAD_L = 62, PAD_R = 20, PAD_T = 0, PAD_B = 16;
    const plotW = W - PAD_L - PAD_R;
    const plotH = H - PAD_T - PAD_B;
    const rowH = plotH / SVCS.length;

    const step = plotW / commits.length;
    const xPos = commits.map((_, i) => PAD_L + (i * step) + (step / 2));
    const colW = Math.max(2, (plotW / commits.length) - 1.5);

    const ns = 'http://www.w3.org/2000/svg';
    svgEl.setAttribute('viewBox', `0 0 ${W} ${H}`);
    svgEl.setAttribute('preserveAspectRatio', 'none');

    // Draw Labels
    SVCS.forEach((lbl, row) => {
        const t = document.createElementNS(ns, 'text');
        t.setAttribute('x', PAD_L - 6); 
        t.setAttribute('y', PAD_T + row * rowH + rowH / 2 + 3.5);
        t.setAttribute('text-anchor', 'end'); 
        t.setAttribute('font-family', 'Satoshi, sans-serif'); 
        t.setAttribute('font-size', '9.5'); 
        t.setAttribute('fill', '#7a7874'); 
        t.textContent = lbl;
        svgEl.appendChild(t);
    });

    // Draw Cells
    commits.forEach((c, col) => {
        SVCS.forEach((svc, row) => {
            const hit = c[SVC_KEYS[row]] === true;
            const rect = document.createElementNS(ns, 'rect');
            rect.setAttribute('x', xPos[col] - (colW / 2));
            rect.setAttribute('y', PAD_T + row * rowH + 1);
            rect.setAttribute('width', colW);
            rect.setAttribute('height', rowH - 2);
            rect.setAttribute('rx', 2);
            rect.setAttribute('fill', hit ? SC_COLORS[SVC_KEYS[row]] : 'rgba(255,255,255,.04)');
            rect.setAttribute('opacity', hit ? '0.85' : '1');
            rect.setAttribute('class', 'bp-hm-cell');
            svgEl.appendChild(rect);
        });
    });
}
