import { SCOPE_COLORS, TYPE_COLORS } from '../constants/colors.js?v=0.1.436';
import { UI_STATE } from '../core/state.js?v=0.1.436';
import { MD_TOP } from '../charts/plugins.js?v=0.1.436';

let lastCommits = [];
let _transBound = false;

if (!window._hmHoverBound) {
    window._hmHoverBound = true;
    const style = document.createElement('style');
    style.textContent = `
        #cm-heat-svg rect.info-hover { transition: opacity 0.2s ease; cursor: default !important; }
        #cm-heat-svg.is-hovering rect.info-hover:not(.active-col) { opacity: 0.10 !important; }
    `;
    document.head.appendChild(style);

    document.addEventListener('mouseover', (e) => {
        const t = e.target;
        if (t && typeof t.closest === 'function') {
            const rect = t.closest('rect.info-hover');
            if (rect) {
                const svg = rect.closest('#cm-heat-svg');
                if (svg) {
                    svg.classList.add('is-hovering');
                    const col = rect.getAttribute('data-col');
                    if (col !== null) {
                        svg.querySelectorAll('rect[data-col="' + col + '"]').forEach(r => r.classList.add('active-col'));
                    }
                }
            }
        }
    });
    
    document.addEventListener('mouseout', (e) => {
        const t = e.target;
        if (t && typeof t.closest === 'function') {
            const rect = t.closest('rect.info-hover');
            if (rect) {
                const svg = rect.closest('#cm-heat-svg');
                if (svg) {
                    svg.classList.remove('is-hovering');
                    svg.querySelectorAll('rect.active-col').forEach(r => r.classList.remove('active-col'));
                }
            }
        }
    });
}


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
    if (!svgEl || !container) return;
    while(svgEl.firstChild) svgEl.removeChild(svgEl.firstChild);
    if (!commits || !commits.length) return;

    if (!_transBound) {
        _transBound = true;
        container.addEventListener('transitionend', (e) => {
            if (e.target === container && lastCommits.length) {
                renderHeatmap(lastCommits);
            }
        });
    }
    
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
                rect.setAttribute('data-col', col);
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
                const d = new Date((c.ts || 0) * 1000); 
                const dateStr = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][d.getMonth()] + ' ' + String(d.getDate()).padStart(2,'0');
                const svgs = {'Pivotal':'<svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor"><path d="M11.13 2.76a1 1 0 011.74 0l9.26 16.05a1 1 0 01-.87 1.5H2.74a1 1 0 01-.87-1.5l9.26-16.05z"/></svg>','Core':'<svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor"><rect x="3" y="3" width="18" height="18" rx="4"/></svg>','Minor':'<svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor"><rect x="4" y="10" width="16" height="4" rx="2"/></svg>'};
                const tColor = c.tier === 'Pivotal' ? '#D43BC6' : c.tier === 'Core' ? '#36B8D8' : '#6F8197';
                
                const typ = (c.p_type || c.t || c.type || 'chore').toLowerCase();
                const scp = (c.p_scope || c.scope || 'global').toLowerCase();
                const typClr = (typeof TYPE_COLORS !== 'undefined' && TYPE_COLORS[typ]) ? TYPE_COLORS[typ] : '#aaa';
                const scpClr = SCOPE_COLORS[scp] || '#aaa';

                let barsHtml = '';
                SVCS.forEach(s => {
                    const sVal = c[`touches_${s.toLowerCase()}`];
                    if (sVal > 0) {
                        const sColor = SCOPE_COLORS[s.toLowerCase()] || '#4caf50';
                        const pct = (sVal / 4) * 100;
                        barsHtml += `<div style="display:flex;align-items:center;justify-content:flex-start;gap:12px;"><span style="color:${sColor};font-weight:700;width:60px;text-align:right;">${s}</span><div style="flex-grow:1;background:rgba(255,255,255,0.05);height:6px;border-radius:3px;overflow:hidden;min-width:100px;"><div style="width:${pct}%;background:${sColor};height:100%;border-radius:3px;"></div></div></div>`;
                    }
                });
                
                let h = `<div style="display:flex;justify-content:space-between;gap:16px;font-weight:bold;margin-bottom:8px;border-bottom:1px solid rgba(255,255,255,0.06);padding-bottom:6px;"><span>#${c.n || ''} — ${dateStr}</span><span style="font-family:monospace;opacity:0.5">${(c.h || c.hash_short || '').substring(0,7)}</span></div>`;
                h += `<div style="display:flex;align-items:center;justify-content:space-between;gap:8px;font-size:10px;font-family:monospace;margin-bottom:8px;color:#9e9e9e;"><div style="display:flex;gap:4px;"><span style="color:${typClr};background:rgba(255,255,255,0.05);padding:2px 4px;border-radius:3px;">${typ}</span><span style="color:${scpClr};background:rgba(255,255,255,0.05);padding:2px 4px;border-radius:3px;">${scp}</span></div><div><span style="color:#4caf50">+${c.lines_added||c.la||0}</span> <span style="color:#f44336">-${c.lines_deleted||c.ld||0}</span></div></div>`;
                h += `<div style="font-size:12px;color:#d9d8d5;margin-bottom:12px;line-height:1.4;max-width:250px;white-space:normal;border-bottom:1px solid rgba(255,255,255,0.06);padding-bottom:10px;">${c.s || c.subject || c.clean_s || 'unknown'}</div>`;
                h += `<div style="display:flex;align-items:center;justify-content:space-between;font-size:14px;font-family:Satoshi, sans-serif;font-weight:700;margin-bottom:12px;color:${tColor};"><div style="display:flex;align-items:center;gap:6px;">${svgs[c.tier]||''} ${c.tier}</div><div style="color:#e0e0e0;font-size:12px;">Score: ${c.tot||0}</div></div>`;
                h += `<div style="display:flex;flex-direction:column;gap:6px;">${barsHtml}</div>`;
                rect.setAttribute('data-info', h);
                
                fragment.appendChild(rect);
            }
        });
    });

    svgEl.appendChild(fragment);
}
