import { SCOPE_COLORS } from '../constants/colors.js?v=0.1.211';
import { UI_STATE } from '../core/state.js?v=0.1.211';
import { MD_TOP } from '../charts/plugins.js?v=0.1.211';

let lastCommits = [];
let _transBound = false;

function scheduleRender(commits) {
    requestAnimationFrame(() => {
        requestAnimationFrame(() => renderHeatmap(commits));
    });
}

if(!window._hmSync){ window._hmSync=true; window.addEventListener('cm-sync-heat', ()=>lastCommits.length&&scheduleRender(lastCommits)); }

export function renderHeatmap(commits) {
    lastCommits = commits;
    const svgEl = document.getElementById('cm-heat-svg');
    const container = document.getElementById('cm-heat-body');
    if (!svgEl || !container || !commits.length) return;

    if (!_transBound) {
        _transBound = true;
        container.addEventListener('transitionend', (e) => {
            if (e.target === container && lastCommits.length) {
                renderHeatmap(lastCommits);
            }
        });
    }
    while(svgEl.firstChild) svgEl.removeChild(svgEl.firstChild);
    
    const W = container.clientWidth || 600, H = container.clientHeight || 200;
    if (W === 0) return;
    
    // Dynamically generate axes based on present touches_* keys
    const keysSet = new Set();
    commits.forEach(c => Object.keys(c).forEach(k => { if (k.startsWith('touches_')) keysSet.add(k); }));
    const SVC_KEYS = Array.from(keysSet).sort();
    if (!SVC_KEYS.length) return;
    
    const SVCS = SVC_KEYS.map(k => k.replace('touches_', '').charAt(0).toUpperCase() + k.replace('touches_', '').slice(1));
    
    const isLin = window.CM_GLOBAL_CHRON === true || window.CM_CHRON === true || UI_STATE.timeline === true || UI_STATE.linear === true || UI_STATE.isLinear === true || (document.getElementById('cm-global-chron-btn') && (document.getElementById('cm-global-chron-btn').classList.contains('active') || document.getElementById('cm-global-chron-btn').textContent.includes('Timeline')));
    const PAD_L = 74;
    const PAD_R = 14;
    const rightEdge = W - PAD_R;
    const PAD_T = isLin ? MD_TOP : 4;
    const PAD_B = 16;
    const plotW = rightEdge - PAD_L, plotH = Math.max(10, H - PAD_T - PAD_B), rowH = plotH / SVCS.length;

    const colW = isLin ? 6 : Math.min(8, Math.max(2, (plotW / commits.length) - 1.5));

    let xPos = [];
    if (isLin) {
        const t0 = Math.min(...commits.map(c => c.ts));
        const tN = Math.max(...commits.map(c => c.ts));
        const pad = (tN === t0) ? 86400 : (tN - t0) * 0.05;
        // Distribute identical timestamps cleanly across the day
        const tsCounts = {};
        commits.forEach(c => { tsCounts[c.ts] = (tsCounts[c.ts] || 0) + 1; });
        const tsSeen = {};
        
        xPos = commits.map(c => {
            let base_x = PAD_L + ((c.ts - (t0 - pad)) / ((tN + pad) - (t0 - pad))) * plotW;
            let count = tsCounts[c.ts];
            if (count > 1) {
                let seen = tsSeen[c.ts] || 0;
                tsSeen[c.ts] = seen + 1;
                // Create a bounded spread window for overlapping commits
                let spread = Math.min(count * 5, plotW * 0.05); 
                base_x += (seen - (count - 1) / 2) * (spread / count);
            }
            return base_x;
        });
    } else {
        const innerW = plotW - colW;
        const step = commits.length > 1 ? innerW / (commits.length - 1) : 0;
        xPos = commits.map((_, i) => PAD_L + (colW / 2) + (i * step));
    }
    
    const ns = 'http://www.w3.org/2000/svg';
    svgEl.setAttribute('viewBox', `0 0 ${W} ${H}`); 
    svgEl.setAttribute('preserveAspectRatio', 'none');

    const fragment = document.createDocumentFragment();

    SVCS.forEach((lbl, row) => {
        const t = document.createElementNS(ns, 'text');
        t.setAttribute('x', PAD_L - 6); 
        t.setAttribute('y', PAD_T + row * rowH + rowH / 2 + 3.5);
        t.setAttribute('text-anchor', 'end'); 
        t.setAttribute('font-family', 'Satoshi, sans-serif'); 
        t.setAttribute('font-size', '10'); 
        t.setAttribute('fill', '#7a7874'); 
        t.textContent = lbl;
        fragment.appendChild(t);

        const bgRect = document.createElementNS(ns, 'rect');
        bgRect.setAttribute('x', PAD_L); 
        bgRect.setAttribute('y', PAD_T + row * rowH + 1);
        bgRect.setAttribute('width', plotW); 
        bgRect.setAttribute('height', rowH - 2); 
        bgRect.setAttribute('rx', 2);
        bgRect.setAttribute('fill', 'rgba(255,255,255,.04)');
        fragment.appendChild(bgRect);
    });

    // Draw Month/Year Dividers if in Timeline Mode
    if (isLin && commits.length > 0) {
        const t0 = Math.min(...commits.map(c => c.ts));
        const tN = Math.max(...commits.map(c => c.ts));
        const pad = (tN === t0) ? 86400 : (tN - t0) * 0.05;
        
        let cur = new Date(t0 * 1000);
        cur.setDate(1); 
        cur.setHours(0,0,0,0); 
        cur.setMonth(cur.getMonth() + 1); // Start at the first day of the next month
        
        while(cur.getTime() / 1000 <= tN) {
            const px = PAD_L + (((cur.getTime() / 1000) - (t0 - pad)) / ((tN + pad) - (t0 - pad))) * plotW;
            
            if (px >= PAD_L && px <= rightEdge) {
                // Vertical Line
                const line = document.createElementNS(ns, 'line');
                line.setAttribute('x1', px);
                line.setAttribute('y1', PAD_T - MD_TOP);
                line.setAttribute('x2', px);
                line.setAttribute('y2', PAD_T + plotH + 6);
                line.setAttribute('stroke', 'rgba(255,255,255,0.25)');
                line.setAttribute('stroke-width', '1');
                fragment.appendChild(line);
                
                // Month Label
                const mLabel = document.createElementNS(ns, 'text');
                mLabel.setAttribute('x', px + 4);
                mLabel.setAttribute('y', PAD_T - MD_TOP + 6);
                mLabel.setAttribute('font-family', 'Satoshi, sans-serif');
                mLabel.setAttribute('font-weight', '700');
                mLabel.setAttribute('font-size', '9');
                mLabel.setAttribute('fill', 'rgba(255,255,255,0.75)');
                mLabel.setAttribute('alignment-baseline', 'middle');
                mLabel.textContent = cur.toLocaleString('default', { month: 'short' }).toUpperCase();
                fragment.appendChild(mLabel);
            }
            cur.setMonth(cur.getMonth() + 1);
        }
    }

    commits.forEach((c, col) => {
        let rx = xPos[col] - (colW / 2);
        rx = Math.max(PAD_L, Math.min(rx, rightEdge - colW));
        SVCS.forEach((svc, row) => {
            const val = c[`touches_${svc.toLowerCase()}`];
            if (val > 0) {
                const rect = document.createElementNS(ns, 'rect');
                rect.setAttribute('x', rx);
                rect.setAttribute('y', PAD_T + row * rowH + 1);
                rect.setAttribute('width', colW);
                rect.setAttribute('height', rowH - 2);
                rect.setAttribute('rx', 2);
                const color = SCOPE_COLORS[svc.toLowerCase()] || '#4caf50';
                
                // Adjust opacity based on intensity (val is 1-4)
                let op = 0.25 * val;
                if (op > 1) op = 1;
                
                rect.setAttribute('fill', color);
                rect.setAttribute('opacity', op);
                
                // Tooltip handling (relies on global document listener in tooltips.js)
                rect.setAttribute('class', 'info-hover');
                const ttt = `${svc} [${val}/4] - ${c.h ? c.h.substring(0,7) : c.hash_short}\n\n${c.s || c.subject}`;
                rect.setAttribute('data-tt-temp', ttt);
                
                fragment.appendChild(rect);
            }
        });
    });

    svgEl.appendChild(fragment);
}
