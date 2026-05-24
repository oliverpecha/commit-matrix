import "./ui/terminal.js?v=99";
import { processCommits } from './core/dataEngine.js?v=99';
import { renderTypesChart, renderStackChart, renderTrendChart, renderAnalytics, renderConvergenceChart, renderTierChart } from './charts/chartCtrl.js?v=99';
import { renderHeatmap } from './ui/heatmap.js?v=99';
import { renderTable } from './ui/tableCtrl.js?v=99';

function attemptRender() {
    const p = processCommits(window.MATRIX_PAYLOAD || []);
    if (p.length === 0) return console.warn("MATRIX WARNING: Payload empty.");

    const canvas = document.getElementById('cm-c-types');
    if (!canvas || canvas.clientHeight === 0) {
        requestAnimationFrame(attemptRender);
        return;
    }

    try {
        document.getElementById('cm-kp').textContent = p.length;
        document.getElementById('cm-ka').textContent = (p.reduce((a, c) => a + c.tot, 0) / p.length).toFixed(1);
        document.getElementById('cm-kc').textContent = p.filter(c => c.tier === 'Critical').length;
        document.getElementById('cm-ks').textContent = p.filter(c => c.tier === 'Significant').length;
        document.getElementById('cm-kr').textContent = p.filter(c => c.tier === 'Routine').length;

        // Render all visual components
        renderTierChart(p);
        renderTypesChart(p);
        renderStackChart(p);
        renderTrendChart(p);
        renderAnalytics(p);
        renderConvergenceChart(p);
        renderHeatmap(p);
        renderTable(p);
        
    } catch(e) {
        console.error("MATRIX UI ERROR:", e);
    }
}
window.addEventListener('load', attemptRender);
