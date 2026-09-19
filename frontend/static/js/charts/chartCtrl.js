const ChartRegistry = new Map();
import { CM_COLORS, BP_AXC_BASE, SC_COLORS, TYPE_COLORS } from '../constants/colors.js?v=0.1.373';
import { calcMAvg, getTop25, processCommits } from '../core/dataEngine.js?v=0.1.373';
import { UI_STATE } from '../core/state.js?v=0.1.373';
import { monthDiv, customTooltip, getXConf, MD_TOP } from './plugins.js?v=0.1.373';

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
});

let charts = {};

const safeDestroy = (chartInstance) => {
    if (!chartInstance) return;
    const cmTt = document.getElementById('cm-tt'); if (cmTt) cmTt.classList.remove('visible');
    const infoTt = document.getElementById('info-tt'); if (infoTt) infoTt.classList.remove('visible');
    
    // Extract canvas ID from the instance if available, to clear the registry
    if (chartInstance.canvas && chartInstance.canvas.id) {
        ChartRegistry.delete(chartInstance.canvas.id);
    }
    
    chartInstance.destroy();
};

// Intercept Chart constructor to populate registry safely BEFORE canvas binding
const OriginalChart = window.Chart;
if (OriginalChart && !window.CM_CHART_INTERCEPTED) {
    window.CM_CHART_INTERCEPTED = true;
    window.Chart = class extends OriginalChart {
        constructor(context, config) {
            // 1. Resolve Canvas ID BEFORE initializing the new chart
            let cid = null;
            if (typeof context === 'string') cid = context;
            else if (context && context.id) cid = context.id;
            else if (context && context.canvas && context.canvas.id) cid = context.canvas.id;
            else if (context && context.length && context[0] && context[0].id) cid = context[0].id;

            // 2. Destroy zombie instances to free the canvas context
            if (cid) {
                // Try native Chart.js v3+ registry first (survives module reloads)
                if (OriginalChart.getChart) {
                    const existing = OriginalChart.getChart(cid);
                    if (existing) { const cmTt = document.getElementById('cm-tt'); if (cmTt) cmTt.classList.remove('visible'); const infoTt = document.getElementById('info-tt'); if (infoTt) infoTt.classList.remove('visible'); existing.destroy(); }
                }
                // Fallback to our local Map registry
                if (typeof ChartRegistry !== 'undefined' && ChartRegistry.has(cid)) {
                    { const cmTt = document.getElementById('cm-tt'); if (cmTt) cmTt.classList.remove('visible'); const infoTt = document.getElementById('info-tt'); if (infoTt) infoTt.classList.remove('visible'); ChartRegistry.get(cid).destroy(); }
                    ChartRegistry.delete(cid);
                }
            }

            // 3. NOW it is safe to bind the new instance
            super(context, config);

            // 4. Register the fresh instance
            if (cid && typeof ChartRegistry !== 'undefined') {
                ChartRegistry.set(cid, this);
            }
        }
    };
}


const ensureRange = (c) => {
    if (c.length > 1) return c;
    if (!c || c.length === 0) return [];
    if (c.length > 1) return c;
    const fake = { ...c[0], ts: c[0].ts - 86400, _fake: true };
    return [fake, c[0]];
};

const def = (c) => ({ clip: false, responsive:true, maintainAspectRatio:false, plugins:{legend:{display:false},tooltip:{enabled:false,external:customTooltip(c)}}, scales:{y:{grid:{color:'rgba(255,255,255,.04)'},ticks:{color:'#7a7874',font:{family:'Satoshi',size:10}}}} });
const defRaw = (c) => ({ clip: false, responsive:true, maintainAspectRatio:false, plugins:{legend:{display:false},tooltip:{enabled:false,external:customTooltip(c)}}, scales:{y:{grid:{color:'rgba(255,255,255,.04)'},ticks:{color:'#7a7874',font:{family:'Satoshi',size:10}}}} });

