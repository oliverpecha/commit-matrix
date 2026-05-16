import { fmtCD } from '../core/dataEngine.js?v=2';
import { CM_COLORS, BP_AX, BP_AXC, SC_COLORS } from '../core/constants.js?v=2';
export const MD_TOP = 18;
export const monthDiv = (commits) => ({
    id: 'monthDiv',
    afterDraw(chart) {
        const { ctx, scales:{x}, chartArea: ca } = chart; if (!x || x.type !== 'linear') return;
        const t0=commits[0].ts, tN=commits[commits.length-1].ts; if(tN===t0) return;
        let cur=new Date(t0*1000); cur.setDate(1); cur.setHours(0,0,0,0); cur.setMonth(cur.getMonth()+1);
        while(cur.getTime()/1000 <= tN) {
            const px=x.getPixelForValue(cur.getTime()/1000);
            if(px>=ca.left && px<=ca.right){
                ctx.save(); ctx.beginPath(); ctx.strokeStyle='rgba(255,255,255,0.25)'; ctx.lineWidth=1;
                ctx.moveTo(px,ca.top-MD_TOP); ctx.lineTo(px,ca.bottom+6); ctx.stroke();
                ctx.font='700 9px Satoshi, sans-serif'; ctx.fillStyle='rgba(255,255,255,0.75)'; ctx.textBaseline='middle';
                ctx.fillText(cur.toLocaleString('default',{month:'short'}).toUpperCase(), px+4, ca.top-MD_TOP+6); ctx.restore();
            }
            cur.setMonth(cur.getMonth()+1);
        }
    }
});
export const customTooltip = (commits) => function(ctx) {
    const el=document.getElementById('cm-tt'); const m=ctx.tooltip; if(m.opacity===0){el.classList.remove('visible');return;}
    const id=ctx.chart.canvas.id, c=commits[m.dataPoints[0].dataIndex];
    let h = `<div class="cm-tt-hd"><span>#${c.n} — ${fmtCD(c.ts)}</span><span style="font-family:monospace;opacity:0.5">${c.h}</span></div><div class="cm-tt-bd">`;
    if(id==='cm-c-stack'){ BP_AX.forEach((ax,i)=>h+=`<div class="cm-tt-row"><span style="color:${BP_AXC[i]}">${ax}</span><span class="cm-tt-val">${c[ax]}</span></div>`); h+=`<div class="cm-tt-row"><span style="color:#fff">Tot</span><span class="cm-tt-val">${c.tot}</span></div>`; }
    else if(id==='cm-c-trend'){ h+=`<div class="cm-tt-row"><span style="color:${CM_COLORS[c.tier]||'#fff'}">● ${c.tier}</span><span class="cm-tt-val">${c.tot}</span></div>`; }
    else if(id==='cm-c-conv'){ h+=`<div class="cm-tt-row"><span style="color:${SC_COLORS['t_'+c.scope]||'#fff'}">■ Convergence Node</span></div>`; }
    else { h+=`<div class="cm-tt-row"><span style="color:${m.dataPoints[0].dataset.backgroundColor}">■ ${m.dataPoints[0].dataset.label}</span><span class="cm-tt-val">${m.dataPoints[0].parsed.y}</span></div>`; }
    el.innerHTML = h+`</div><div class="cm-tt-subj">${c.clean_s}</div>`;
    const pos=ctx.chart.canvas.getBoundingClientRect(); el.style.left=pos.left+window.scrollX+m.caretX+'px'; el.style.top=pos.top+window.scrollY+m.caretY+'px'; el.classList.add('visible');
};
export const getXConf = (isLin, c) => {
    if(!isLin||c.length<2) return {type:'category'}; const pad=(c[c.length-1].ts-c[0].ts)*0.05;
    return { type:'linear', bounds:'data', offset:false, min:c[0].ts-pad, max:c[c.length-1].ts+pad, grid:{color:'rgba(255,255,255,.04)'}, ticks:{color:'#7a7874',font:{family:'Satoshi',size:10},callback:v=>fmtCD(v)} };
};
