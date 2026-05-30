import { hub } from "./core/eventHub.js";
import "./core/appStateCtrl.js";
import "./engine/repoManager.js";
import "./engine/telemetryStream.js";
import "./engine/engineControl.js";
import "./ui/terminalView.js";

import { processCommits } from './core/dataEngine.js';
import { renderTypesChart, renderStackChart, renderTrendChart, renderAnalytics, renderConvergenceChart, renderTierChart } from './charts/chartCtrl.js';
import { renderHeatmap } from './ui/heatmap.js';
import { renderTable } from './ui/tableCtrl.js';
import { UI_STATE } from './core/state.js';

window.hub = hub;
window.triggerLedgerRefresh = () => hub.emit("ACTION:REFRESH_LEDGER");
window.CM_CLOSE_IN_PROGRESS = window.CM_CLOSE_IN_PROGRESS || false;
window.CM_ENGINE_CONTROLLABLE = window.CM_ENGINE_CONTROLLABLE || false;

function attemptRender() {
    const p = processCommits(window.MATRIX_PAYLOAD || []);
    if (p.length === 0) return;

    const canvas = document.getElementById('cm-c-types');
    if (!canvas || canvas.clientHeight === 0) { requestAnimationFrame(attemptRender); return; }

    try {
        document.getElementById('cm-kp').textContent = p.length;
        document.getElementById('cm-ka').textContent = (p.reduce((a, c) => a + c.tot, 0) / p.length).toFixed(1);
        document.getElementById('cm-kc').textContent = p.filter(c => c.tier === 'Critical').length;
        document.getElementById('cm-ks').textContent = p.filter(c => c.tier === 'Significant').length;
        document.getElementById('cm-kr').textContent = p.filter(c => c.tier === 'Routine').length;

        renderTierChart(p); renderTypesChart(p); renderStackChart(p); renderTrendChart(p);
        renderAnalytics(p); renderConvergenceChart(p); renderHeatmap(p); renderTable(p);
    } catch(e) { console.error("MATRIX UI ERROR:", e); }
}
window.addEventListener('load', attemptRender);

window.triggerSilentRefresh = async function() {
    try {
        if (window.CM_CLOSE_IN_PROGRESS) return;
        const urlParams = new URLSearchParams(window.location.search);
        const repo = urlParams.get('repo') || 'commit-matrix';
        const token = urlParams.get('token') || '';
        const res = await fetch(`/api/data?repo=${repo}&token=${token}`);
        if (!res.ok) return;

        const newData = await res.json();
        if (window.CM_CLOSE_IN_PROGRESS) return;

        if (JSON.stringify(newData) !== JSON.stringify(window.MATRIX_PAYLOAD)) {
            const hadNoLedger = !Array.isArray(window.MATRIX_PAYLOAD) || window.MATRIX_PAYLOAD.length === 0;
            const hasLedgerNow = Array.isArray(newData) && newData.length > 0;

            window.MATRIX_PAYLOAD = newData;

            const zs = document.getElementById('cm-zero-state');
            if (zs) zs.remove();

            document.querySelectorAll('.cm-row, .cm-kpi-row, #cm-ledger-card').forEach(el => {
                if (el.style.display === 'none') el.style.display = '';
            });

            if (!window.CM_CLOSE_IN_PROGRESS) attemptRender();
        }
    } catch (e) { }
};

// --- 1. SYSTEM UI ACTIONS DELEGATOR ---
document.addEventListener("click", (e) => {
    // Exit Hook (Force reload on close)
    if (e.target.closest('.modal-close') || e.target.closest('#close-terminal') || e.target.closest('#cm-btn-close') || e.target.closest('#cm-btn-close-cli')) {
        window.location.reload();
        return;
    }

    const btn = e.target.closest("button");
    const divBtn = e.target.closest("div");

    if ((btn && btn.textContent.includes("+ Add Repository")) ||
        (divBtn && divBtn.textContent.includes("+ Add Repository")) ||
        (e.target.getAttribute && e.target.getAttribute("onclick") && e.target.getAttribute("onclick").includes("ADD_REPO"))) {
        e.preventDefault();
        hub.emit("ACTION:ADD_REPO_REQUESTED");
        return;
    }

    if (btn && (btn.textContent.includes("Refresh Ledger") || btn.textContent.includes("Initialize"))) {
        e.preventDefault();
        hub.emit("ACTION:REFRESH_LEDGER");
        return;
    }
});

// --- 2. CHART INTERACTION DELEGATOR ---
document.addEventListener("click", (e) => {
    const fbtn = e.target.closest('.cm-fbtn[data-action]');
    if (!fbtn) return;
    
    const action = fbtn.dataset.action;
    const target = fbtn.dataset.target;
    
    console.log(`📊 Chart Button Clicked: [${action}] targeting [${target}]`);
    
    try {
        const processed = processCommits(window.MATRIX_PAYLOAD || []);

        if (action === 'toggleChron') {
            UI_STATE[target] = !UI_STATE[target];
            fbtn.classList.toggle('active', UI_STATE[target]);
            if (target === 'stack') renderStackChart(processed);
            if (target === 'trend') renderTrendChart(processed);
            if (target === 'heat') renderHeatmap(processed);
            if (['frag','churn','blast'].includes(target)) renderAnalytics(processed);
            if (target === 'conv') renderConvergenceChart(processed);
        }

        if (action === 'cycleAvg') {
            const key = 'avg' + target.charAt(0).toUpperCase() + target.slice(1);
            UI_STATE[key] = (UI_STATE[key] + 1) % 6;
            const modeNames = ['Off', 'Trailing 5', 'Daily Peak', 'Daily Median', 'Vol-Weighted', '7D High-Water'];
            fbtn.textContent = ` Avg: ${modeNames[UI_STATE[key]]}`;
            fbtn.classList.toggle('active', UI_STATE[key] !== 0);
            if (target === 'trend') renderTrendChart(processed);
            if (['frag','churn','blast'].includes(target)) renderAnalytics(processed);
        }
    } catch (err) {
        console.error(`❌ Chart render failed for target [${target}]:`, err);
    }
});