export function renderTypesChart(rawC) {
    const canvasId = 'cm-c-types';
    let canvasEl = document.getElementById(canvasId);
    if (!canvasEl) return;
    if (!rawC || rawC.length === 0) {
        if (charts.types) { safeDestroy(charts.types); charts.types = null; }
        return;
    }

    const lin = UI_STATE.globalChron;
    const c = lin ? ensureRange(rawC) : rawC;

    if (lin) {
        const sorted = [...c].filter(x => !x._fake).sort((a, b) => a.ts - b.ts);
        const knownTypes = ['feat', 'fix', 'refactor', 'chore', 'test', 'docs', 'perf'];
        
        const runningCounts = {};
        knownTypes.forEach(t => runningCounts[t] = 0);
        let runningTotal = 0;
        
        const dayMap = new Map();
        
        sorted.forEach(x => {
            let t = String(x.p_type || x.t || x.type || "unknown").trim().toLowerCase();
            if (!TYPE_COLORS[t]) {
                const m = t.match(/^([a-z_-]+)/);
                if (m && TYPE_COLORS[m[1]]) t = m[1];
            }
            if (!knownTypes.includes(t)) t = 'chore';
            
            runningCounts[t]++;
            runningTotal++;
            
            const dTs = Math.floor(x.ts / 86400) * 86400;
            dayMap.set(dTs, { ts: dTs, counts: { ...runningCounts }, total: runningTotal });
        });

        const sortedDays = Array.from(dayMap.values()).sort((a, b) => a.ts - b.ts);
        if (sortedDays.length > 0 && c.length > 0) {
            const minTs = Math.min(...c.map(x => x.ts));
            const maxTs = Math.max(...c.map(x => x.ts));
            // Prevent first snapshot from rendering before t0 (Bug B fix)
            if (sortedDays[0].ts < minTs) {
                sortedDays[0].ts = minTs;
            }
            const lastDay = sortedDays[sortedDays.length - 1];
            if (maxTs > lastDay.ts) {
                sortedDays.push({ ...lastDay, ts: maxTs });
            }
        }

        const datasets = knownTypes.map((t, tIdx) => ({
            label: t,
            data: [],
            backgroundColor: (ctx) => {
                const base = TYPE_COLORS[t] || '#888888';
                const hoverIdx = ctx.chart ? (ctx.chart._hoverDatasetIndex ?? -1) : -1;
                if (hoverIdx === -1) return base + '80';
                return hoverIdx === ctx.datasetIndex ? base + 'cc' : base + '33';
            },
            borderColor: (ctx) => {
                const base = TYPE_COLORS[t] || '#888888';
                const hoverIdx = ctx.chart ? (ctx.chart._hoverDatasetIndex ?? -1) : -1;
                if (hoverIdx === -1) return base;
                return hoverIdx === ctx.datasetIndex ? base : base + '40';
            },
            borderWidth: 1.5,
            pointRadius: 0,
            fill: tIdx === 0 ? 'origin' : '-1',
            tension: 0.4
        }));

        sortedDays.forEach(day => {
            datasets.forEach(ds => {
                ds.data.push({
                    x: day.ts,
                    y: day.total > 0 ? ((day.counts[ds.label] || 0) / day.total) * 100 : 0,
                    _count: day.counts[ds.label] || 0
                });
            });
        });

        const activeDs = datasets
            .filter(ds => ds.data.some(d => d && d.y > 0))
            .map((ds, i) => ({ ...ds, fill: i > 0 ? '-1' : 'origin' }));
        charts.types = new Chart(canvasEl, {
            type: 'line', data: { datasets: activeDs },
            options: {
                ...def(c), 
                onHover: (e, elements, chart) => {
                    const mouseY = window._cmMouseY - chart.canvas.getBoundingClientRect().top;
                    let activeDs = -1;
                    if (elements.length > 0) {
                        const valid = elements.filter(el => el.element && el.element.y !== undefined);
                        if (valid.length) activeDs = valid.reduce((p, curr) => Math.abs(curr.element.y - mouseY) < Math.abs(p.element.y - mouseY) ? curr : p).datasetIndex;
                    }
                    if (chart._hoverDatasetIndex !== activeDs) { chart._hoverDatasetIndex = activeDs; chart.update(); }
                },
                interaction: { mode: 'index', intersect: false }, 
                layout: { padding: { top: MD_TOP, right: 4, left: 0 } },
                scales: { 
                    x: getXConf(true, c, UI_STATE.dateFilter?.end, 'types'), 
                    y: { ...def(c).scales.y, min: 0, max: 100, stacked: true, ticks: { ...def(c).scales.y.ticks, callback: v => v + '%' } }
                }
            }, plugins: [monthDiv(c)]
        });
    } else {
        const tc = {};
        c.forEach(x => {
            let type = String(x.p_type || x.t || x.type || "unknown").trim().toLowerCase();
            if (!TYPE_COLORS[type]) { const m = type.match(/^([a-z_-]+)/); if (m && TYPE_COLORS[m[1]]) type = m[1]; }
            tc[type] = (tc[type] || 0) + 1;
        });
        const types = Object.keys(tc).sort((a, b) => tc[b] - tc[a]);
        const bgColors = types.map(t => TYPE_COLORS[t] || '#888888');

        charts.types = new Chart(canvasEl, {
            type: 'bar',
            data: { labels: types, datasets: [{ data: types.map(t => tc[t]), backgroundColor: (ctx) => {
                const base = bgColors[ctx.dataIndex] || '#888888';
                if (ctx.type !== 'data') return base; 
                const hoverIdx = ctx.chart ? (ctx.chart._hoverDataIndex ?? -1) : -1;
                return (hoverIdx !== -1 && hoverIdx !== ctx.dataIndex) ? base + '33' : base;
            }, borderWidth: 0, borderRadius: 4 }] },
            options: { 
                responsive: true, maintainAspectRatio: false, indexAxis: 'y', 
                onHover: (e, elements, chart) => {
                    const activeIdx = elements.length > 0 ? elements[0].index : -1;
                    if (chart._hoverDataIndex !== activeIdx) { chart._hoverDataIndex = activeIdx; chart.update(); }
                },
                plugins: { legend: { display: false }, tooltip: { enabled: false, external: customTooltip(c) } }, 
                scales: { x: { grid: { color: 'rgba(255,255,255,.04)' } }, y: { grid: { color: 'rgba(255,255,255,.04)' } } } 
            }
        });
    }
}

