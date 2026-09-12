import { CM_COLORS, BP_AXC_BASE, SC_COLORS, TYPE_COLORS } from '../constants/colors.js?v=0.1.211';
import { calcMAvg, getTop25, processCommits } from '../core/dataEngine.js?v=0.1.211';
import { UI_STATE } from '../core/state.js?v=0.1.211';
import { monthDiv, customTooltip, getXConf, MD_TOP } from './plugins.js?v=0.1.211';
const SVCS_GHOST = ['Metrics','Preflight','Tests','Docs','Dashboard','Config','Scripts','Proxy'];
const ghostCanvas = document.createElement('canvas');
ghostCanvas.width = 600;
ghostCanvas.height = 200;
ghostCanvas.style.cssText = 'position:absolute;visibility:hidden;width:600px;height:200px;';
document.body.appendChild(ghostCanvas);

const ghostSync = { id: 'ghostSync', afterLayout(chart) {
    const a = chart.chartArea;
    window.CM_CHART_AREA = window.CM_CHART_AREA || {};
    if (window.CM_CHART_AREA.left !== a.left) {
        window.CM_CHART_AREA.left = a.left;
        window.dispatchEvent(new CustomEvent('cm-sync-heat'));
    }
}};

document.fonts.ready.then(() => {
    const ghost = new Chart(ghostCanvas, { type:'bar', data:{labels:SVCS_GHOST, datasets:[{data:SVCS_GHOST.map(()=>0)}]}, options:{ responsive:false, maintainAspectRatio:false, indexAxis:'y', scales:{y:{ticks:{font:{family:'Satoshi',size:10}}}}, plugins:{legend:{display:false}} }, plugins:[ghostSync] });
    console.log('Ghost chartArea:', ghost.chartArea);
    console.log('Ghost canvas actual font used:', ghost.ctx.font);
});

let charts = {};

const ensureRange = (c) => {
    if (c.length > 1) return c;
    const fake = { ...c[0], ts: c[0].ts - 3600, _fake: true };
    return [fake, c[0]];
};

const def = (c) => ({ responsive:true, maintainAspectRatio:false, plugins:{legend:{display:false},tooltip:{enabled:false,external:customTooltip(c)}}, scales:{y:{grid:{color:'rgba(255,255,255,.04)'},ticks:{color:'#7a7874',font:{family:'Satoshi',size:10}}}} });
const defRaw = (c) => ({ responsive:true, maintainAspectRatio:false, plugins:{legend:{display:false},tooltip:{enabled:false,external:customTooltip(c)}}, scales:{y:{grid:{color:'rgba(255,255,255,.04)'},ticks:{color:'#7a7874',font:{family:'Satoshi',size:10}}}} });

