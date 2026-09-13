import { fmtCD } from '../core/dataEngine.js?v=0.1.234';
import { CM_COLORS, BP_AXC, SC_COLORS, TYPE_COLORS } from '../constants/colors.js?v=0.1.234';
import { BP_AX } from '../constants/config.js?v=0.1.234';export const MD_TOP = 18;
export const monthDiv = (commits) => ({
    id: 'monthDiv',
    afterDraw(chart) {
        const { ctx, scales:{x}, chartArea: ca } = chart; if (!x || x.type !== 'linear') return;
        const t0 = Math.min(...commits.map(c=>c.ts)), tN = Math.max(...commits.map(c=>c.ts)); if(tN===t0) return;
        let cur=new Date(t0*1000); cur.setDate(1); cur.setHours(0,0,0,0); cur.setMonth(cur.getMonth()+1);
        while(cur.getTime()/1000 <= tN) {
            const px=x.getPixelForValue(cur.getTime()/1000);
            if(px>=ca.left && px<=ca.right){
                ctx.save(); ctx.beginPath(); ctx.strokeStyle='rgba(255,255,255,0.25)'; ctx.lineWidth=1;
                ctx.moveTo(px,ca.top-MD_TOP); ctx.lineTo(px,ca.bottom+6); ctx.stroke();
                ctx.font='700 9px Satoshi, sans-serif'; ctx.fillStyle='rgba(255,255,255,0.75)'; ctx.textAlign='left'; ctx.textBaseline='middle';
                ctx.fillText(cur.toLocaleString('default',{month:'short'}).toUpperCase(), px+4, ca.top-MD_TOP+6); ctx.restore();
            }
            cur.setMonth(cur.getMonth()+1);
        }
    }
});
export const customTooltip = (commits) => function(ctx) {
    const el = document.getElementById('cm-tt'); const m = ctx.tooltip; 
    if (m.opacity === 0) { el.classList.remove('visible'); return; }
    
    const id = ctx.chart.canvas.id;
    window._cmActiveChartCanvas = ctx.chart.canvas;

    if (id === 'cm-c-tier') {
        const lbl = m.dataPoints[0].label;
        const val = m.dataPoints[0].parsed;
        const clr = m.dataPoints[0].dataset.backgroundColor[m.dataPoints[0].dataIndex];
        const svgs = {
            'Pivotal': '<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M11.13 2.76a1 1 0 011.74 0l9.26 16.05a1 1 0 01-.87 1.5H2.74a1 1 0 01-.87-1.5l9.26-16.05z"/></svg>',
            'Core': '<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><rect x="3" y="3" width="18" height="18" rx="4"/></svg>',
            'Minor': '<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><rect x="4" y="10" width="16" height="4" rx="2"/></svg>'
        };
        el.innerHTML = `<div class="cm-tt-hd" style="border:none;margin:0;padding:0;"><span>Tier Snapshot</span></div>
        <div class="cm-tt-bd" style="margin-top:8px;border-top:1px solid rgba(255,255,255,0.06);padding-top:8px;">
            <div class="cm-tt-row"><span style="color:${clr};display:flex;align-items:center;gap:6px;font-weight:700;">${svgs[lbl]||''} ${lbl}</span><span class="cm-tt-val">${val}</span></div>
        </div>`;
        el.style.width = '140px';
        el.style.minWidth = '140px';
    } 
    else if (id === 'cm-c-types') {
        const lbl = m.dataPoints[0].label;
        const val = m.dataPoints[0].parsed.x || m.dataPoints[0].parsed.y || m.dataPoints[0].raw || 0;
        const clr = m.dataPoints[0].dataset.backgroundColor[m.dataPoints[0].dataIndex] || m.dataPoints[0].dataset.backgroundColor;
        el.innerHTML = `<div class="cm-tt-bd"><div class="cm-tt-row">
            <span style="display:flex;align-items:center;gap:6px;font-weight:700;color:#d9d8d5;"><div style="width:10px;height:10px;border-radius:3px;background:${clr};"></div>${lbl}</span>
            <span class="cm-tt-val">${val}</span>
        </div></div>`;
        el.style.width = '140px';
        el.style.minWidth = '140px';
    } 
    else {
        el.style.width = '';
        el.style.minWidth = '';
        const c = commits[m.dataPoints[0].dataIndex]; if (!c) return;
        
        // Exact metadata extraction mapping to SPA contract
        const subj = c.p_desc || c.clean_s || c.desc || c.s || c.subject || c.message || 'Unknown subject';
        const typ = (c.p_type || c.t || c.type || 'chore').toLowerCase();
        const scp = (c.p_scope || c.scope || 'global').toLowerCase();
        
        const scpClr = (typeof SC_COLORS !== 'undefined' && SC_COLORS['t_'+scp]) ? SC_COLORS['t_'+scp] : ((typeof SC_COLORS !== 'undefined' && SC_COLORS[scp]) ? SC_COLORS[scp] : '#aaa');
        const typClr = (typeof TYPE_COLORS !== 'undefined' && TYPE_COLORS[typ]) ? TYPE_COLORS[typ] : '#aaa';
        
        const shortHash = c.h ? c.h.substring(0,7) : '';
        let h = `<div class="cm-tt-hd"><span>#${c.n} — ${fmtCD(c.ts)}</span><span style="font-family:monospace;opacity:0.5">${shortHash}</span></div>`;
        h += `<div class="cm-tt-meta" style="display:flex;align-items:center;justify-content:space-between;gap:8px;font-size:10px;font-family:monospace;margin-bottom:10px;color:#9e9e9e;">
            <span style="color:${typClr};background:rgba(255,255,255,0.05);padding:2px 4px;border-radius:3px;">${typ}</span>
            <span style="color:${scpClr};background:rgba(255,255,255,0.05);padding:2px 4px;border-radius:3px;">${scp}</span>
            <div><span style="color:#4caf50">+${c.lines_added||c.la||0}</span> <span style="color:#f44336">-${c.lines_deleted||c.ld||0}</span></div>
        </div><div class="cm-tt-bd">`;
        
        const payloadEl = document.getElementById('cm-page-payload');
        const pData = payloadEl ? JSON.parse(payloadEl.textContent) : {};
        const rName = (new URLSearchParams(window.location.search).get("rubric") || pData.default_rubric || "unknown").replace('_mock', '').toLowerCase();
        const rMeta = (pData.rubrics_meta && pData.rubrics_meta[rName]) ? pData.rubrics_meta[rName] : {};
        const axColors = (rMeta.colors && rMeta.colors.length) ? rMeta.colors : ['#5c91e0','#c99ef0','#ffb84d','#ff4b4b','#4caf50','#00bcd4'];

        if (id === 'cm-c-stack') { 
            (window.CM_ACTIVE_AXES || ['C','O','R','D']).forEach((ax,i)=>h+=`<div class="cm-tt-row" style="justify-content:flex-start;gap:16px;"><span style="color:${axColors[i % axColors.length]};font-weight:800;width:32px;">${ax}</span><span class="cm-tt-val">${c[ax]!==undefined?c[ax]:'-'}</span></div>`); 
            h+=`<div class="cm-tt-row" style="margin-top:4px;justify-content:flex-start;gap:16px;"><span style="color:#fff;font-weight:800;width:32px;">Total</span><span class="cm-tt-val">${c.tot}</span></div>`; 
        } 
        else if (id === 'cm-c-trend') { const svgs={'Pivotal':'<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M11.13 2.76a1 1 0 011.74 0l9.26 16.05a1 1 0 01-.87 1.5H2.74a1 1 0 01-.87-1.5l9.26-16.05z"/></svg>','Core':'<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><rect x="3" y="3" width="18" height="18" rx="4"/></svg>','Minor':'<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><rect x="4" y="10" width="16" height="4" rx="2"/></svg>'}; h+=`<div class="cm-tt-row" style="justify-content:flex-start;gap:8px;"><span style="color:${(typeof CM_COLORS !== 'undefined' && CM_COLORS[c.tier])?CM_COLORS[c.tier]:'#fff'};display:flex;align-items:center;gap:6px;">${svgs[c.tier]||''} ${c.tier}</span><span class="cm-tt-val" style="margin-left:auto;">Score: ${c.tot}</span></div>`; } 
        else if (id === 'cm-c-conv') { h+=`<div class="cm-tt-row"><span style="color:${scpClr}">■ Convergence Node</span></div>`; } 
        else { h+=`<div class="cm-tt-row"><span style="color:${m.dataPoints[0].dataset.backgroundColor}">■ ${m.dataPoints[0].dataset.label}</span><span class="cm-tt-val">${m.dataPoints[0].parsed.y}</span></div>`; }
        
        h += `</div><div class="cm-tt-subj" style="font-size:11px;color:#9e9e9e;border-top:1px solid rgba(255,255,255,0.06);margin-top:8px;padding-top:8px;line-height:1.4;max-width:250px;white-space:normal;">${subj}</div>`;
        el.innerHTML = h;
    }

    // Dynamic Centering & Viewport Math
    const pos = ctx.chart.canvas.getBoundingClientRect();

    let activeY = m.caretY;
    if (['cm-c-frag','cm-c-churn','cm-c-blast','cm-c-conv'].includes(id) && m.dataPoints) {
        // Explicitly grab the bar dataset (index 1) to ignore the line's Y-coordinate
        const targetIndex = id === 'cm-c-conv' ? 0 : 1;
        const barDp = m.dataPoints.find(dp => dp.datasetIndex === targetIndex);
        if (barDp && barDp.element && typeof barDp.element.y === 'number') {
            activeY = barDp.element.y;
        }
    }

    // Default alignment
    let transY = '-100%';
    let offsetY = -15; // 15px above caret
    
    if (id === 'cm-c-tier' || id === 'cm-c-types') {
        transY = '-50%';
        offsetY = 0;
    } else {
        const ca = ctx.chart.chartArea;
        if (ca) {
            const isTopHalf = (activeY - ca.top) < (ca.bottom - ca.top) / 2;
            if (isTopHalf) {
                // If top half, render below caret
                transY = '0';
                offsetY = 15;
            }
        }
    }

    el.style.transform = `translate(-50%, ${transY})`;
    el.style.left = (pos.left + m.caretX) + 'px';
    el.style.top = (pos.top + activeY + offsetY) + 'px';
    el.classList.add('visible');
    
    // Viewport clamp via RAF to allow DOM to size
    requestAnimationFrame(() => {
        const rect = el.getBoundingClientRect();
        if (rect.left < 10) {
            el.style.transform = `translate(calc(-50% + ${10 - rect.left}px), ${transY})`;
        } else if (rect.right > window.innerWidth - 10) {
            el.style.transform = `translate(calc(-50% - ${rect.right - window.innerWidth + 10}px), ${transY})`;
        }
    });
};
export const getXConf = (isLin, c) => {
    if(!isLin||c.length<2) return {type:'category'}; 
    const t0 = Math.min(...c.map(x=>x.ts)), tN = Math.max(...c.map(x=>x.ts));
    const pad=(tN-t0)*0.05;
    return { type:'linear', bounds:'data', offset:false, min:t0-pad, max:tN+pad, grid:{color:'rgba(255,255,255,.04)'}, ticks:{color:'#7a7874',font:{family:'Satoshi',size:10},callback:v=>fmtCD(v)} };
};