export function renderStackChart(rawC) {
    if (!rawC || rawC.length === 0) {
        if (charts.stack) { safeDestroy(charts.stack); charts.stack = null; }
        return;
    }
    const lin=UI_STATE.stack; 
    const c = lin ? ensureRange(rawC) : rawC; 
    const mk=(ax)=>c.map(x=>lin?{x:x.ts,y:x._fake?null:x[ax]}:x[ax]);
    const allVals = c.map(x=>x.tot).filter(v=>typeof v==='number'&&!isNaN(v)&&isFinite(v));
    const maxVal = allVals.length ? Math.max(...allVals) : 16;
    const sMax = maxVal + 1;
    
    charts.stack = new Chart('cm-c-stack',{
        type:'bar',
        data:{
            labels:lin?undefined:c.map(x=>`#${x.n}`),
            datasets:(window.CM_ACTIVE_AXES || ['C','O','R','D']).map((ax, i) => ({ 
                label: ax, 
                data: mk(ax), 
                backgroundColor: (ctx) => {
                    const hexColors = ['#5c91e0', '#c99ef0', '#ffb84d', '#ff4b4b', '#4caf50', '#00bcd4'];
                    const base = hexColors[i % hexColors.length];
                    const hoverIdx = ctx.chart ? ctx.chart._lastActiveIndex : -1;
                    if (hoverIdx !== undefined && hoverIdx !== -1) {
                        return ctx.dataIndex === hoverIdx ? base : base + '40';
                    }
                    return base + (lin ? 'ee' : ''); 
                }, 
                stack: 's', 
                barThickness: lin ? 6 : undefined, 
                categoryPercentage: lin ? undefined : 1.0, 
                barPercentage: lin ? undefined : 1.0 
            }))
        },
        options:{
            ...defRaw(c),
            layout:{padding:{top: lin ? MD_TOP : 6, right: 4, left: 0}},
            scales:{
                x:{...getXConf(lin, c, UI_STATE.dateFilter?.end),stacked:true},
                y:{...defRaw(c).scales.y,stacked:true,min:0,max:sMax,ticks:{...(defRaw(c).scales.y.ticks||{}),stepSize:4}}
            }
        },
        plugins:lin?[monthDiv(c)]:[]
    });
}