export function renderTypesChart(c) {
    const canvasId = 'cm-c-types';
    let canvasEl = document.getElementById(canvasId);
    
    if (canvasEl) {
        const newCanvas = document.createElement('canvas');
        newCanvas.id = canvasId;
        canvasEl.parentNode.replaceChild(newCanvas, canvasEl);
        canvasEl = newCanvas; 
    }
    
    if (charts.types) { delete charts.types; }

    const tc = {};
    c.forEach(x => {
        let type = String(x.p_type || x.t || x.type || "unknown").trim().toLowerCase();
        if (!TYPE_COLORS[type]) {
            const m = type.match(/^([a-z_-]+)/);
            if (m && TYPE_COLORS[m[1]]) type = m[1];
        }
        tc[type] = (tc[type] || 0) + 1;
    });

    const types = Object.keys(tc).sort((a, b) => tc[b] - tc[a]);
    const bgColors = types.map(t => TYPE_COLORS[t] || '#888888');

    charts.types = new Chart(canvasEl, {
        type: 'bar',
        data: {
            labels: types,
            datasets: [{
                data: types.map(t => tc[t]),
                backgroundColor: bgColors,
                borderWidth: 0,
                borderRadius: 4
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false, indexAxis: 'y',
            plugins: { legend: { display: false } },
            scales: { x: { grid: { color: 'rgba(255,255,255,.04)' } }, y: { grid: { color: 'rgba(255,255,255,.04)' } } }
        }
    });
}

export function renderStackChart(rawC) {
    if(charts.stack) charts.stack.destroy(); const lin=UI_STATE.stack; const c = lin ? ensureRange(rawC) : rawC; 
    const mk=(ax)=>c.map(x=>lin?{x:x.ts,y:x._fake?null:x[ax]}:x[ax]);
    const allVals = c.map(x=>x.tot).filter(v=>typeof v==='number'&&!isNaN(v)&&isFinite(v));
    const maxVal = allVals.length ? Math.max(...allVals) : 16;
    const sMax = maxVal + 1;
    charts.stack = new Chart('cm-c-stack',{type:'bar',data:{labels:lin?undefined:c.map(x=>`#${x.n}`),datasets:(window.CM_ACTIVE_AXES || ['C','O','R','D']).map((ax, i) => ({ label: ax, data: mk(ax), backgroundColor: ['#5c91e0', '#c99ef0', '#ffb84d', '#ff4b4b', '#4caf50', '#00bcd4'][i % 6], stack: 's', barThickness: lin ? 6 : undefined }))},options:{...defRaw(c),layout:{padding:{top: lin ? MD_TOP : 6, right: 8, left: 2}},scales:{x:{...getXConf(lin,c),stacked:true},y:{...defRaw(c).scales.y,stacked:true,min:0,max:sMax,ticks:{...defRaw(c).scales.y.ticks,stepSize:4}}}},plugins:lin?[monthDiv(c)]:[]});
}

export function renderTrendChart(rawC) {
    if(charts.trend) charts.trend.destroy(); const lin=UI_STATE.trend; const c = lin ? ensureRange(rawC) : rawC;
    const avg=calcMAvg(c.map(x=>x.tot),UI_STATE.avgTrend,c,lin); const mk=(tr)=>c.map(x=>tr&&x.tier!==tr?(lin?{x:x.ts,y:null}:null):(lin?{x:x.ts,y:x._fake?null:x.tot}:x.tot));
    const allVals = c.map(x=>x.tot).concat(avg.map(v=>typeof v==='object'&&v!==null?v.y:v)).filter(v=>typeof v==='number'&&!isNaN(v)&&isFinite(v));
    const tMin = allVals.length ? Math.max(0, Math.floor(Math.min(...allVals) - 1)) : 0;
    const maxVal = allVals.length ? Math.max(...allVals) : 16;
    const tMax = maxVal + 1;
    charts.trend = new Chart('cm-c-trend',{type:'line',data:{labels:lin?undefined:c.map(x=>`#${x.n}`),datasets:[{label:'Avg',data:avg,borderColor:'rgba(79,152,163,0.85)',borderWidth:2,pointRadius:0,fill:false,tension:0.4,showLine:true},{label:'Tot',data:mk(),borderColor:'rgba(200,200,210,.18)',borderWidth:1.5,pointRadius:0,fill:false,showLine:!lin},{label:'Pivotal',data:mk('Pivotal'),borderColor:'transparent',pointBackgroundColor:CM_COLORS.Pivotal,pointRadius:5,showLine:false},{label:'Core',data:mk('Core'),borderColor:'transparent',pointBackgroundColor:CM_COLORS.Core,pointRadius:5,showLine:false},{label:'Minor',data:mk('Minor'),borderColor:'transparent',pointBackgroundColor:CM_COLORS.Minor,pointRadius:5,showLine:false}]},options:{...def(c),layout:{padding:{top: lin ? MD_TOP : 6, right: 8, left: 2}},scales:{x:getXConf(lin,c),y:{...def(c).scales.y,min:tMin,max:tMax}}},plugins:lin?[monthDiv(c)]:[]});
}

function buildCombo(id, stKey, avgKey, rawC, dFunc, clr) {
    if(charts[stKey]) charts[stKey].destroy(); const lin=UI_STATE[stKey]; const c = lin ? ensureRange(rawC) : rawC;
    const avg=calcMAvg(c.map(dFunc),UI_STATE[avgKey],c,lin);
    const rawVals = c.map(dFunc).filter(v=>typeof v==='number'&&!isNaN(v)&&isFinite(v));
    const avgVals = avg.map(v=>typeof v==='object'&&v!==null?v.y:v).filter(v=>typeof v==='number'&&!isNaN(v)&&isFinite(v));
    const allVals = rawVals.concat(avgVals);
    const cMin = allVals.length ? Math.max(0, Math.floor(Math.min(...allVals) - 1)) : 0;
    const cMax = allVals.length ? Math.ceil(Math.max(...allVals) + 1) : 10;
    charts[stKey] = new Chart(id,{type:'bar',data:{labels:lin?undefined:c.map(x=>`#${x.n}`),datasets:[{type:'line',data:avg,borderColor:'rgba(79,152,163,0.8)',borderWidth:1.5,pointRadius:0,tension:0.3},{type:'bar',data:c.map(x=>lin?{x:x.ts,y:x._fake?null:dFunc(x)}:dFunc(x)),backgroundColor:clr,borderRadius:2,barThickness:lin?4:undefined}]},options:{...def(c),layout:{padding:{top: lin ? MD_TOP : 6, right: 8, left: 2}},scales:{x:getXConf(lin,c),y:{...def(c).scales.y,min:cMin,max:cMax}}},plugins:lin?[monthDiv(c)]:[]});
}

export function renderFragChart(c) {
    buildCombo('cm-c-frag','frag','avgFrag',c,x=>((x[(window.CM_ACTIVE_AXES || ['C','O','R','D'])[0]] || 0)+(x[(window.CM_ACTIVE_AXES || ['C','O','R','D'])[2]] || 0))/((x[(window.CM_ACTIVE_AXES || ['C','O','R','D'])[3]] || 0)||1),'rgba(255, 75, 75, 0.7)');
}

export function renderChurnChart(c) {
    buildCombo('cm-c-churn','churn','avgChurn',c,x=>(x[(window.CM_ACTIVE_AXES || ['C','O','R','D'])[0]] || 0)/((x[(window.CM_ACTIVE_AXES || ['C','O','R','D'])[1]] || 0)||1),'rgba(201, 158, 240, 0.7)');
}

export function renderBlastChart(c) {
    buildCombo('cm-c-blast','blast','avgBlast',c,x => { const a = window.CM_ACTIVE_AXES || ['C','O','R','D']; return (x[a[0]] || 1) * (x[a[2] || a[1]] || 1); },'rgba(255, 184, 77, 0.7)');
}

export function renderAnalytics(c) {
    renderFragChart(c);
    renderChurnChart(c);
    renderBlastChart(c);
}

export function renderConvergenceChart(rawC) {
    if(charts.conv) charts.conv.destroy(); const lin=UI_STATE.conv; const c = lin ? ensureRange(rawC) : rawC;
    const f=c.map(x=>((x[(window.CM_ACTIVE_AXES || ['C','O','R','D'])[0]] || 0)+(x[(window.CM_ACTIVE_AXES || ['C','O','R','D'])[2]] || 0))/((x[(window.CM_ACTIVE_AXES || ['C','O','R','D'])[3]] || 0)||1)), ch=c.map(x=>(x[(window.CM_ACTIVE_AXES || ['C','O','R','D'])[0]] || 0)/((x[(window.CM_ACTIVE_AXES || ['C','O','R','D'])[1]] || 0)||1)), b=c.map(x => { const a = window.CM_ACTIVE_AXES || ['C','O','R','D']; return (x[a[0]] || 1) * (x[a[2] || a[1]] || 1); }); const fT=getTop25(f), cT=getTop25(ch), bT=getTop25(b);
    const nd=c.map((x,i)=>{ const h=(f[i]>=fT?1:0)+(ch[i]>=cT?1:0)+(b[i]>=bT?1:0); if(h>=2&&x.tot>0){const m=Math.max(f[i],ch[i],b[i]);return lin?{x:x.ts,y:x._fake?null:m+1}:m+1;} return lin?{x:x.ts,y:null}:null; });
    const allVals = f.concat(ch, b).filter(v=>typeof v==='number'&&!isNaN(v)&&isFinite(v));
    const cvMin = allVals.length ? Math.max(0, Math.floor(Math.min(...allVals) - 1)) : 0;
    const cvMax = allVals.length ? Math.ceil(Math.max(...allVals) + 1) : 10;
    charts.conv = new Chart('cm-c-conv',{type:'line',data:{labels:lin?undefined:c.map(x=>`#${x.n}`),datasets:[{label:'Node',data:nd,type:'scatter',pointBackgroundColor:c.map(x=>SC_COLORS['t_'+x.scope]||'#fff'),pointBorderColor:'rgba(255,255,255,0.8)',pointBorderWidth:2,pointRadius:6},{label:'Frag',data:c.map((x,i)=>lin?{x:x.ts,y:x._fake?null:f[i]}:f[i]),borderColor:'rgba(255, 75, 75, 0.4)',backgroundColor:'rgba(255, 75, 75, 0.05)',borderWidth:1,fill:true,tension:0.4,pointRadius:0},{label:'Churn',data:c.map((x,i)=>lin?{x:x.ts,y:x._fake?null:ch[i]}:ch[i]),borderColor:'rgba(201, 158, 240, 0.4)',backgroundColor:'rgba(201, 158, 240, 0.05)',borderWidth:1,fill:true,tension:0.4,pointRadius:0},{label:'Blast',data:c.map((x,i)=>lin?{x:x.ts,y:x._fake?null:b[i]}:b[i]),borderColor:'rgba(255, 184, 77, 0.4)',backgroundColor:'rgba(255, 184, 77, 0.05)',borderWidth:1,fill:true,tension:0.4,pointRadius:0}]},options:{...def(c),layout:{padding:{top: lin ? MD_TOP : 6, right: 8, left: 2}},scales:{x:getXConf(lin,c),y:{...def(c).scales.y,min:cvMin,max:cvMax}}},plugins:lin?[monthDiv(c)]:[]});
}


export function updateKPIs(c) {
    const counts = { Pivotal: 0, Core: 0, Minor: 0 };
    let totalScore = 0;
    c.forEach(x => {
        if (counts[x.tier] !== undefined) counts[x.tier]++;
        totalScore += (x.tot || 0);
    });
    
    const totalCommits = c.length;
    const avgScore = totalCommits > 0 ? (totalScore / totalCommits) : 0;

    const setVal = (id, val, color) => {
        const el = document.getElementById(id);
        if (el) {
            el.textContent = val;
            if (color) el.style.color = color;
        }
    };

    // Apply exact UI colors dynamically
    setVal('cm-kp', totalCommits, '#d9d8d5');
    setVal('cm-kc', counts.Pivotal, counts.Pivotal > 0 ? CM_COLORS.Pivotal : '#7a7874');
    setVal('cm-ks', counts.Core, counts.Core > 0 ? CM_COLORS.Core : '#7a7874');
    setVal('cm-kr', counts.Minor, counts.Minor > 0 ? CM_COLORS.Minor : '#7a7874');

    // Dynamic color routing for Average Score based on performance tier
    let avgColor = CM_COLORS.Minor;
    if (avgScore >= 13) avgColor = CM_COLORS.Pivotal;
    else if (avgScore >= 9) avgColor = CM_COLORS.Core;

    setVal('cm-ka', avgScore.toFixed(1), totalCommits > 0 ? avgColor : '#7a7874');
}

export function renderTierChart(c) {
    updateKPIs(c);
    if(charts.tier) charts.tier.destroy();
    const counts = { Pivotal: 0, Core: 0, Minor: 0 };
    c.forEach(x => { if(counts[x.tier] !== undefined) counts[x.tier]++; });
    charts.tier = new Chart('cm-c-tier', {
        type: 'doughnut',
        data: {
            labels: ['Pivotal', 'Core', 'Minor'],
            datasets: [{
                data: [counts.Pivotal, counts.Core, counts.Minor],
                backgroundColor: [CM_COLORS.Pivotal || '#D43BC6', CM_COLORS.Core || '#36B8D8', CM_COLORS.Minor || '#6F8197'],
                borderWidth: 0,
                hoverOffset: 4
            }]
        },
        options: { responsive: true, maintainAspectRatio: false, cutout: '70%', plugins: { legend: { display: false }, tooltip: { enabled: true } } }
    });
}

const avgModeNames = ['Off', 'Trailing 5', 'Daily Peak', 'Daily Median', 'Vol-Weighted', '7D High-Water'];

if (!window._cmChartBindingsReady) {
    window._cmChartBindingsReady = true;
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('button[data-action]');
        if (!btn) return;
        
        const action = btn.getAttribute('data-action');
        const target = btn.getAttribute('data-target');
        if (!['toggleChron', 'cycleAvg', 'toggleGlobalChron'].includes(action)) return;

        const payload = processCommits(window.MATRIX_CHART_PAYLOAD || window.MATRIX_PAYLOAD || []);

        if (action === 'toggleGlobalChron') {
            UI_STATE.globalChron = !UI_STATE.globalChron;
            const isChron = UI_STATE.globalChron;
            
            btn.innerHTML = isChron 
                ? `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg> Timeline` 
                : `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg> Index`;
            
            btn.classList.toggle('active', isChron);

            // Boolean indicating if tables/charts can be swapped
            const CHRONO_CAPABLE = ['stack', 'trend', 'conv', 'frag', 'churn', 'blast', 'heat'];
            CHRONO_CAPABLE.forEach(t => {
                UI_STATE[t] = isChron;
                if (['trend', 'frag', 'churn', 'blast'].includes(t)) {
                    const avgKey = t === 'trend' ? 'avgTrend' : 'avg' + t.charAt(0).toUpperCase() + t.slice(1);
                    UI_STATE[avgKey] = isChron ? 2 : 0;
                    const ab = document.querySelector(`button[data-action="cycleAvg"][data-target="${t}"]`);
                    if (ab) { 
                        ab.textContent = `📊 Avg: ${avgModeNames[UI_STATE[avgKey]]}`; 
                        ab.classList.toggle('active', UI_STATE[avgKey] !== 0); 
                    }
                }
            });

            // Batched Redraw
            renderStackChart(payload);
            renderTrendChart(payload);
            renderConvergenceChart(payload);
            renderFragChart(payload);
            renderChurnChart(payload);
            renderBlastChart(payload);
            
            import('../ui/heatmap.js?v=0.1.211').then(m => {
                if (m.renderHeatmap) m.renderHeatmap(payload);
            }).catch(err => console.error("Failed to trigger heatmap redraw", err));
        } else if (action === 'cycleAvg') {
            const avgKey = target === 'trend' ? 'avgTrend' : 'avg' + target.charAt(0).toUpperCase() + target.slice(1);
            UI_STATE[avgKey] = (UI_STATE[avgKey] + 1) % 6;
            btn.textContent = `📊 Avg: ${avgModeNames[UI_STATE[avgKey]]}`;
            btn.classList.toggle('active', UI_STATE[avgKey] !== 0);
            
            if (target === 'trend') renderTrendChart(payload);
            else if (target === 'frag') renderFragChart(payload);
            else if (target === 'churn') renderChurnChart(payload);
            else if (target === 'blast') renderBlastChart(payload);
            else renderAnalytics(payload);
        }
    });
}
