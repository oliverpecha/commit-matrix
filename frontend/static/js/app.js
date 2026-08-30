import { hub } from "./core/eventHub.js?v=0.6.19";
import "./core/appStateCtrl.js?v=0.6.19";
import "./engine/repoManager.js?v=0.6.19";
import "./engine/telemetryStream.js?v=0.6.19";
import "./engine/engineControl.js?v=0.6.19";
import "./ui/terminalView.js?v=0.6.19";

import { processCommits } from './core/dataEngine.js?v=0.6.19';
import { renderTypesChart, renderStackChart, renderTrendChart, renderAnalytics, renderConvergenceChart, renderTierChart } from './charts/chartCtrl.js?v=0.6.19';
import { renderHeatmap } from './ui/heatmap.js?v=0.6.19';
import { renderTable } from './ui/tableCtrl.js?v=0.6.19';
import { UI_STATE } from './core/state.js?v=0.6.19';

window.hub = hub;
window.triggerLedgerRefresh = () => hub.emit("ACTION:REFRESH_LEDGER");
window.CM_CLOSE_IN_PROGRESS = window.CM_CLOSE_IN_PROGRESS || false;
window.CM_ENGINE_CONTROLLABLE = window.CM_ENGINE_CONTROLLABLE || false;

window.CM_RENDER_GEN = 0;

function computeKPIs(p) {
    let tot = 0, crit = 0, sig = 0, rout = 0;
    for (const c of p) {
        tot += c.tot;
        if (c.tier === 'Critical') crit++;
        else if (c.tier === 'Significant') sig++;
        else if (c.tier === 'Routine') rout++;
    }
    return { count: p.length, avg: (tot / p.length).toFixed(1), crit, sig, rout };
}

function paintKPIs(k) {
    document.getElementById('cm-kp').textContent = k.count;
    document.getElementById('cm-ka').textContent = k.avg;
    document.getElementById('cm-kc').textContent = k.crit;
    document.getElementById('cm-ks').textContent = k.sig;
    document.getElementById('cm-kr').textContent = k.rout;
}

function buildRenderSteps(p) {
    return [
        () => renderTierChart(p),
        () => renderTypesChart(p),
        () => renderTrendChart(p),
        () => renderStackChart(p),
        () => renderAnalytics(p),
        () => renderConvergenceChart(p),
        () => renderHeatmap(p),
        () => renderTable(p),
    ];
}

function runRenderQueue(steps, gen) {
    let i = 0;
    function step() {
        if (gen !== window.CM_RENDER_GEN) return;
        const t0 = performance.now();
        try {
            while (i < steps.length && (performance.now() - t0) < 8) {
                steps[i++]();
            }
        } catch (e) {
            console.error("MATRIX UI ERROR:", e);
        }
        if (i < steps.length && gen === window.CM_RENDER_GEN) {
            requestAnimationFrame(step);
        }
    }
    requestAnimationFrame(step);
}

function attemptRender() {
    const p = processCommits(window.MATRIX_CHART_PAYLOAD || window.MATRIX_PAYLOAD || []);
    if (p.length === 0) return;

    const canvas = document.getElementById('cm-c-types');
    if (!canvas || canvas.clientHeight === 0) {
        if (!window.CM_CANVAS_RO && canvas) {
            window.CM_CANVAS_RO = new ResizeObserver((entries, obs) => {
                if (canvas.clientHeight > 0) {
                    obs.disconnect();
                    window.CM_CANVAS_RO = null;
                    requestAnimationFrame(attemptRender);
                }
            });
            window.CM_CANVAS_RO.observe(canvas.parentElement || document.body);
        }
        return;
    }

    const gen = ++window.CM_RENDER_GEN;
    paintKPIs(computeKPIs(p));

    const steps = buildRenderSteps(p);
    runRenderQueue(steps, gen);
}
window.addEventListener('load', attemptRender);

window.triggerSilentRefresh = async function(opts = {}) {
    try {
        if (window.CM_CLOSE_IN_PROGRESS) return;
        const urlParams = new URLSearchParams(window.location.search);
        const repo = opts.repo || urlParams.get('repo') || '';
        const token = opts.token || urlParams.get('token') || '';
        const rubric = opts.rubric || urlParams.get('rubric') || 'cirsd';
        const res = await fetch(`/api/data?repo=${repo}&rubric=${rubric}&token=${token}`);
        if (!res.ok) return;

        const newData = await res.json();
        if (window.CM_CLOSE_IN_PROGRESS) return;

        window.CM_RENDER_GEN = (window.CM_RENDER_GEN || 0) + 1;
        if (window.CM_SCROLL_ABORT) { window.CM_SCROLL_ABORT.abort(); window.CM_SCROLL_ABORT = null; }
        if (window.CM_CANVAS_RO) { window.CM_CANVAS_RO.disconnect(); window.CM_CANVAS_RO = null; }
        if (window.CM_TABLE_OBSERVER) { window.CM_TABLE_OBSERVER.disconnect(); window.CM_TABLE_OBSERVER = null; }

        if (JSON.stringify(newData) !== JSON.stringify(window.MATRIX_PAYLOAD)) {
            window.MATRIX_PAYLOAD = newData;
            window.MATRIX_CHART_PAYLOAD = null;

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
    
    window.triggerSilentRefresh({ repo: r, rubric: ru }).then(() => {
        if (wrap) wrap.style.opacity = "1";
        const msg = document.getElementById("cm-fetch-msg");
        if (msg) msg.remove();
    });
});

// Formalize Event-Driven Rendering to silence terminal warnings
hub.on("DATA:LEDGER_UPDATED", () => {
    if (!window.CM_CLOSE_IN_PROGRESS) attemptRender();
});