export function renderTrendChart(rawC) {
    if (!rawC || rawC.length === 0) {
        if (charts.trend) { safeDestroy(charts.trend); charts.trend = null; }
        return;
    }
    const sortedRaw = [...rawC].sort((a, b) => (a.ts || 0) - (b.ts || 0));
    const lin=UI_STATE.trend; const c = lin ? ensureRange(sortedRaw) : sortedRaw;
    const isAvgOff = UI_STATE.avgTrend === 0;
    
    if (!isAvgOff) UI_STATE._lastAvgTrend = UI_STATE.avgTrend;
    const simMode = isAvgOff ? (UI_STATE._lastAvgTrend || 1) : UI_STATE.avgTrend;
    const avgRaw = calcMAvg(c.map(x=>x.tot), simMode, c, lin);
    const avg = isAvgOff ? avgRaw.map(v => typeof v === 'object' && v !== null ? { ...v, y: 0 } : 0) : avgRaw;
    
    const mk = (tr) => c.map((x, i) => {
        const jY = Math.sin((x.h ? x.h.charCodeAt(0) + x.h.charCodeAt(1) : i) * 12.3) * 0.25;
        if (tr && x.tier !== tr) return lin ? {x: x.ts, y: null} : null;
        if (x._fake) return lin ? {x: x.ts, y: null} : null;
        return lin ? {x: x.ts, y: x.tot + jY} : (x.tot + jY);
    });
    
    const rawVals = c.map(x=>x.tot).filter(v=>typeof v==='number'&&!isNaN(v)&&isFinite(v));
    let tMin = rawVals.length ? Math.max(0, Math.floor(Math.min(...rawVals) - 1)) : 0;
    if (tMin % 2 !== 0) tMin = Math.max(0, tMin - 1);
    let maxVal = rawVals.length ? Math.max(...rawVals) : 16;
    let tMax = maxVal + 1;
    if (tMax % 2 !== 0) tMax += 1;

    if (charts.trend && document.getElementById('cm-c-trend')) {
        const curType = (charts.trend.options?.scales?.x?.type) || (charts.trend.scales?.x?.type) || 'unknown';
        const newType = lin ? 'linear' : 'category';
        if (curType === newType) {
            charts.trend.data.labels = lin ? undefined : c.map(x => `#${x.n}`);
            charts.trend.data.datasets[0].data = avg;
            charts.trend.data.datasets[0].borderWidth = isAvgOff ? 0 : 2.5;
            charts.trend.data.datasets[1].data = mk('Pivotal');
            charts.trend.data.datasets[2].data = mk('Core');
            charts.trend.data.datasets[3].data = mk('Minor');
            charts.trend.options.scales.x = getXConf(lin, c);
            charts.trend.options.scales.y.min = tMin;
            charts.trend.options.scales.y.max = tMax;
            if (charts.trend.options.scales.y.ticks) charts.trend.options.scales.y.ticks.stepSize = 2;
            
            charts.trend._cmCommits = c; 
            charts.trend._cmLin = lin;
            charts.trend.update(); 
            return;
        }
        }

    const getGrad = (ctx, ca, y, alpha, isF) => {
        if (!ca || !y || typeof y.getPixelForValue !== 'function') return 'transparent';
        const top = ca.top, h = ca.bottom - top;
        const gSt = (v) => Math.max(0, Math.min(1, (y.getPixelForValue(v) - top) / h));
        
        const s13 = gSt(12.5), s9 = gSt(8.5);
        const g = ctx.createLinearGradient(0, top, 0, ca.bottom);
        
        const cP = `rgba(212, 59, 198, ${alpha})`;
        const cC = `rgba(54, 184, 216, ${alpha})`;
        const cM = `rgba(111, 129, 151, ${alpha})`;
        
        g.addColorStop(0, cP);
        g.addColorStop(Math.max(0, s13 - 0.05), cP); 
        g.addColorStop(Math.min(1, s13 + 0.1), cC);
        g.addColorStop(Math.max(0, s9 - 0.05), cC);
        
        if (isF) {
            g.addColorStop(Math.min(1, s9 + 0.1), `rgba(111, 129, 151, ${alpha * 0.4})`);
            g.addColorStop(1, 'rgba(0, 0, 0, 0)');
        } else {
            g.addColorStop(Math.min(1, s9 + 0.1), cM);
            g.addColorStop(1, cM);
        }
        return g;
    };

    charts.trend = new Chart('cm-c-trend',{
        type:'line',
        data:{
            labels:lin?undefined:c.map(x=>`#${x.n}`),
            datasets:[
                {
                    label:'Avg',
                    data:avg,
                    borderWidth: isAvgOff ? 0 : 2.5,
                    pointRadius:0,
                    pointHitRadius:0,
                    hoverRadius:0,
                    fill:true,
                    tension:0.4,
                    showLine:true,
                    borderColor: (c) => {
                        if (!c.chart.chartArea) return null;
                        const hoverDs = c.chart._hoverDatasetIndex ?? -1;
                        // Dim border to 0.35 if hovering a specific tier, otherwise normal 1.0
                        const alpha = (hoverDs > 0) ? 0.35 : 1.0;
                        return getGrad(c.chart.ctx, c.chart.chartArea, c.chart.scales.y, alpha, false);
                    },
                    backgroundColor: (c) => {
                        if (!c.chart.chartArea) return null;
                        const hoverDs = c.chart._hoverDatasetIndex ?? -1;
                        // Dim gradient fill to 0.15 if hovering a specific tier, otherwise normal 0.70
                        const alpha = (hoverDs > 0) ? 0.15 : 0.70;
                        return getGrad(c.chart.ctx, c.chart.chartArea, c.chart.scales.y, alpha, true);
                    }
                },
                {
                    label:'Pivotal',
                    data:mk('Pivotal'),
                    borderColor:'transparent',
                    animation: false,
                    pointBackgroundColor: (ctx) => {
                        const base = CM_COLORS.Pivotal || '#D43BC6';
                        const hoverDs = ctx.chart ? (ctx.chart._hoverDatasetIndex ?? -1) : -1;
                        if (hoverDs === -1) return base;
                        return hoverDs === ctx.datasetIndex ? base : base + '33';
                    },
                    pointRadius: (ctx) => {
                        const hoverDs = ctx.chart ? (ctx.chart._hoverDatasetIndex ?? -1) : -1;
                        if (hoverDs === -1) return 8;
                        return hoverDs === ctx.datasetIndex ? 9 : 4;
                    },
                    pointHitRadius:12,
                    showLine:false
                },
                {
                    label:'Core',
                    data:mk('Core'),
                    borderColor:'transparent',
                    animation: false,
                    pointBackgroundColor: (ctx) => {
                        const base = CM_COLORS.Core || '#36B8D8';
                        const hoverDs = ctx.chart ? (ctx.chart._hoverDatasetIndex ?? -1) : -1;
                        if (hoverDs === -1) return base;
                        return hoverDs === ctx.datasetIndex ? base : base + '33';
                    },
                    pointRadius: (ctx) => {
                        const hoverDs = ctx.chart ? (ctx.chart._hoverDatasetIndex ?? -1) : -1;
                        if (hoverDs === -1) return 5;
                        return hoverDs === ctx.datasetIndex ? 6 : 3;
                    },
                    pointHitRadius:10,
                    showLine:false
                },
                {
                    label:'Minor',
                    data:mk('Minor'),
                    borderColor:'transparent',
                    animation: false,
                    pointBackgroundColor: (ctx) => {
                        const base = CM_COLORS.Minor || '#6F8197';
                        const hoverDs = ctx.chart ? (ctx.chart._hoverDatasetIndex ?? -1) : -1;
                        if (hoverDs === -1) return base;
                        return hoverDs === ctx.datasetIndex ? base : base + '33';
                    },
                    pointRadius: (ctx) => {
                        const hoverDs = ctx.chart ? (ctx.chart._hoverDatasetIndex ?? -1) : -1;
                        if (hoverDs === -1) return 3;
                        return hoverDs === ctx.datasetIndex ? 4 : 2;
                    },
                    pointHitRadius:8,
                    showLine:false
                }
            ]
        },
        options:{
            ...def(c),
            onHover: (e, elements, chart) => {
                let activeDs = -1;
                if (elements.length > 0) {
                    activeDs = elements[0].datasetIndex;
                }
                if (chart._hoverDatasetIndex !== activeDs) {
                    chart._hoverDatasetIndex = activeDs;
                    chart.update();
                }
            },
            interaction:{mode:'nearest',intersect:true},
            animations:{x:{duration:0}},
            layout:{padding:{top: lin ? MD_TOP : 6, right: 4, left: 0}},
            scales:{x:getXConf(lin, c, UI_STATE.dateFilter?.end),y:{...def(c).scales.y,min:tMin,max:tMax,ticks:{...(def(c).scales.y.ticks||{}),stepSize:2}}}
        },
        plugins:lin?[monthDiv(c)]:[]
    });
    charts.trend._cmCommits = c;
    charts.trend.update("none");
}

