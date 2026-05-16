import { CM_COLORS, BP_AXC, BP_AXC_BASE } from '../core/constants.js';
import { fmtChartDate, calculateMovingAverage } from '../core/dataEngine.js';

const CHART_DEFAULTS = {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
        x: { grid: { color: 'rgba(255,255,255,.04)' }, ticks: { color: '#7a7874', font: { family: 'Satoshi', size: 10 } } },
        y: { grid: { color: 'rgba(255,255,255,.04)' }, ticks: { color: '#7a7874', font: { family: 'Satoshi', size: 10 } } }
    }
};

export function renderTypesChart(commits) {
    const ctx = document.getElementById('cm-c-types');
    if (!ctx || !commits.length) return;
    
    const tc = {}; 
    commits.forEach(c => tc[c.t] = (tc[c.t] || 0) + 1);
    const types = Object.keys(tc).sort((a,b) => tc[b] - tc[a]);
    const clr = {feat:'#5c91e0', fix:'#ff4b4b', perf:'#c99ef0', refactor:'#8ed068', chore:'#aaa', docs:'#ffa726', test:'#00bcd4', style:'#fce83a'};
    
    new Chart(ctx, { 
        type: 'bar', 
        data: {
            labels: types, 
            datasets: [{ data: types.map(t => tc[t]), backgroundColor: types.map(t => clr[t] || '#888'), borderRadius: 4 }]
        }, 
        options: { ...CHART_DEFAULTS, indexAxis: 'y', scales: { x: { ...CHART_DEFAULTS.scales.x, beginAtZero: true }, y: CHART_DEFAULTS.scales.y } } 
    });
}

export function renderStackChart(commits) {
    const ctx = document.getElementById('cm-c-stack');
    if (!ctx || !commits.length) return;

    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: commits.map(c => `#${c.n}`),
            datasets: [
                { label: 'C', data: commits.map(c=>c.C), backgroundColor: BP_AXC_BASE[0], hoverBackgroundColor: BP_AXC[0], stack: 's' },
                { label: 'I', data: commits.map(c=>c.I), backgroundColor: BP_AXC_BASE[1], hoverBackgroundColor: BP_AXC[1], stack: 's' },
                { label: 'R', data: commits.map(c=>c.R), backgroundColor: BP_AXC_BASE[2], hoverBackgroundColor: BP_AXC[2], stack: 's' },
                { label: 'S', data: commits.map(c=>c.S), backgroundColor: BP_AXC_BASE[3], hoverBackgroundColor: BP_AXC[3], stack: 's' },
                { label: 'D', data: commits.map(c=>c.D), backgroundColor: BP_AXC_BASE[4], hoverBackgroundColor: BP_AXC[4], stack: 's' }
            ]
        },
        options: { ...CHART_DEFAULTS, interaction: { mode: 'index', intersect: false }, scales: { x: { stacked: true, grid: { color: 'rgba(255,255,255,.04)' }, ticks: { color: '#7a7874' } }, y: { stacked: true, max: 16, grid: { color: 'rgba(255,255,255,.04)' }, ticks: { color: '#7a7874' } } } }
    });
}

export function renderTrendChart(commits) {
    const ctx = document.getElementById('cm-c-trend');
    if (!ctx || !commits.length) return;

    // Moving average (Trailing 5)
    const rawData = commits.map(c => c.tot);
    const trailAvg = calculateMovingAverage(rawData, 1, commits, false);

    new Chart(ctx, {
        type: 'line',
        data: {
            labels: commits.map(c => `#${c.n}`),
            datasets: [
                { label: 'Avg', data: trailAvg, borderColor: 'rgba(79,152,163,0.85)', borderWidth: 2, pointRadius: 0, fill: false, tension: 0.4 },
                { label: 'Score', data: rawData, borderColor: 'rgba(200,200,210,.18)', borderWidth: 1.5, pointRadius: 4, pointBackgroundColor: commits.map(c => CM_COLORS[c.tier] || '#fff'), fill: false, tension: 0 }
            ]
        },
        options: { ...CHART_DEFAULTS, scales: { x: CHART_DEFAULTS.scales.x, y: { ...CHART_DEFAULTS.scales.y, min: 0, max: 16 } } }
    });
}
