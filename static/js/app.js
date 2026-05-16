import { processCommits } from './core/dataEngine.js';
import { initGlobalTooltips } from './ui/tooltips.js';
import { renderTable } from './ui/tableCtrl.js';
import { renderTypesChart, renderStackChart, renderTrendChart } from './charts/chartCtrl.js';
import { renderHeatmap } from './ui/heatmap.js';
import { CM_COLORS } from './core/constants.js';

document.addEventListener('DOMContentLoaded', () => {
    const rawCommits = window.MATRIX_PAYLOAD || [];
    const processed = processCommits(rawCommits);

    if (processed.length > 0) {
        // Render KPIs
        document.getElementById('cm-kp').textContent = processed.length;
        document.getElementById('cm-ka').textContent = (processed.reduce((a, c) => a + c.tot, 0) / processed.length).toFixed(1);
        document.getElementById('cm-kc').textContent = processed.filter(c => c.tier === 'Critical').length;
        document.getElementById('cm-ks').textContent = processed.filter(c => c.tier === 'Significant').length;
        document.getElementById('cm-kr').textContent = processed.filter(c => c.tier === 'Routine').length;

        // Render Base UI
        initGlobalTooltips();
        renderTable(processed);

        // Render Charts & Vis
        renderTypesChart(processed);
        renderStackChart(processed);
        renderTrendChart(processed);
        
        // Heatmap needs a slight delay to ensure the container is fully painted
        setTimeout(() => renderHeatmap(processed), 100);

        // Tier Doughnut
        const tierCtx = document.getElementById('cm-c-tier');
        if (tierCtx) {
            new Chart(tierCtx, {
                type: 'doughnut',
                data: {
                    labels: ['Critical', 'Significant', 'Routine'],
                    datasets: [{
                        data: [
                            processed.filter(c => c.tier === 'Critical').length,
                            processed.filter(c => c.tier === 'Significant').length,
                            processed.filter(c => c.tier === 'Routine').length
                        ],
                        backgroundColor: [CM_COLORS.Critical, CM_COLORS.Significant, CM_COLORS.Routine],
                        borderWidth: 2, borderColor: '#1e1d1b'
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false, cutout: '65%', plugins: { legend: { display: false } } }
            });
        }
    }
    
    console.log("⚡ CommitMatrix Engine: All visualization modules online.");
});
