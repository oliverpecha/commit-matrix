import { processCommits } from './core/dataEngine.js';
import { UI_STATE, AVG_NAMES } from './core/state.js';
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
    }
});
