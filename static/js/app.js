import "./ui/terminal.js?v=203";
import { processCommits } from './core/dataEngine.js?v=115';
import { renderTypesChart, renderStackChart, renderTrendChart, renderAnalytics, renderConvergenceChart, renderTierChart } from './charts/chartCtrl.js?v=115';
import { renderHeatmap } from './ui/heatmap.js?v=115';
import { renderTable } from './ui/tableCtrl.js?v=201';

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

// Force refresh on terminal close to clear Zero-State
document.addEventListener('click', (e) => { if (e.target.closest('.modal-close') || e.target.closest('#close-terminal')) window.location.reload(); });


// --- LIVE REFRESH ENGINE ---
window.triggerSilentRefresh = async function() {
    try {
        const urlParams = new URLSearchParams(window.location.search);
        const repo = urlParams.get('repo') || 'commit-matrix';
        const token = urlParams.get('token') || '';
        
        const res = await fetch(`/api/data?repo=${repo}&token=${token}`);
        if (!res.ok) return;
        
        const newData = await res.json();
        // Only trigger heavy DOM repaints if we actually have new commits
        
        const currentData = window.MATRIX_PAYLOAD || [];
        if (JSON.stringify(newData) !== JSON.stringify(window.MATRIX_PAYLOAD)) {

            window.MATRIX_PAYLOAD = newData;
            
            const zs = document.getElementById('cm-zero-state');
            if (zs) zs.remove(); // Purge the zero state completely
            
            // Un-hide all the preserved dashboard elements safely
            document.querySelectorAll('.cm-row, .cm-kpi-row, #cm-ledger-card').forEach(el => {
                if (el.style.display === 'none') el.style.display = '';
            });
            
            attemptRender(); // Inject new data into Chart.js
        }
    } catch (e) { }
};

// Restored original triggerLedgerRefresh

// Polling loop: Only fetches data if the terminal window is actively open
setInterval(() => {
    const term = document.getElementById('cm-terminal-status');
    if (term && !term.innerHTML.includes('RELOAD')) {
        window.triggerSilentRefresh();
    }
}, 2500);

// --- BULLETPROOF TOAST CSS INJECTION ---
if (!document.getElementById('toast-css')) {
    const style = document.createElement('style');
    style.id = 'toast-css';
    style.innerHTML = `
      #cm-terminal-modal {
          position: fixed !important; bottom: 24px !important; right: 24px !important;
          top: auto !important; left: auto !important; width: 720px !important; height: 380px !important;
          transform: none !important; border-radius: 8px !important; background: #0a0e14 !important;
          box-shadow: 0 8px 16px rgba(0,0,0,0.5) !important; border: 1px solid rgba(255,255,255,0.08) !important;
          z-index: 9999 !important; opacity: 0.95 !important; transition: opacity 0.2s ease-in-out; margin: 0 !important;
      }
      #cm-terminal-modal:hover { opacity: 1 !important; }
      /* Nuke blocking layers and conflicting inner modal shades */
      #cm-terminal-backdrop, .modal-backdrop, .cm-backdrop { display: none !important; pointer-events: none !important; }
      #cm-terminal-modal .modal-content, #cm-terminal-modal .modal-dialog {
          background: transparent !important; box-shadow: 0 8px 16px rgba(0,0,0,0.5) !important; border: 1px solid rgba(255,255,255,0.08) !important; border: none !important; margin: 0 !important; width: 100% !important;
      }
      /* Progress Pulse Animation */
      @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.3; } 100% { opacity: 1; } }
      .processing-pulse { animation: pulse 1.5s infinite ease-in-out; }
    `;
    document.head.appendChild(style);
}


// --- SHADOW NUKE ---
if (!document.getElementById('shadow-nuke-css')) {
    const style = document.createElement('style');
    style.id = 'shadow-nuke-css';
    style.innerHTML = `
      /* Destroy native HTML5 dialog backdrops */
      dialog::backdrop, #cm-terminal-modal::backdrop { 
          background: transparent !important; display: none !important; opacity: 0 !important; 
      }
      /* Soften the actual Toast drop-shadow so it doesn't bleed weirdly */
      #cm-terminal-modal { 
          box-shadow: 0 8px 16px rgba(0,0,0,0.5) !important; border: 1px solid rgba(255,255,255,0.08) !important; 
      }
    `;
    document.head.appendChild(style);
}

// --- CHART INTERACTION DELEGATOR ---
import { UI_STATE } from './core/state.js?v=99';

document.addEventListener('click', (e) => {
    const btn = e.target.closest('.cm-fbtn[data-action]');
    if (!btn) return;
    
    const action = btn.dataset.action;
    const target = btn.dataset.target;
    
    // Toggle Chronological/Temporal Axis
    if (action === 'toggleChron') {
        UI_STATE[target] = !UI_STATE[target];
        btn.classList.toggle('active', UI_STATE[target]);
        
        if (target === 'stack') renderStackChart(window.MATRIX_PAYLOAD);
        if (target === 'trend') renderTrendChart(window.MATRIX_PAYLOAD);
        if (target === 'heat') renderHeatmap(window.MATRIX_PAYLOAD);
        if (['frag','churn','blast'].includes(target)) renderAnalytics(window.MATRIX_PAYLOAD);
        if (target === 'conv') renderConvergenceChart(window.MATRIX_PAYLOAD);
    }
    
    // Cycle Moving Averages
    if (action === 'cycleAvg') {
        const key = 'avg' + target.charAt(0).toUpperCase() + target.slice(1);
        UI_STATE[key] = (UI_STATE[key] + 1) % 6; // Modulo 6 for the 6 available modes
        
        const modeNames = ['Off', 'Trailing 5', 'Daily Peak', 'Daily Median', 'Vol-Weighted', '7D High-Water'];
        btn.textContent = ` Avg: ${modeNames[UI_STATE[key]]}`;
        btn.classList.toggle('active', UI_STATE[key] !== 0);
        
        if (target === 'trend') renderTrendChart(window.MATRIX_PAYLOAD);
        if (['frag','churn','blast'].includes(target)) renderAnalytics(window.MATRIX_PAYLOAD);
    }
});
