import { CM_COLORS, BP_AXC_BASE, SC_COLORS } from '../core/constants.js';
import { calcMAvg, getTop25 } from '../core/dataEngine.js';
import { UI_STATE } from '../core/state.js';
import { monthDiv, customTooltip, getXConf, MD_TOP } from './plugins.js';

let charts = {};

// THE FIX: Ensure Chart.js never divides by zero on a 1-commit timeline
const ensureRange = (c) => {
    if (c.length > 1) return c;
    // If only 1 commit, create a fake invisible boundary 1 hour earlier
    const fake = { ...c[0], ts: c[0].ts - 3600, _fake: true };
    return [fake, c[0]];
};

const def = (c) => ({ responsive:true, maintainAspectRatio:false, plugins:{legend:{display:false},tooltip:{enabled:false,external:customTooltip(c)}}, scales:{y:{grid:{color:'rgba(255,255,255,.04)'},ticks:{color:'#7a7874',font:{family:'Satoshi',size:10}}}} });

export function renderTypesChart(c) {
    if(charts.types) charts.types.destroy(); const tc={}; c.forEach(x=>tc[x.t]=(tc[x.t]||0)+1); const types=Object.keys(tc).sort((a,b)=>tc[b]-tc[a]);
    const clr={feat:'#5c91e0',fix:'#ff4b4b',perf:'#c99ef0',refactor:'#8ed068',chore:'#aaa',docs:'#ffa726',test:'#00bcd4'};
    charts.types = new Chart('cm-c-types',{type:'bar',data:{labels:types,datasets:[{data:types.map(t=>tc[t]),backgroundColor:types.map(t=>clr[t]||'#888'),borderRadius:4}]},options:{responsive:true,maintainAspectRatio:false,indexAxis:'y',plugins:{legend:{display:false}},scales:{x:{grid:{color:'rgba(255,255,255,.04)'}},y:{grid:{color:'rgba(255,255,255,.04)'}}}}});
}
export function renderStackChart(rawC) {
    if(charts.stack) charts.stack.destroy(); const lin=UI_STATE.stack; const c = lin ? ensureRange(rawC) : rawC; 
    const mk=(ax)=>c.map(x=>lin?{x:x.ts,y:x._fake?null:x[ax]}:x[ax]);
    charts.stack = new Chart('cm-c-stack',{type:'bar',data:{labels:lin?undefined:c.map(x=>`#${x.n}`),datasets:['C','I','R','S','D'].map((ax,i)=>({label:ax,data:mk(ax),backgroundColor:BP_AXC_BASE[i],stack:'s',barThickness:lin?6:undefined}))},options:{...def(c),layout:{padding:{top:MD_TOP}},scales:{x:{...getXConf(lin,c),stacked:true},y:{...def(c).scales.y,stacked:true,max:16}}},plugins:lin?[monthDiv(c)]:[]});
}
export function renderTrendChart(rawC) {
    if(charts.trend) charts.trend.destroy(); const lin=UI_STATE.trend; const c = lin ? ensureRange(rawC) : rawC;
    const avg=calcMAvg(c.map(x=>x.tot),UI_STATE.avgTrend,c,lin); const mk=(tr)=>c.map(x=>tr&&x.tier!==tr?(lin?{x:x.ts,y:null}:null):(lin?{x:x.ts,y:x._fake?null:x.tot}:x.tot));
    charts.trend = new Chart('cm-c-trend',{type:'line',data:{labels:lin?undefined:c.map(x=>`#${x.n}`),datasets:[{label:'Avg',data:avg,borderColor:'rgba(79,152,163,0.85)',borderWidth:2,pointRadius:0,fill:false,tension:0.4,showLine:true},{label:'Tot',data:mk(),borderColor:'rgba(200,200,210,.18)',borderWidth:1.5,pointRadius:0,fill:false,showLine:!lin},{label:'C',data:mk('Critical'),borderColor:'transparent',pointBackgroundColor:CM_COLORS.Critical,pointRadius:5,showLine:false},{label:'S',data:mk('Significant'),borderColor:'transparent',pointBackgroundColor:CM_COLORS.Significant,pointRadius:5,showLine:false},{label:'R',data:mk('Routine'),borderColor:'transparent',pointBackgroundColor:CM_COLORS.Routine,pointRadius:5,showLine:false}]},options:{...def(c),layout:{padding:{top:MD_TOP}},scales:{x:getXConf(lin,c),y:{...def(c).scales.y,max:16}}},plugins:lin?[monthDiv(c)]:[]});
}
function buildCombo(id, stKey, avgKey, rawC, dFunc, clr) {
    if(charts[stKey]) charts[stKey].destroy(); const lin=UI_STATE[stKey]; const c = lin ? ensureRange(rawC) : rawC;
    const avg=calcMAvg(c.map(dFunc),UI_STATE[avgKey],c,lin);
    charts[stKey] = new Chart(id,{type:'bar',data:{labels:lin?undefined:c.map(x=>`#${x.n}`),datasets:[{type:'line',data:avg,borderColor:'rgba(79,152,163,0.8)',borderWidth:1.5,pointRadius:0,tension:0.3},{type:'bar',data:c.map(x=>lin?{x:x.ts,y:x._fake?null:dFunc(x)}:dFunc(x)),backgroundColor:clr,borderRadius:2,barThickness:lin?4:undefined}]},options:{...def(c),layout:{padding:{top:MD_TOP}},scales:{x:getXConf(lin,c),y:{...def(c).scales.y,beginAtZero:true}}},plugins:lin?[monthDiv(c)]:[]});
}
export function renderAnalytics(c) {
    buildCombo('cm-c-frag','frag','avgFrag',c,x=>(x.C+x.R)/(x.D||1),'rgba(255, 75, 75, 0.7)');
    buildCombo('cm-c-churn','churn','avgChurn',c,x=>x.C/(x.I||1),'rgba(201, 158, 240, 0.7)');
    buildCombo('cm-c-blast','blast','avgBlast',c,x=>x.S*x.R,'rgba(255, 184, 77, 0.7)');
}
export function renderConvergenceChart(rawC) {
    if(charts.conv) charts.conv.destroy(); const lin=UI_STATE.conv; const c = lin ? ensureRange(rawC) : rawC;
    const f=c.map(x=>(x.C+x.R)/(x.D||1)), ch=c.map(x=>x.C/(x.I||1)), b=c.map(x=>x.S*x.R); const fT=getTop25(f), cT=getTop25(ch), bT=getTop25(b);
    const nd=c.map((x,i)=>{ const h=(f[i]>=fT?1:0)+(ch[i]>=cT?1:0)+(b[i]>=bT?1:0); if(h>=2&&x.tot>0){const m=Math.max(f[i],ch[i],b[i]);return lin?{x:x.ts,y:x._fake?null:m+1}:m+1;} return lin?{x:x.ts,y:null}:null; });
    charts.conv = new Chart('cm-c-conv',{type:'line',data:{labels:lin?undefined:c.map(x=>`#${x.n}`),datasets:[{label:'Node',data:nd,type:'scatter',pointBackgroundColor:c.map(x=>SC_COLORS['t_'+x.scope]||'#fff'),pointBorderColor:'rgba(255,255,255,0.8)',pointBorderWidth:2,pointRadius:6},{label:'Frag',data:c.map((x,i)=>lin?{x:x.ts,y:x._fake?null:f[i]}:f[i]),borderColor:'rgba(255, 75, 75, 0.4)',backgroundColor:'rgba(255, 75, 75, 0.05)',borderWidth:1,fill:true,tension:0.4,pointRadius:0},{label:'Churn',data:c.map((x,i)=>lin?{x:x.ts,y:x._fake?null:ch[i]}:ch[i]),borderColor:'rgba(201, 158, 240, 0.4)',backgroundColor:'rgba(201, 158, 240, 0.05)',borderWidth:1,fill:true,tension:0.4,pointRadius:0},{label:'Blast',data:c.map((x,i)=>lin?{x:x.ts,y:x._fake?null:b[i]}:b[i]),borderColor:'rgba(255, 184, 77, 0.4)',backgroundColor:'rgba(255, 184, 77, 0.05)',borderWidth:1,fill:true,tension:0.4,pointRadius:0}]},options:{...def(c),layout:{padding:{top:MD_TOP}},scales:{x:getXConf(lin,c),y:{...def(c).scales.y,beginAtZero:true}}},plugins:lin?[monthDiv(c)]:[]});
}

export function renderTierChart(c) {
    if(charts.tier) charts.tier.destroy();
    const counts = { Critical: 0, Significant: 0, Routine: 0 };
    c.forEach(x => { if(counts[x.tier] !== undefined) counts[x.tier]++; });
    charts.tier = new Chart('cm-c-tier', {
        type: 'doughnut',
        data: {
            labels: ['Critical', 'Significant', 'Routine'],
            datasets: [{
                data: [counts.Critical, counts.Significant, counts.Routine],
                backgroundColor: [CM_COLORS.Critical, CM_COLORS.Significant, CM_COLORS.Routine],
                borderWidth: 0,
                hoverOffset: 4
            }]
        },
        options: { responsive: true, maintainAspectRatio: false, cutout: '70%', plugins: { legend: { position: 'right', labels: { color: '#7a7874', boxWidth: 10 } }, tooltip: { enabled: true } } }
    });
}
