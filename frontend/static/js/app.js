// v0.1.17
import { hub } from "./core/eventHub.js?v=0.1.234";
import "./core/appStateCtrl.js?v=0.1.234";
import "./engine/repoManager.js?v=0.1.234";
import "./engine/telemetryStream.js?v=0.1.234";
import "./engine/engineControl.js?v=0.1.234";
import "./ui/terminalView.js?v=0.1.234";

import { processCommits } from './core/dataEngine.js?v=0.1.234';
import { renderTypesChart, renderStackChart, renderTrendChart, renderAnalytics, renderConvergenceChart, renderTierChart } from './charts/chartCtrl.js?v=0.1.234';
import { renderHeatmap } from './ui/heatmap.js?v=0.1.234';
import { renderTable } from './ui/tableCtrl.js?v=0.1.234';
import { CM_COLORS } from './constants/colors.js?v=0.1.234';
import { UI_STATE, bumpGeneration } from './core/state.js?v=0.1.234';
window.hub = hub;
import { initGlobalTooltips } from './ui/tooltips.js';
initGlobalTooltips();
window.triggerLedgerRefresh = () => hub.emit("ACTION:REFRESH_LEDGER");
window.CM_CLOSE_IN_PROGRESS = window.CM_CLOSE_IN_PROGRESS || false;
window.CM_ENGINE_CONTROLLABLE = window.CM_ENGINE_CONTROLLABLE || false;

window.CM_RENDER_GEN = 0;

function computeKPIs(p) {
    let tot = 0, crit = 0, sig = 0, rout = 0;
    for (const c of p) {
        tot += c.tot;
        if (c.tier === 'Pivotal') crit++;
        else if (c.tier === 'Core') sig++;
        else if (c.tier === 'Minor') rout++;
    }
    return { count: p.length, avg: (tot / p.length).toFixed(1), crit, sig, rout };
}

