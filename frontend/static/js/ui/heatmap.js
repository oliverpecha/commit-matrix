import { SCOPE_COLORS } from '../constants/colors.js?v=0.1.157';
import { UI_STATE } from '../core/state.js?v=0.1.157';
import { MD_TOP } from '../charts/plugins.js?v=0.1.157';

// FIX: Aligned perfectly with your CSV headers
const SVCS = ['Metrics','Preflight','Tests','Docs','Dashboard','Config','Scripts','Proxy','Critical'];
const SVC_KEYS = ['t_metrics','t_preflight','t_tests','t_docs','t_dashboard','t_config','t_scripts','t_proxy','t_core'];

let lastCommits = [];
if(!window._hmSync){ window._hmSync=true; window.addEventListener('cm-sync-heat', ()=>lastCommits.length&&renderHeatmap(lastCommits)); }
export function renderHeatmap(commits) {
    lastCommits = commits;
    const svgEl = document.getElementById('cm-heat-svg');
    const container = document.getElementById('cm-heat-body');
    if (!svgEl || !container || !commits.length) return;
    while(svgEl.firstChild) svgEl.removeChild(svgEl.firstChild);
    
    const W = container.clientWidth || 600, H = container.clientHeight || 200;
    if (W === 0) return;
    
    const isLin = UI_STATE.heat;
    const PAD_L = (window.CM_CHART_AREA && window.CM_CHART_AREA.left) || 62;
    const PAD_R = 12;
    const rightEdge = W - PAD_R;
    const PAD_T = isLin ? MD_TOP : 6;
    const PAD_B = 16;
    const plotW = rightEdge - PAD_L, plotH = H - PAD_T - PAD_B, rowH = plotH / SVCS.length;

    const colW = isLin ? 6 : Math.min(8, Math.max(2, (plotW / commits.length) - 1.5));

    let xPos = [];
    if (isLin) {
        const t0 = Math.min(...commits.map(c => c.ts));
        const tN = Math.max(...commits.map(c => c.ts));
        const pad = (tN === t0) ? 86400 : (tN - t0) * 0.05;
        xPos = commits.map(c => PAD_L + ((c.ts - (t0 - pad)) / ((tN + pad) - (t0 - pad))) * plotW);
    } else {
        const innerW = plotW - colW;
        const step = commits.length > 1 ? innerW / (commits.length - 1) : 0;
        xPos = commits.map((_, i) => PAD_L + (colW / 2) + (i * step));
    }
    const ns = 'http://www.w3.org/2000/svg';
    svgEl.setAttribute('viewBox', `0 0 ${W} ${H}`); svgEl.setAttribute('preserveAspectRatio', 'xMidYMid meet');

    const fragment = document.createDocumentFragment();

    SVCS.forEach((lbl, row) => {
        // 1. Text Label
        const t = document.createElementNS(ns, 'text');
        t.setAttribute('x', PAD_L - 6); 
        t.setAttribute('y', PAD_T + row * rowH + rowH / 2 + 3.5);
        t.setAttribute('text-anchor', 'end'); 
        t.setAttribute('font-family', 'Satoshi, sans-serif'); 
        t.setAttribute('font-size', '10'); 
        t.setAttribute('fill', '#7a7874'); 
        t.textContent = lbl;
        fragment.appendChild(t);

        // 2. Full-width faint background row (Replaces thousands of empty rects)
        const bgRect = document.createElementNS(ns, 'rect');
        bgRect.setAttribute('x', PAD_L); 
        bgRect.setAttribute('y', PAD_T + row * rowH + 1);
        bgRect.setAttribute('width', plotW); 
        bgRect.setAttribute('height', rowH - 2); 
        bgRect.setAttribute('rx', 2);
        bgRect.setAttribute('fill', 'rgba(255,255,255,.04)');
        fragment.appendChild(bgRect);
    });

    commits.forEach((c, col) => {
        let rx = xPos[col] - (colW / 2);
        rx = Math.max(PAD_L, Math.min(rx, rightEdge - colW));
        SVCS.forEach((svc, row) => {
            const hit = c[SVC_KEYS[row]] === true;
            
            // OPTIMIZATION: Only generate DOM nodes for actual data hits
            if (!hit) return; 

            const rect = document.createElementNS(ns, 'rect');
            rect.setAttribute('x', rx); 
            rect.setAttribute('y', PAD_T + row * rowH + 1);
            rect.setAttribute('width', colW); 
            rect.setAttribute('height', rowH - 2); 
            rect.setAttribute('rx', 2);
            rect.setAttribute('fill', SCOPE_COLORS[String(SVC_KEYS[row]).replace(/^t_/, '').toLowerCase()] || '#4f98a3'); 
            rect.setAttribute('opacity', '0.85');
            fragment.appendChild(rect);
        });
    });

    svgEl.appendChild(fragment);
}
