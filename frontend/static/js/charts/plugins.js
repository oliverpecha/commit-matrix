if (typeof window !== 'undefined' && !window._cmMouseTracker) {
    window._cmMouseTracker = true;
    window._cmMouseY = 0;
    document.addEventListener('mousemove', e => window._cmMouseY = e.clientY);
}
import { fmtCD } from '../core/dataEngine.js?v=0.1.324';
import { CM_COLORS, BP_AXC, SC_COLORS, TYPE_COLORS } from '../constants/colors.js?v=0.1.324';
import { BP_AX } from '../constants/config.js?v=0.1.324';export const MD_TOP = 18;
export const monthDiv = (commits) => ({
    id: 'monthDiv',
    afterDraw(chart) {
        const { ctx, scales:{x}, chartArea: ca } = chart; if (!x || x.type !== 'linear') return;
        const latestC = chart._cmCommits || commits;
        const t0 = Math.min(...latestC.map(c=>c.ts)), tN = Math.max(...latestC.map(c=>c.ts)); if(tN===t0) return;
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

    if (id === 'cm-c-trend' && m.dataPoints && m.dataPoints[0].dataset.label === 'Avg') {
        el.classList.remove('visible');
        return;
    }

    if (id === 'cm-c-tier') {
        if (ctx.chart.config.type === 'line') {
            const dp = m.dataPoints;
            const ts = dp[0].parsed.x;
            
            const getVal = (lbl) => { 
                const d = dp.find(x => x.dataset.label === lbl); 
                return d ? (d.raw && d.raw.y !== undefined ? d.raw.y : (d.parsed.y || 0)) : 0; 
            };
            
            const piv = getVal('Pivotal');
            const cor = getVal('Core');
            const min = getVal('Minor');
            const tot = piv + cor + min || 1;
            
            const fmt = (v) => `${v} <span style="opacity:0.5;font-weight:normal;">/ ~${Math.round((v/tot*100))}%</span>`;
            const rowHTML = (lbl, val, clr, svgPath) => `<div class="cm-tt-row" style="margin-bottom:4px;justify-content:flex-start;gap:8px;"><span style="color:${clr};display:flex;align-items:center;gap:6px;"><svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">${svgPath}</svg> ${lbl}</span><span class="cm-tt-val" style="margin-left:auto;">${fmt(val)}</span></div>`;

            const tiers = [
                { l: 'Pivotal', v: piv, c: CM_COLORS.Pivotal||'#D43BC6', p: '<path d="M11.13 2.76a1 1 0 011.74 0l9.26 16.05a1 1 0 01-.87 1.5H2.74a1 1 0 01-.87-1.5l9.26-16.05z"/>' },
                { l: 'Core', v: cor, c: CM_COLORS.Core||'#36B8D8', p: '<rect x="3" y="3" width="18" height="18" rx="4"/>' },
                { l: 'Minor', v: min, c: CM_COLORS.Minor||'#6F8197', p: '<rect x="4" y="10" width="16" height="4" rx="2"/>' }
            ];

            let activeDp = dp[0];
            if (window._cmMouseY) {
                const rect = ctx.chart.canvas.getBoundingClientRect();
                const mouseY = window._cmMouseY - rect.top;
                const validDp = dp.filter(d => d.element && typeof d.element.y === 'number');
                if (validDp.length) activeDp = validDp.reduce((p, c) => Math.abs(c.element.y - mouseY) < Math.abs(p.element.y - mouseY) ? c : p);
            }
            const activeLbl = activeDp.dataset.label;

            let h = `<div class="cm-tt-hd"><div style="display:flex; justify-content:space-between; align-items:center; width:100%;"><span>Tier Snapshot</span><span style="font-family:monospace;opacity:0.5;font-weight:normal;">${fmtCD(ts)}</span></div></div>
            <div class="cm-tt-bd" style="margin-top:8px;border-top:1px solid rgba(255,255,255,0.06);padding-top:8px;">`;

            const activeT = tiers.find(t => t.l === activeLbl);
            if (activeT) {
                h += rowHTML(activeT.l, activeT.v, activeT.c, activeT.p);
                h += `<div style="border-top:1px solid rgba(255,255,255,0.06); margin: 6px 0;"></div>`;
            }

            const restT = tiers.filter(t => t.l !== activeLbl && t.v >= 0.1).sort((a, b) => b.v - a.v);
            restT.forEach(t => { h += rowHTML(t.l, t.v, t.c, t.p); });

            h += `</div>`;
            el.innerHTML = h;
            el.style.width = '180px';
            el.style.minWidth = '180px';
        } else {
            const lbl = m.dataPoints[0].label;
            const val = m.dataPoints[0].parsed.x || m.dataPoints[0].parsed.y || m.dataPoints[0].raw || 0;
            let clr = m.dataPoints[0].dataset.backgroundColor[m.dataPoints[0].dataIndex] || m.dataPoints[0].dataset.backgroundColor;
            if (typeof clr === 'function') clr = TYPE_COLORS[lbl] || '#888888';
            
            const allData = m.chart.data.datasets[0].data;
            const tot = allData.reduce((a, b) => a + b, 0) || 1;
            const pct = ((val / tot) * 100).toFixed(1) + '%';
            
            const svgs = {
                'Pivotal': '<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M11.13 2.76a1 1 0 011.74 0l9.26 16.05a1 1 0 01-.87 1.5H2.74a1 1 0 01-.87-1.5l9.26-16.05z"/></svg>',
                'Core': '<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><rect x="3" y="3" width="18" height="18" rx="4"/></svg>',
                'Minor': '<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><rect x="4" y="10" width="16" height="4" rx="2"/></svg>'
            };
            el.innerHTML = `<div class="cm-tt-hd" style="border:none;margin:0;padding:0;"><span>Tier Snapshot</span></div>
            <div class="cm-tt-bd" style="margin-top:8px;border-top:1px solid rgba(255,255,255,0.06);padding-top:8px;">
                <div class="cm-tt-row" style="justify-content:flex-start;gap:8px;"><span style="color:${clr};display:flex;align-items:center;gap:6px;">${svgs[lbl]||''} ${lbl}</span><span class="cm-tt-val" style="margin-left:auto;">${val} <span style="opacity:0.5;font-weight:normal;">/ ${pct}</span></span></div>
            </div>`;
            el.style.width = '160px';
            el.style.minWidth = '160px';
        }
    } 
    else if (id === 'cm-c-types') {
        if (ctx.chart.config.type === 'line') {
            const dp = m.dataPoints;
            const ts = dp[0].parsed.x;
            
            let activeDp = dp[0];
            if (window._cmMouseY) {
                const rect = ctx.chart.canvas.getBoundingClientRect();
                const mouseY = window._cmMouseY - rect.top;
                const validDp = dp.filter(d => d.element && typeof d.element.y === 'number');
                if (validDp.length) activeDp = validDp.reduce((p, c) => Math.abs(c.element.y - mouseY) < Math.abs(p.element.y - mouseY) ? c : p);
            }
            const activeLbl = activeDp.dataset.label;
            
            let h = `<div class="cm-tt-hd" style="display:flex; justify-content:space-between; align-items:center;"><span>Type Composition</span><span style="font-family:monospace;opacity:0.5;font-weight:normal;">${fmtCD(ts)}</span></div>
            <div class="cm-tt-bd" style="margin-top:8px;border-top:1px solid rgba(255,255,255,0.06);padding-top:8px;">`;
            
            const getRawCount = (d) => {
                if (d.raw && d.raw._count !== undefined) return d.raw._count;
                if (d.dataset && d.dataset.data && d.dataset.data[d.dataIndex] && d.dataset.data[d.dataIndex]._count !== undefined) return d.dataset.data[d.dataIndex]._count;
                return 0;
            };
            
            const formatRow = (d) => {
                let bgClr = (typeof TYPE_COLORS !== 'undefined' && TYPE_COLORS[d.dataset.label]) ? TYPE_COLORS[d.dataset.label] : '#888888';
                return `<div class="cm-tt-row" style="margin-bottom:4px;"><span style="color:${bgClr};display:flex;align-items:center;gap:6px;font-weight:700;"><div style="width:10px;height:10px;border-radius:3px;background:${bgClr};"></div>${d.dataset.label}</span><span class="cm-tt-val">${getRawCount(d)} <span style="opacity:0.5;font-weight:normal;">/ ~${Math.round(d.parsed.y)}%</span></span></div>`;
            };
            
            h += formatRow(activeDp);
            h += `<div style="border-top:1px solid rgba(255,255,255,0.06); margin: 6px 0;"></div>`;
            
            const restDp = dp.filter(d => d.dataset.label !== activeLbl && d.parsed.y >= 0.1).sort((a, b) => b.parsed.y - a.parsed.y);
            restDp.forEach(d => { h += formatRow(d); });
            h += `</div>`;
            
            el.innerHTML = h;
            el.style.width = '180px';
            el.style.minWidth = '180px';
        } else {
            const lbl = m.dataPoints[0].label;
            const val = m.dataPoints[0].parsed.x || m.dataPoints[0].parsed.y || m.dataPoints[0].raw || 0;
            const clr = (typeof TYPE_COLORS !== 'undefined' && TYPE_COLORS[lbl]) ? TYPE_COLORS[lbl] : '#888888';
            
            const allData = m.chart.data.datasets[0].data;
            const tot = allData.reduce((a, b) => a + b, 0) || 1;
            const pct = ((val / tot) * 100).toFixed(1) + '%';
            
            el.innerHTML = `<div class="cm-tt-hd" style="border:none;margin:0;padding:0;"><span>Type Composition</span></div>
            <div class="cm-tt-bd" style="margin-top:8px;border-top:1px solid rgba(255,255,255,0.06);padding-top:8px;"><div class="cm-tt-row">
                <span style="display:flex;align-items:center;gap:6px;font-weight:700;color:#d9d8d5;"><div style="width:10px;height:10px;border-radius:3px;background:${clr};"></div>${lbl}</span>
                <span class="cm-tt-val">${val} <span style="opacity:0.5;font-weight:normal;">/ ${pct}</span></span>
            </div></div>`;
            el.style.width = '180px';
            el.style.minWidth = '180px';
        }
    } 
    else {
        el.style.width = '';
        el.style.minWidth = '';
const c = (ctx.chart._cmCommits || commits)[m.dataPoints[0].dataIndex]; if (!c) return;
        
        const subj = c.p_desc || c.clean_s || c.desc || c.s || c.subject || c.message || 'Unknown subject';
        const typ = (c.p_type || c.t || c.type || 'chore').toLowerCase();
        const scp = (c.p_scope || c.scope || 'global').toLowerCase();
        
        const scpClr = (typeof SC_COLORS !== 'undefined' && SC_COLORS['t_'+scp]) ? SC_COLORS['t_'+scp] : ((typeof SC_COLORS !== 'undefined' && SC_COLORS[scp]) ? SC_COLORS[scp] : '#aaa');
        const typClr = (typeof TYPE_COLORS !== 'undefined' && TYPE_COLORS[typ]) ? TYPE_COLORS[typ] : '#aaa';
        
        const shortHash = c.h ? c.h.substring(0,7) : '';
        let h = `<div class="cm-tt-hd"><span>#${c.n} — ${fmtCD(c.ts)}</span><span style="font-family:monospace;opacity:0.5">${shortHash}</span></div>`;
        h += `<div class="cm-tt-meta" style="display:flex;align-items:center;justify-content:space-between;gap:8px;font-size:10px;font-family:monospace;margin-bottom:8px;color:#9e9e9e;">
            <span style="color:${typClr};background:rgba(255,255,255,0.05);padding:2px 4px;border-radius:3px;">${typ}</span>
            <span style="color:${scpClr};background:rgba(255,255,255,0.05);padding:2px 4px;border-radius:3px;">${scp}</span>
            <div><span style="color:#4caf50">+${c.lines_added||c.la||0}</span> <span style="color:#f44336">-${c.lines_deleted||c.ld||0}</span></div>
        </div>`;
        h += `<div class="cm-tt-subj" style="font-size:12px;color:#d9d8d5;margin-bottom:10px;line-height:1.4;max-width:250px;white-space:normal;">${subj}</div>`;
        h += `<div style="border-top:1px solid rgba(255,255,255,0.06);margin-bottom:8px;"></div><div class="cm-tt-bd">`;
        
        const payloadEl = document.getElementById('cm-page-payload');
        const pData = payloadEl ? JSON.parse(payloadEl.textContent) : {};
        const rName = (new URLSearchParams(window.location.search).get("rubric") || pData.default_rubric || "unknown").replace('_mock', '').toLowerCase();
        const rMeta = (pData.rubrics_meta && pData.rubrics_meta[rName]) ? pData.rubrics_meta[rName] : {};
        const axColors = (rMeta.colors && rMeta.colors.length) ? rMeta.colors : ['#5c91e0','#c99ef0','#ffb84d','#ff4b4b','#4caf50','#00bcd4'];

        if (id === 'cm-c-stack') { 
            const svgsTier={'Pivotal':'<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M11.13 2.76a1 1 0 011.74 0l9.26 16.05a1 1 0 01-.87 1.5H2.74a1 1 0 01-.87-1.5l9.26-16.05z"/></svg>','Core':'<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><rect x="3" y="3" width="18" height="18" rx="4"/></svg>','Minor':'<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><rect x="4" y="10" width="16" height="4" rx="2"/></svg>'};
            const tierClr = (typeof CM_COLORS !== 'undefined' && CM_COLORS[c.tier]) ? CM_COLORS[c.tier] : '#fff';
            const axes = window.CM_ACTIVE_AXES || ['C','O','R','D'];
            
            h += `<div style="display:grid; grid-template-columns: auto 1fr auto; gap: 4px 16px; align-items: center;">`;
            
            // Column 1: Merged Tier Cell spanning all rows
            h += `<div style="grid-row: 1 / span ${axes.length + 1}; display:flex; flex-direction:column; align-items:center; justify-content:center; padding-right:16px; border-right:1px solid rgba(255,255,255,0.08); color:${tierClr}; font-weight:700; gap:8px;">${svgsTier[c.tier]||''} <span>${c.tier}</span></div>`;
            
            // Columns 2 & 3: Axes Rows
            axes.forEach((ax,i) => {
                h += `<div style="color:${axColors[i % axColors.length]}; font-weight:800;">${ax}</div>`;
                h += `<div class="cm-tt-val" style="text-align:right;">${c[ax]!==undefined?c[ax]:'-'}</div>`;
            });
            
            // Columns 2 & 3: Total Row
            h += `<div style="color:#fff; font-weight:800; border-top:1px solid rgba(255,255,255,0.06); padding-top:6px; margin-top:2px;">Total</div>`;
            h += `<div class="cm-tt-val" style="text-align:right; border-top:1px solid rgba(255,255,255,0.06); padding-top:6px; margin-top:2px;">${c.tot}</div>`;
            
            h += `</div>`;
        } 
        else if (id === 'cm-c-trend') { const svgs={'Pivotal':'<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M11.13 2.76a1 1 0 011.74 0l9.26 16.05a1 1 0 01-.87 1.5H2.74a1 1 0 01-.87-1.5l9.26-16.05z"/></svg>','Core':'<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><rect x="3" y="3" width="18" height="18" rx="4"/></svg>','Minor':'<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><rect x="4" y="10" width="16" height="4" rx="2"/></svg>'}; h+=`<div class="cm-tt-row" style="justify-content:flex-start;gap:8px;"><span style="color:${(typeof CM_COLORS !== 'undefined' && CM_COLORS[c.tier])?CM_COLORS[c.tier]:'#fff'};display:flex;align-items:center;gap:6px;">${svgs[c.tier]||''} ${c.tier}</span><span class="cm-tt-val" style="margin-left:auto;">Score: ${c.tot}</span></div>`; } 
        else if (id === 'cm-c-conv') { h+=`<div class="cm-tt-row"><span style="color:${scpClr}">■ Convergence Node</span></div>`; } 
        else { h+=`<div class="cm-tt-row"><span style="color:${m.dataPoints[0].dataset.backgroundColor}">■ ${m.dataPoints[0].dataset.label}</span><span class="cm-tt-val">${m.dataPoints[0].parsed.y}</span></div>`; }
        
        h += `</div>`;
        el.innerHTML = h;
    }

    // Dynamic Centering & Viewport Math
    const pos = ctx.chart.canvas.getBoundingClientRect();

    let activeX = m.caretX;
    let activeY = m.caretY;

    // Use global mouse Y if available to track vertical movement better on bars
    if (window._cmMouseY) {
        const localY = window._cmMouseY - pos.top;
        if (localY >= 0 && localY <= pos.height) activeY = localY;
    }

    // Standardized mouse icon size offset (Bottom-Right placement)
    const cursorOffsetX = 12;
    const cursorOffsetY = 12;

    el.style.transform = `translate(0px, 0px)`;
    el.style.left = (pos.left + activeX + cursorOffsetX) + 'px';
    el.style.top = (pos.top + activeY + cursorOffsetY) + 'px';
    el.classList.add('visible');
    
    requestAnimationFrame(() => {
        const rect = el.getBoundingClientRect();
        let shiftX = 0;
        let shiftY = 0;

        // X-Axis bounds clamping
        if (rect.left < 10) {
            shiftX = 10 - rect.left;
        } else if (rect.right > window.innerWidth - 10) {
            shiftX = window.innerWidth - 10 - rect.right;
        }

        // Y-Axis bounds clamping
        if (rect.top < 10) {
            shiftY = 10 - rect.top;
        } else if (rect.bottom > window.innerHeight - 10) {
            shiftY = window.innerHeight - 10 - rect.bottom;
        }

        if (shiftX !== 0 || shiftY !== 0) {
            el.style.transform = `translate(${shiftX}px, ${shiftY}px)`;
        }
    });
};
export const getXConf = (isLin, c) => {
    if(!isLin||c.length<2) return {type:'category'}; 
    const t0 = Math.min(...c.map(x=>x.ts)), tN = Math.max(...c.map(x=>x.ts));
    const pad=(tN-t0)*0.005;
    return { type:'linear', bounds:'data', offset:false, min:t0, max:tN+pad, grid:{color:'rgba(255,255,255,.04)'}, ticks:{color:'#7a7874',font:{family:'Satoshi',size:10},maxRotation:0,autoSkipPadding:25,callback:v=>fmtCD(v)} };
};