function buildCombo(id, stKey, avgKey, rawC, dFunc, clr) {
    if (!rawC || rawC.length === 0) {
        if (charts[stKey]) { safeDestroy(charts[stKey]); charts[stKey] = null; }
        return;
    }
    const lin=UI_STATE[stKey]; const c = lin ? ensureRange(rawC) : rawC;
    const avg=calcMAvg(c.map(dFunc),UI_STATE[avgKey],c,lin);
    const rawVals = c.map(dFunc).filter(v=>typeof v==='number'&&!isNaN(v)&&isFinite(v));
    const avgVals = avg.map(v=>typeof v==='object'&&v!==null?v.y:v).filter(v=>typeof v==='number'&&!isNaN(v)&&isFinite(v));
    const allVals = rawVals.concat(avgVals);
    const cMin = allVals.length ? Math.max(0, Math.floor(Math.min(...allVals) - 1)) : 0;
    const cMax = allVals.length ? Math.ceil(Math.max(...allVals) + 1) : 10;
    charts[stKey] = new Chart(id,{type:'bar',data:{labels:lin?undefined:c.map(x=>`#${x.n}`),datasets:[{type:'line',data:avg,borderColor:'rgba(79,152,163,0.8)',borderWidth:1.5,pointRadius:0,tension:0.3},{type:'bar',data:c.map(x=>lin?{x:x.ts,y:x._fake?null:dFunc(x)}:dFunc(x)),backgroundColor:clr,borderRadius:2,barThickness:lin?4:undefined}]},options:{...def(c),interaction:{mode:'index',intersect:false},layout:{padding:{top: lin ? MD_TOP : 6, right: 4, left: 0}},scales:{x:getXConf(lin, c, UI_STATE.dateFilter?.end),y:{...def(c).scales.y,min:cMin,max:cMax}}},plugins:lin?[monthDiv(c)]:[]});
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

export function renderRiskCharts(c) {
    renderFragChart(c);
    renderChurnChart(c);
    renderBlastChart(c);
}

export function renderConvergenceChart(rawC) {
    if (!rawC || rawC.length === 0) {
        if (charts.conv) { safeDestroy(charts.conv); charts.conv = null; }
        return;
    }
    const lin=UI_STATE.conv; const c = lin ? ensureRange(rawC) : rawC;
    const f=c.map(x=>((x[(window.CM_ACTIVE_AXES || ['C','O','R','D'])[0]] || 0)+(x[(window.CM_ACTIVE_AXES || ['C','O','R','D'])[2]] || 0))/((x[(window.CM_ACTIVE_AXES || ['C','O','R','D'])[3]] || 0)||1)), ch=c.map(x=>(x[(window.CM_ACTIVE_AXES || ['C','O','R','D'])[0]] || 0)/((x[(window.CM_ACTIVE_AXES || ['C','O','R','D'])[1]] || 0)||1)), b=c.map(x => { const a = window.CM_ACTIVE_AXES || ['C','O','R','D']; return (x[a[0]] || 1) * (x[a[2] || a[1]] || 1); }); const fT=getTop25(f), cT=getTop25(ch), bT=getTop25(b);
    const nd=c.map((x,i)=>{ const h=(f[i]>=fT?1:0)+(ch[i]>=cT?1:0)+(b[i]>=bT?1:0); if(h>=2&&x.tot>0){const m=Math.max(f[i],ch[i],b[i]);return lin?{x:x.ts,y:x._fake?null:m+1}:m+1;} return lin?{x:x.ts,y:null}:null; });
    const allVals = f.concat(ch, b).filter(v=>typeof v==='number'&&!isNaN(v)&&isFinite(v));
    const cvMin = allVals.length ? Math.max(0, Math.floor(Math.min(...allVals) - 1)) : 0;
    const cvMax = allVals.length ? Math.ceil(Math.max(...allVals) + 1) : 10;
    charts.conv = new Chart('cm-c-conv',{type:'line',data:{labels:lin?undefined:c.map(x=>`#${x.n}`),datasets:[{label:'Node',data:nd,type:'scatter',pointBackgroundColor:c.map(x=>SC_COLORS['t_'+x.scope]||'#fff'),pointBorderColor:'rgba(255,255,255,0.8)',pointBorderWidth:2,pointRadius:6},{label:'Frag',data:c.map((x,i)=>lin?{x:x.ts,y:x._fake?null:f[i]}:f[i]),borderColor:'rgba(255, 75, 75, 0.4)',backgroundColor:'rgba(255, 75, 75, 0.05)',borderWidth:1,fill:true,tension:0.4,pointRadius:0},{label:'Churn',data:c.map((x,i)=>lin?{x:x.ts,y:x._fake?null:ch[i]}:ch[i]),borderColor:'rgba(201, 158, 240, 0.4)',backgroundColor:'rgba(201, 158, 240, 0.05)',borderWidth:1,fill:true,tension:0.4,pointRadius:0},{label:'Blast',data:c.map((x,i)=>lin?{x:x.ts,y:x._fake?null:b[i]}:b[i]),borderColor:'rgba(255, 184, 77, 0.4)',backgroundColor:'rgba(255, 184, 77, 0.05)',borderWidth:1,fill:true,tension:0.4,pointRadius:0}]},options:{...def(c),interaction:{mode:'index',intersect:false},layout:{padding:{top: lin ? MD_TOP : 6, right: 4, left: 0}},scales:{x:getXConf(lin, c, UI_STATE.dateFilter?.end),y:{...def(c).scales.y,min:cvMin,max:cvMax}}},plugins:lin?[monthDiv(c)]:[]});
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

    setVal('cm-kp', totalCommits, '#d9d8d5');
    setVal('cm-kc', counts.Pivotal, counts.Pivotal > 0 ? CM_COLORS.Pivotal : '#7a7874');
    setVal('cm-ks', counts.Core, counts.Core > 0 ? CM_COLORS.Core : '#7a7874');
    setVal('cm-kr', counts.Minor, counts.Minor > 0 ? CM_COLORS.Minor : '#7a7874');

    let avgColor = CM_COLORS.Minor;
    if (avgScore >= 13) avgColor = CM_COLORS.Pivotal;
    else if (avgScore >= 9) avgColor = CM_COLORS.Core;

    setVal('cm-ka', avgScore.toFixed(1), totalCommits > 0 ? avgColor : '#7a7874');
}

export function renderTierChart(rawC) {
    // updateKPIs(rawC); // Delegated completely to paintKPIs in app.js
    if (!rawC || rawC.length === 0) {
        if (charts.tier) { safeDestroy(charts.tier); charts.tier = null; }
        return;
    }
    const lin = UI_STATE.globalChron;
    const c = lin ? ensureRange(rawC) : rawC;

    const counts = { Pivotal: 0, Core: 0, Minor: 0 };
    rawC.forEach(x => { if(counts[x.tier] !== undefined) counts[x.tier]++; });

    if (lin) {
        const dp = [], dc = [], dm = [];
        let curP = 0, curC = 0, curM = 0;
        let validCount = 0;
        
        const sorted = [...c].sort((a, b) => a.ts - b.ts);
        const dayMap = new Map();
        
        sorted.forEach(x => {
            if (!x._fake) {
                if (x.tier === 'Pivotal') curP++;
                else if (x.tier === 'Core') curC++;
                else if (x.tier === 'Minor') curM++;
                validCount++;
            }
            const dTs = Math.floor(x.ts / 86400) * 86400;
            dayMap.set(dTs, { x: dTs, p: curP, c: curC, m: curM, fake: x._fake });
        });
        
        const sortedDays = Array.from(dayMap.values()).sort((a, b) => a.x - b.x);
        if (sortedDays.length > 0 && c.length > 0) {
            const minTs = Math.min(...c.map(x => x.ts));
            const maxTs = Math.max(...c.map(x => x.ts));
            // Prevent first snapshot from rendering before t0 (Bug B fix)
            if (sortedDays[0].x < minTs) {
                sortedDays[0].x = minTs;
            }
            const lastDay = sortedDays[sortedDays.length - 1];
            if (maxTs > lastDay.x) {
                sortedDays.push({ ...lastDay, x: maxTs });
            }
        }
        
        sortedDays.forEach(d => {
            dp.push({ x: d.x, y: d.fake ? null : d.p });
            dc.push({ x: d.x, y: d.fake ? null : d.c });
            dm.push({ x: d.x, y: d.fake ? null : d.m });
        });

        const tiersInfo = [
            { label: 'Minor', data: dm, color: CM_COLORS.Minor || '#6F8197' },
            { label: 'Core', data: dc, color: CM_COLORS.Core || '#36B8D8' },
            { label: 'Pivotal', data: dp, color: CM_COLORS.Pivotal || '#D43BC6' }
        ];

        const ds = tiersInfo.map((tInfo, tIdx) => ({
            label: tInfo.label,
            data: tInfo.data,
            backgroundColor: (ctx) => {
                const base = tInfo.color;
                const hoverIdx = ctx.chart ? (ctx.chart._hoverDatasetIndex ?? -1) : -1;
                if (hoverIdx === -1) return base + '80';
                return hoverIdx === ctx.datasetIndex ? base + 'cc' : base + '33';
            },
            borderColor: (ctx) => {
                const base = tInfo.color;
                const hoverIdx = ctx.chart ? (ctx.chart._hoverDatasetIndex ?? -1) : -1;
                if (hoverIdx === -1) return base;
                return hoverIdx === ctx.datasetIndex ? base : base + '40';
            },
            borderWidth: 1.5,
            pointRadius: 0,
            fill: tIdx === 0 ? 'origin' : '-1',
            tension: 0.4
        }));

        charts.tier = new Chart('cm-c-tier', {
            type: 'line',
            data: { datasets: ds },
            options: { 
                ...def(c), 
                onHover: (e, elements, chart) => {
                    const mouseY = window._cmMouseY - chart.canvas.getBoundingClientRect().top;
                    let activeDs = -1;
                    if (elements.length > 0) {
                        const valid = elements.filter(el => el.element && el.element.y !== undefined);
                        if (valid.length) activeDs = valid.reduce((p, curr) => Math.abs(curr.element.y - mouseY) < Math.abs(p.element.y - mouseY) ? curr : p).datasetIndex;
                    }
                    if (chart._hoverDatasetIndex !== activeDs) { chart._hoverDatasetIndex = activeDs; chart.update(); }
                },
                interaction: { mode: 'index', intersect: false }, 
                layout: { padding: { top: MD_TOP, right: 4, left: 0 } }, 
                scales: { 
                    x: getXConf(true, c, UI_STATE.dateFilter?.end, 'types'), 
                    y: { 
                        ...def(c).scales.y, 
                        min: 0, 
                        max: validCount || undefined, 
                        stacked: true 
                    } 
                } 
            },
            plugins: [monthDiv(c)]
        });
    } else {
        charts.tier = new Chart('cm-c-tier', {
            type: 'doughnut',
            data: {
                labels: ['Pivotal', 'Core', 'Minor'],
                datasets: [{
                    data: [counts.Pivotal, counts.Core, counts.Minor],
                    backgroundColor: [CM_COLORS.Pivotal || '#D43BC6', CM_COLORS.Core || '#36B8D8', CM_COLORS.Minor || '#6F8197'],
                    borderWidth: 0, hoverOffset: 4
                }]
            },
            options: { responsive: true, maintainAspectRatio: false, cutout: '70%', plugins: { legend: { display: false }, tooltip: { enabled: false, external: customTooltip(c) } } }
        });
    }
}

const avgModeNames = ['Off', 'Trailing', 'Daily Peak', 'Daily Median', 'Vol-Weighted', 'High-Water'];

if (!window._cmChartBindingsReady) {
    window._cmChartBindingsReady = true;
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('button[data-action]');
        if (!btn) return;
        
        const action = btn.getAttribute('data-action');
        const target = btn.getAttribute('data-target');
        if (!['toggleChron', 'cycleAvg', 'toggleGlobalChron'].includes(action)) return;

        const payload = window.CM_CURRENT_FILTERED_PAYLOAD || window.MATRIX_CHART_PAYLOAD || window.MATRIX_PAYLOAD || [];

        if (action === 'toggleGlobalChron') {
            UI_STATE.globalChron = !UI_STATE.globalChron;
            const isChron = UI_STATE.globalChron;

            btn.innerHTML = isChron 
                ? `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="display:inline-block; vertical-align:-2px;"><circle cx="5" cy="12" r="4"/><path d="M5 9v3h1.5M9 12h1.5M13.5 12h1M17.5 12h3"/><circle cx="12" cy="12" r="1.5"/><circle cx="16" cy="12" r="1.5"/><circle cx="22" cy="12" r="1.5"/></svg>Timeline` 
                : `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="display:inline-block; vertical-align:-2px;"><path d="M2 18h2M8 18h2M14 18h2M20 18h2"/><circle cx="6" cy="18" r="2"/><circle cx="12" cy="18" r="2"/><circle cx="18" cy="18" r="2"/><rect x="4" y="4" width="4" height="10" rx="2"/><rect x="10" y="4" width="4" height="10" rx="2"/><rect x="16" y="4" width="4" height="10" rx="2"/></svg>Index`;

            btn.classList.toggle('active', isChron);

            const CHRONO_CAPABLE = ['stack', 'trend', 'conv', 'frag', 'churn', 'blast', 'heat', 'types', 'tier'];
            CHRONO_CAPABLE.forEach(t => {
                UI_STATE[t] = isChron;
                if (['trend', 'frag', 'churn', 'blast'].includes(t)) {
                    const avgKey = t === 'trend' ? 'avgTrend' : 'avg' + t.charAt(0).toUpperCase() + t.slice(1);
                    UI_STATE[avgKey] = isChron ? 2 : 0;
                    const ab = document.querySelector(`button[data-action="cycleAvg"][data-target="${t}"]`);
                    if (ab) { 
                        ab.innerHTML = `<svg width="14" height="14" viewBox="0 0 32 32" fill="currentColor" style="display:inline-block; vertical-align:-2px; margin-right:4px;"><path d="M23,24c-3.5991,0-5.0293-4.1758-6.4126-8.2139C15.2764,11.9583,13.92,8,11,8a3.44,3.44,0,0,0-3.0532,2.3215L6.0513,9.6838C6.1016,9.5334,7.3218,6,11,6c4.3491,0,6.0122,4.8547,7.48,9.1379C19.6885,18.6667,20.83,22,23,22a3.44,3.44,0,0,0,3.0532-2.3215l1.8955.6377C27.8984,20.4666,26.6782,24,23,24Z"/><path d="M4,28V17H6V15H4V2H2V28a2,2,0,0,0,2,2H30V28Z"/><rect x="8" y="15" width="2" height="2"/><rect x="12" y="15" width="2" height="2"/><rect x="20" y="15" width="2" height="2"/><rect x="24" y="15" width="2" height="2"/><rect x="28" y="15" width="2" height="2"/></svg> ${avgModeNames[UI_STATE[avgKey]]}`; 
                        ab.classList.toggle('active', UI_STATE[avgKey] !== 0); 
                    }
                }
            });

            renderStackChart(payload);
            renderTrendChart(payload);
            renderConvergenceChart(payload);
            renderFragChart(payload);
            renderChurnChart(payload);
            renderBlastChart(payload);
            renderTierChart(payload);
            renderTypesChart(payload);

            let ver = "0.1.309"; 
            try { ver = window.location.href.match(/v=([0-9\.]+)/)[1]; } catch(e){}
            import(`../ui/heatmap.js?v=${ver}`).then(m => {
                if (m.renderHeatmap) m.renderHeatmap(payload);
            }).catch(err => console.error("Failed to trigger heatmap redraw", err));

        } else if (action === 'cycleAvg') {
            const avgKey = target === 'trend' ? 'avgTrend' : 'avg' + target.charAt(0).toUpperCase() + target.slice(1);
            UI_STATE[avgKey] = (UI_STATE[avgKey] + 1) % 6;
            btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 32 32" fill="currentColor" style="display:inline-block; vertical-align:-2px; margin-right:4px;"><path d="M23,24c-3.5991,0-5.0293-4.1758-6.4126-8.2139C15.2764,11.9583,13.92,8,11,8a3.44,3.44,0,0,0-3.0532,2.3215L6.0513,9.6838C6.1016,9.5334,7.3218,6,11,6c4.3491,0,6.0122,4.8547,7.48,9.1379C19.6885,18.6667,20.83,22,23,22a3.44,3.44,0,0,0,3.0532-2.3215l1.8955.6377C27.8984,20.4666,26.6782,24,23,24Z"/><path d="M4,28V17H6V15H4V2H2V28a2,2,0,0,0,2,2H30V28Z"/><rect x="8" y="15" width="2" height="2"/><rect x="12" y="15" width="2" height="2"/><rect x="20" y="15" width="2" height="2"/><rect x="24" y="15" width="2" height="2"/><rect x="28" y="15" width="2" height="2"/></svg> ${avgModeNames[UI_STATE[avgKey]]}`;
            btn.classList.toggle('active', UI_STATE[avgKey] !== 0);

            if (target === 'trend') renderTrendChart(payload);
            else if (target === 'frag') renderFragChart(payload);
            else if (target === 'churn') renderChurnChart(payload);
            else if (target === 'blast') renderBlastChart(payload);
            else renderRiskCharts(payload);
        }
    });
}

