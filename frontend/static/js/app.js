import { hub } from "./core/eventHub.js?v=0.6.9";
import "./core/appStateCtrl.js?v=0.6.9";
import "./engine/repoManager.js?v=0.6.9";
import "./engine/telemetryStream.js?v=0.6.9";
import "./engine/engineControl.js?v=0.6.9";
import "./ui/terminalView.js?v=0.6.9";

import { processCommits } from './core/dataEngine.js?v=0.6.9';
import { renderTypesChart, renderStackChart, renderTrendChart, renderAnalytics, renderConvergenceChart, renderTierChart } from './charts/chartCtrl.js?v=0.6.9';
import { renderHeatmap } from './ui/heatmap.js?v=0.6.9';
import { renderTable } from './ui/tableCtrl.js?v=0.6.9';
import { UI_STATE } from './core/state.js?v=0.6.9';

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
        const repo = urlParams.get('repo') || '';
        const token = urlParams.get('token') || '';
        const rubric = urlParams.get('rubric') || 'cirsd';
        const res = await fetch(`/api/data?repo=${repo}&rubric=${rubric}&token=${token}`);
        if (!res.ok) return;

        const newData = await res.json();
        if (window.CM_CLOSE_IN_PROGRESS) return;

        if (JSON.stringify(newData) !== JSON.stringify(window.MATRIX_PAYLOAD)) {
            window.MATRIX_PAYLOAD = newData;

            const zs = document.getElementById('cm-zero-state');
            if (zs) zs.remove();

            document.querySelectorAll('.cm-row, .cm-kpi-row, #cm-ledger-card').forEach(el => {
                el.style.display = '';
            });

            if (window.hub) {
                window.hub.emit("DATA:LEDGER_UPDATED"); 
            }
        }
    } catch (e) { }
};

// --- Standardized Soft-Routing Data Pipeline ---
hub.on("CONTEXT_CHANGED", (payload) => {
    const wrap = document.getElementById("main-dashboard-wrap");
    if (wrap) wrap.style.opacity = "0.4"; // Smooth visual loading indicator
    
    let fetchMsg = document.getElementById("cm-fetch-msg");
    if (!fetchMsg) {
        fetchMsg = document.createElement("div");
        fetchMsg.id = "cm-fetch-msg";
        fetchMsg.style.cssText = "position:fixed; top:50%; left:50%; transform:translate(-50%, -50%); background:rgba(10,14,20,0.95); border:1px solid rgba(255,255,255,0.1); padding:16px 32px; border-radius:8px; font-family:monospace; font-size:14px; z-index:9999; text-align:center; box-shadow:0 10px 40px rgba(0,0,0,0.8);";
        document.body.appendChild(fetchMsg);
    }
    
    const urlParams = new URLSearchParams(window.location.search);
    const o = (payload && payload.org) || urlParams.get('org') || 'Account';
    const r = (payload && payload.repo) || urlParams.get('repo') || 'Repo';
    const ru = (payload && payload.rubric) || urlParams.get('rubric') || 'Rubric';
    
    fetchMsg.innerHTML = `<span style="color:#8ab4f0; font-weight:bold;">${o}</span> <span style="color:#555; margin:0 6px;">/</span> <span style="color:#8ed068; font-weight:bold;">${r}</span> <span style="color:#555; margin:0 6px;">/</span> <span style="color:#a38b4f; font-weight:bold;">${ru.toUpperCase()}</span> <span style="color:#aaa; margin-left:8px;">metrics being fetched...</span>`;
    
    window.triggerSilentRefresh().then(() => {
        if (wrap) wrap.style.opacity = "1";
        const msg = document.getElementById("cm-fetch-msg");
        if (msg) msg.remove();
    });
});

// Formalize Event-Driven Rendering to silence terminal warnings
hub.on("DATA:LEDGER_UPDATED", () => {
    if (!window.CM_CLOSE_IN_PROGRESS) attemptRender();
});