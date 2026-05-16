import { processCommits } from './core/dataEngine.js?v=2';
import { renderTable } from './ui/tableCtrl.js?v=2';
import { renderTypesChart, renderStackChart, renderTrendChart, renderAnalytics, renderConvergenceChart } from './charts/chartCtrl.js?v=2';
import { renderHeatmap } from './ui/heatmap.js?v=2';
import { UI_STATE, AVG_NAMES } from './core/state.js?v=2';

document.addEventListener('DOMContentLoaded', () => {
    const p = processCommits(window.MATRIX_PAYLOAD || []);
    if (p.length > 0) {
        try {
            document.getElementById('cm-kp').textContent = p.length;
            document.getElementById('cm-ka').textContent = (p.reduce((a, c) => a + c.tot, 0) / p.length).toFixed(1);
            document.getElementById('cm-kc').textContent = p.filter(c => c.tier === 'Critical').length;
            document.getElementById('cm-ks').textContent = p.filter(c => c.tier === 'Significant').length;
            document.getElementById('cm-kr').textContent = p.filter(c => c.tier === 'Routine').length;
        } catch(e){}

        renderTable(p);
        const boot = () => { renderTypesChart(p); renderStackChart(p); renderTrendChart(p); renderAnalytics(p); renderConvergenceChart(p); renderHeatmap(p); };
        requestAnimationFrame(() => requestAnimationFrame(boot));

        document.querySelectorAll('[data-action="toggleChron"]').forEach(b => b.addEventListener('click', e => {
            const t = e.target.dataset.target; UI_STATE[t] = !UI_STATE[t]; e.target.classList.toggle('active', UI_STATE[t]); boot(); 
        }));
        document.querySelectorAll('[data-action="cycleAvg"]').forEach(b => b.addEventListener('click', e => {
            const t = e.target.dataset.target; const k = t === 'trend' ? 'avgTrend' : 'avg' + t.charAt(0).toUpperCase() + t.slice(1);
            UI_STATE[k] = (UI_STATE[k] + 1) % 6; e.target.textContent = `📊 Avg: ${AVG_NAMES[UI_STATE[k]]}`; e.target.classList.toggle('active', UI_STATE[k] !== 0); boot();
        }));
    }
});