if (typeof window !== 'undefined' && window.Chart) {
    window.Chart.register({
        id: 'cmSafeHover',
        afterEvent(chart, args) {
            const e = args.event;
            if (e.type === 'mouseout' || e.type === 'mouseleave') {
                let changed = false;
                if (chart._hoverDatasetIndex !== undefined && chart._hoverDatasetIndex !== -1) {
                    chart._hoverDatasetIndex = -1;
                    changed = true;
                }
                if (chart._hoverDataIndex !== undefined && chart._hoverDataIndex !== -1) {
                    chart._hoverDataIndex = -1;
                    changed = true;
                }
                if (changed) chart.update();
            }

            if (chart.canvas.id === 'cm-c-stack') {
                const active = chart.getActiveElements();
                const activeIndex = active.length > 0 ? active[0].index : -1;
                if (chart._lastActiveIndex !== activeIndex) {
                    chart._lastActiveIndex = activeIndex;
                    chart.update();
                }
            }
        },
        beforeUpdate(chart) {
            if (chart.canvas.id === 'cm-c-trend') {
                chart.data.datasets.forEach(ds => {
                    const orig = ds.pointRadius || ds.radius || 4;
                    ds.pointHoverRadius = (ctx) => {
                        let r = typeof orig === 'function' ? orig(ctx) : orig;
                        return (typeof r === 'number' ? r : 4) + 3;
                    };
                    ds.hoverRadius = ds.pointHoverRadius;
                });
            }
        }
    });
}