function paintKPIs(k) {
    const kp = document.getElementById('cm-kp');
    if (!kp) return;
    kp.textContent = k.count;
    document.getElementById('cm-ka').textContent = k.avg;
    const kc = document.getElementById('cm-kc'); if(kc) { kc.textContent = k.crit; kc.style.color = CM_COLORS.Pivotal; }
    const ks = document.getElementById('cm-ks'); if(ks) { ks.textContent = k.sig; ks.style.color = CM_COLORS.Core; }
    const kr = document.getElementById('cm-kr'); if(kr) { kr.textContent = k.rout; kr.style.color = CM_COLORS.Minor; }
    
    const applyBadge = (id, color) => {
        const el = document.getElementById(id);
        if (el && color) {
            el.style.color = color;
            el.style.borderColor = color;
            el.style.background = color + '1A'; // 10% opacity hex
        }
    };
    applyBadge('tier-badge-pivotal', CM_COLORS.Pivotal);
    applyBadge('tier-badge-core', CM_COLORS.Core);
    applyBadge('tier-badge-minor', CM_COLORS.Minor);
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

function setDashboardVisibility(hasData, errorMsg = "") {
    const rows = document.querySelectorAll('.cm-row');
    const flexes = document.querySelectorAll('.cm-kpi-row, #cm-ledger-card');
    
    // Broad selector to capture common header action containers holding the Toggle/Filter/Sync buttons
    const actions = document.querySelectorAll('#cm-header-actions, .cm-header-actions, #cm-toolbar, .cm-toolbar, #cm-actions, .cm-actions');
    const wrap = document.getElementById("main-dashboard-wrap");
    
    if (hasData) {
        // Clear inline display style to safely restore original CSS stylesheet layout (restores full width grid/flex)
        rows.forEach(el => el.style.display = '');
        flexes.forEach(el => el.style.display = '');
        actions.forEach(el => el.style.display = '');
        const zs = document.getElementById('cm-zero-state');
        if (zs) zs.remove();
        if (wrap) wrap.style.opacity = "1";
    } else {
        rows.forEach(el => el.style.display = 'none');
        flexes.forEach(el => el.style.display = 'none');
        actions.forEach(el => el.style.display = 'none');
        if (wrap) wrap.style.opacity = "1";
        
        // Suppress Ledger Empty ghost dialog if the route itself is a 404 state
        if (window.MATRIX_INVALID_OWNER || window.MATRIX_INVALID_REPO || window.MATRIX_INVALID_RUBRIC) return;
        
        let zs = document.getElementById('cm-zero-state');
        if (!zs && wrap) {
            zs = document.createElement("div");
            zs.id = "cm-zero-state";
            zs.style.cssText = "position:fixed; left:50%; top:45%; transform:translate(-50%, -50%); display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; font-family:Satoshi, sans-serif; z-index:50; width:100%; ";
            wrap.insertBefore(zs, wrap.firstChild);
        }
        const activeZs = document.getElementById('cm-zero-state');
        if (activeZs) {
            const activeRubric = new URLSearchParams(window.location.search).get('rubric');
            const msg = errorMsg ? errorMsg : (activeRubric ? `No telemetry found for rubric: ${activeRubric.toUpperCase()}.` : `Please select an available rubric ledger to continue.`);
            activeZs.innerHTML = `
                <div style="font-size:52px; margin-bottom:20px; opacity:0.8;">🌌</div>
                <h2 style="color:#e0e0e0; margin-bottom:12px; font-weight:600; letter-spacing:0.5px;">Ledger Empty</h2>
                <p style="color:#888; max-width:420px; margin-bottom:30px; line-height:1.6; font-size:15px;">${msg}</p>
            `;
        }
    }
}

function attemptRender() {
    const rawData = window.MATRIX_CHART_PAYLOAD || window.MATRIX_PAYLOAD || [];
    let p = [];
    try {
        p = processCommits(rawData);
    } catch (e) {
        console.error("[Data Engine] processCommits failed silently:", e);
    }
    
    console.log(`[Data Engine] attemptRender -> rawData: ${rawData.length}, processed: ${p.length}`);

    const params = new URLSearchParams(window.location.search);
    if (!params.get('rubric')) {
        setDashboardVisibility(false, "Please select an available rubric ledger to continue.");
        return;
    }

    if (p.length === 0) {
        setDashboardVisibility(false);
        return;
    }
    
    setDashboardVisibility(true);

    const gen = window.CM_RENDER_GEN;
    
    // Force browser layout recalculation immediately so dimensions are available
    void document.body.offsetHeight;

    // Yield one frame to ensure DOM layout is fully resolved before drawing canvas contexts
    requestAnimationFrame(() => {
        if (gen !== window.CM_RENDER_GEN) return;
        try {
            paintKPIs(computeKPIs(p));
            const steps = buildRenderSteps(p);
            runRenderQueue(steps, gen);
        } catch (err) {
            console.error("MATRIX UI RENDER ERROR:", err);
        }
    });
}
window.addEventListener('load', async () => {
    const urlParams = new URLSearchParams(window.location.search);
    const owner = urlParams.get('owner') || window.MATRIX_OWNER || '';
    const repo = urlParams.get('repo');
    const rubric = urlParams.get('rubric');
    
    const isInvalid = window.MATRIX_INVALID_OWNER || window.MATRIX_INVALID_REPO || window.MATRIX_INVALID_RUBRIC;
    if (repo && rubric && !isInvalid && (window.MATRIX_PAYLOAD || window.MATRIX_CHART_PAYLOAD)) {
        console.log(`[Data Engine] Loading SQLite ledger via API: /api/data?owner=${owner}&repo=${repo}&rubric=${rubric} (Force: ${typeof isForce !== 'undefined' ? isForce : false})`);
    }

    attemptRender();
    if (repo) {
        const currentOwner = new URLSearchParams(window.location.search).get('owner') || (typeof owner !== "undefined" ? owner : window.MATRIX_OWNER || "local");
        let url = `/api/engine/status?owner=${currentOwner}&repo=${repo}`;
        if (urlParams.get('rubric')) url += `&rubric=${urlParams.get('rubric')}`;
        try {
            const res = await fetch(url);
            const data = await res.json();
            if (data.running && window.hub) {
                console.log(`[Auto-Attach] Found active ${data.mode || "docker"} run for ${currentOwner}/${repo}. Attaching...`);
                window.hub.emit("ENGINE:SCAN_REQUESTED", { repo: repo, rubric: urlParams.get("rubric"), owner: currentOwner, mode: data.mode });
            }
        } catch (e) {}
    }
});

window.triggerSilentRefresh = async function(opts = {}) {
    const myGen = opts.gen || window.CM_RENDER_GEN;
    try {
        if (window.CM_CLOSE_IN_PROGRESS) return;
        const urlParams = new URLSearchParams(window.location.search);
        const owner = opts.owner || urlParams.get('owner') || window.MATRIX_OWNER || '';
        const repo = opts.repo || urlParams.get('repo') || '';
        const token = opts.token || urlParams.get('token') || '';
        const rubric = opts.rubric || urlParams.get('rubric') || '';
        const isForce = !!opts.force;

        let urlChanged = false;
        if (opts.repo && opts.repo !== urlParams.get('repo')) { urlParams.set('repo', opts.repo); urlChanged = true; }
        if (opts.rubric && opts.rubric !== urlParams.get('rubric')) { urlParams.set('rubric', opts.rubric); urlChanged = true; }
        if (urlChanged) window.history.replaceState({}, '', `${window.location.pathname}?${urlParams.toString()}`);
        
        if (!rubric) {
            if (myGen === window.CM_RENDER_GEN) setDashboardVisibility(false, "Please select an available rubric ledger to continue.");
            return;
        }

        console.log(`[Data Engine] Loading ledger payload: data/${owner}/${repo}/db/${repo}_ledger_${rubric}.csv`);
        const res = await fetch(`/api/data?owner=${owner}&repo=${repo}&rubric=${rubric}&token=${token}&force=${isForce ? 'true' : 'false'}&_t=${Date.now()}`);
        if (!res.ok) {
            if (myGen === window.CM_RENDER_GEN) setDashboardVisibility(false);
            return;
        }

        const newData = await res.json();
        if (window.CM_CLOSE_IN_PROGRESS) return;

        // Gate: Drop response if generation drifted during our fetch round trip
        if (myGen !== window.CM_RENDER_GEN) return; 
        
        console.log(`[Data Engine] Fetched ${repo}/${rubric} | Array Size: ${Array.isArray(newData) ? newData.length : 'Not Array (Err)'}`);

        if (isForce || JSON.stringify(newData) !== JSON.stringify(window.MATRIX_PAYLOAD)) {
            window.MATRIX_PAYLOAD = newData;
            window.MATRIX_CHART_PAYLOAD = null;

            if (window.hub) {
                window.hub.emit("DATA:LEDGER_UPDATED", { gen: myGen }); 
            } else {
                attemptRender();
            }
        }
    } catch (e) {
        console.error("Silent refresh error:", e);
        if (myGen === window.CM_RENDER_GEN) setDashboardVisibility(false);
    }
};

// --- Standardized Soft-Routing Data Pipeline ---
hub.on("CONTEXT_CHANGED", (payload) => {
    const cmTt = document.getElementById("cm-tt"); if (cmTt) cmTt.classList.remove("visible");
    const infoTt = document.getElementById("info-tt"); if (infoTt) infoTt.classList.remove("visible");
    const urlParams = new URLSearchParams(window.location.search);
    const o = (payload && payload.owner) || urlParams.get('owner') || 'Owner';
    const r = (payload && payload.repo) || urlParams.get('repo') || 'Repo';
    const ru = (payload && payload.rubric) || urlParams.get('rubric') || '';

    // Very first line: Synchronous state lockdown and increment
    const myGen = bumpGeneration(r, ru);

    const wrap = document.getElementById("main-dashboard-wrap");
    if (wrap) wrap.style.opacity = "0.4";
    
    // Invalidate stale payload immediately to fix the Equality Trap
    window.MATRIX_PAYLOAD = null;
    window.MATRIX_CHART_PAYLOAD = null;

    let fetchMsg = document.getElementById("cm-fetch-msg");
    if (!fetchMsg) {
        fetchMsg = document.createElement("div");
        fetchMsg.id = "cm-fetch-msg";
        fetchMsg.style.cssText = "position:fixed; top:50%; left:50%; transform:translate(-50%, -50%); background:rgba(10,14,20,0.95); border:1px solid rgba(255,255,255,0.1); padding:16px 32px; border-radius:8px; font-family:monospace; font-size:14px; z-index:9999; text-align:center; box-shadow:0 10px 40px rgba(0,0,0,0.8); ";
        document.body.appendChild(fetchMsg);
    }
    
    if (ru) {
        fetchMsg.innerHTML = `<span style="color:#8ab4f0; font-weight:bold;">${o}</span> <span style="color:#555; margin:0 6px;">/</span> <span style="color:#8ed068; font-weight:bold;">${r}</span> <span style="color:#555; margin:0 6px;">/</span> <span style="color:#a38b4f; font-weight:bold;">${ru.toUpperCase()}</span> <span style="color:#aaa; margin-left:8px;">metrics being fetched...</span>`;
    } else {
        fetchMsg.innerHTML = `<span style="color:#a38b4f; font-weight:bold;">Loading Repository Data...</span>`;
    }

    window.triggerSilentRefresh({ repo: r, rubric: ru, force: true, gen: myGen }).finally(() => {
        if (myGen === window.CM_RENDER_GEN) {
            if (wrap) wrap.style.opacity = "1";
            const msg = document.getElementById("cm-fetch-msg");
            if (msg) msg.remove();
        }
    });
});

hub.on("DATA:LEDGER_UPDATED", (payload = {}) => {
    if (payload.gen && payload.gen !== window.CM_RENDER_GEN) return;
    if (!window.CM_CLOSE_IN_PROGRESS) attemptRender();
});
