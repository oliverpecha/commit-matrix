// v0.1.17
import { hub } from "./core/eventHub.js?v=0.1.348";
import "./core/appStateCtrl.js?v=0.1.348";
import "./engine/repoManager.js?v=0.1.348";
import "./engine/telemetryStream.js?v=0.1.348";
import "./engine/engineControl.js?v=0.1.348";
import "./ui/terminalView.js?v=0.1.348";

import { processCommits, filterByDateBounds } from './core/dataEngine.js?v=0.1.348';
import { renderTypesChart, renderStackChart, renderTrendChart, renderRiskCharts, renderConvergenceChart, renderTierChart } from './charts/chartCtrl.js?v=0.1.348';
import { renderHeatmap } from './ui/heatmap.js?v=0.1.348';
import { renderTable } from './ui/tableCtrl.js?v=0.1.348';
import { CM_COLORS } from './constants/colors.js?v=0.1.348';
import { UI_STATE, bumpGeneration } from './core/state.js?v=0.1.348';
import { showTotalZeroState, showFilteredZeroState, hideZeroStates } from './ui/zeroStateCtrl.js?v=0.1.348';
import { showTotalZeroState, showFilteredZeroState, hideZeroStates } from './ui/zeroStateCtrl.js?v=0.1.348';
window.hub = hub;
import { initGlobalTooltips } from './ui/tooltips.js';
initGlobalTooltips();
window.triggerLedgerRefresh = () => hub.emit("ACTION:REFRESH_LEDGER");
window.CM_CLOSE_IN_PROGRESS = window.CM_CLOSE_IN_PROGRESS || false;
window.CM_ENGINE_CONTROLLABLE = window.CM_ENGINE_CONTROLLABLE || false;

window.CM_RENDER_GEN = 0;
window.CM_LAST_GOOD_FILTER = { start: null, end: null, label: 'All history' };

function computeKPIs(p) {
    let tot = 0, crit = 0, sig = 0, rout = 0;
    for (const c of p) {
        tot += c.tot;
        if (c.tier === 'Pivotal') crit++;
        else if (c.tier === 'Core') sig++;
        else if (c.tier === 'Minor') rout++;
    }
    const rawData = window.MATRIX_PAYLOAD_RAW || window.MATRIX_PAYLOAD || [];
    const totalAll = rawData.length || p.length;
    return { count: p.length, totalAll, avg: p.length > 0 ? (tot / p.length).toFixed(1) : "0.0", crit, sig, rout };
}

function paintKPIs(k) {
    const kp = document.getElementById('cm-kp');
    if (!kp) return;
    if (k.totalAll > k.count) {
        kp.innerHTML = `${k.count}<span style="opacity:0.5;font-weight:normal;font-size:0.65em;margin-left:4px;">/ ${k.totalAll}</span>`;
    } else {
        kp.textContent = k.count;
    }
    document.getElementById('cm-ka').textContent = k.avg;
    
    const setTierVal = (id, count, clr) => {
        const el = document.getElementById(id);
        if (!el) return;
        el.style.color = count > 0 ? clr : '#7a7874';
        if (k.count > 0 && count > 0) {
            const pct = Math.round((count / k.count) * 100);
            el.innerHTML = `${count}<span style="color:#7a7874;font-weight:normal;font-size:0.65em;margin-left:4px;">/ ~${pct}%</span>`;
        } else {
            el.textContent = count;
        }
    };

    setTierVal('cm-kc', k.crit, CM_COLORS.Pivotal);
    setTierVal('cm-ks', k.sig, CM_COLORS.Core);
    setTierVal('cm-kr', k.rout, CM_COLORS.Minor);

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
        () => renderRiskCharts(p),
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
    if (!window.MATRIX_PAYLOAD_RAW && window.MATRIX_PAYLOAD && window.MATRIX_PAYLOAD.length) {
        window.MATRIX_PAYLOAD_RAW = window.MATRIX_PAYLOAD;
    }
    const sourceData = window.MATRIX_PAYLOAD_RAW || window.MATRIX_CHART_PAYLOAD || window.MATRIX_PAYLOAD || [];
    
    let p = [];
    try {
        p = processCommits(sourceData);
    } catch (e) {
        console.error("[Data Engine] processCommits failed silently:", e);
    }

    // Apply filtering AFTER processCommits normalizes the timestamps to c.ts
    const p_all = p;
    const df = UI_STATE.dateFilter || { start: null, end: null, label: 'All history' };
    const filteredP = filterByDateBounds(p, df.start, df.end);
    window.CM_CURRENT_FILTERED_PAYLOAD = filteredP;
    p = filteredP; // Enforce filtered set downwards through the rendering chain

    console.log(`[Data Engine] attemptRender -> rawData: ${sourceData.length}, processed: ${p.length}, filtered: ${filteredP.length}`);

    const floatingAudit = document.getElementById('cm-alert-float');
    if (window.CM_AUDIT_ANOMALIES && window.CM_AUDIT_ANOMALIES.length > 0) {
        if (floatingAudit) floatingAudit.style.display = 'flex';
        const floatCount = document.getElementById('cm-alert-float-count');
        if (floatCount) floatCount.textContent = window.CM_AUDIT_ANOMALIES.length;
        const floatNoun = document.getElementById('cm-alert-float-noun');
        if (floatNoun) floatNoun.textContent = window.CM_AUDIT_ANOMALIES.length === 1 ? 'Scoring Anomaly' : 'Scoring Anomalies';
        const auditList = document.getElementById('cm-alert-list');
        if (auditList) {
            auditList.innerHTML = window.CM_AUDIT_ANOMALIES.map(a => `
                <div style="background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.08); border-radius:6px; padding:12px;">
                    <div style="display:flex; justify-content:space-between; margin-bottom:8px; color:#8ab4f0;">
                        <span><strong>#${a.num}</strong> <code style="background:rgba(0,0,0,0.3); padding:2px 6px; border-radius:4px;">${(a.hash||'').substring(0,7)}</code></span>
                        <span style="color:#888;">${new Date(a.ts * 1000).toLocaleDateString()}</span>
                    </div>
                    <div style="color:#e0e0e0; margin-bottom:8px; font-family:Satoshi, sans-serif;">${a.subj}</div>
                    <div style="color:#ff4b4b; margin-bottom:8px;">${a.reasons.map(r => `<div>↳ ${r}</div>`).join('')}</div>
                    <div style="font-size:11px; color:#a38b4f;">🤖 Scored by: <strong>${a.model}</strong></div>
                </div>
            `).join('');
        }
    } else {
        if (floatingAudit) floatingAudit.style.display = 'none';
    }
    const params = new URLSearchParams(window.location.search);
    if (!params.get('rubric')) {
        showTotalZeroState("Please select an available rubric ledger to continue.");
        return;
    }

    const hasRawTelemetry = Array.isArray(sourceData) && sourceData.length > 0;
    if (!hasRawTelemetry) {
        showTotalZeroState();
        return;
    }

    if (p.length === 0) {
        showFilteredZeroState({
            filter: df,
            allCommits: p_all,
            lastGoodFilter: window.CM_LAST_GOOD_FILTER,
            onRevert: () => {
                const target = window.CM_LAST_GOOD_FILTER || { start: null, end: null, label: 'All history' };
                if (typeof window.CM_APPLY_DATE_FILTER === 'function') {
                    window.CM_APPLY_DATE_FILTER(target.start, target.end, target.label);
                }
            }
        });
        return;
    }

    // Track last successful filter that returned active commits
    window.CM_LAST_GOOD_FILTER = { start: df.start, end: df.end, label: df.label || 'All history' };
    hideZeroStates();

    // [Patch] Enforce Timeline Mode defaults securely on initial boot
    if (!window._cmBootSyncDone) {
        window._cmBootSyncDone = true;
        UI_STATE.globalChron = true;

        const CHRONO_CAPABLE = ['stack', 'trend', 'conv', 'frag', 'churn', 'blast', 'heat', 'types', 'tier'];
        CHRONO_CAPABLE.forEach(t => {
            UI_STATE[t] = true;
            if (['trend', 'frag', 'churn', 'blast'].includes(t)) {
                const avgKey = t === 'trend' ? 'avgTrend' : 'avg' + t.charAt(0).toUpperCase() + t.slice(1);
                UI_STATE[avgKey] = 2; // Default to Daily Peak
                const ab = document.querySelector(`button[data-action="cycleAvg"][data-target="${t}"]`);
                if (ab) { 
                    ab.innerHTML = `<svg width="14" height="14" viewBox="0 0 32 32" fill="currentColor" style="display:inline-block; vertical-align:-2px; margin-right:4px;"><path d="M23,24c-3.5991,0-5.0293-4.1758-6.4126-8.2139C15.2764,11.9583,13.92,8,11,8a3.44,3.44,0,0,0-3.0532,2.3215L6.0513,9.6838C6.1016,9.5334,7.3218,6,11,6c4.3491,0,6.0122,4.8547,7.48,9.1379C19.6885,18.6667,20.83,22,23,22a3.44,3.44,0,0,0,3.0532-2.3215l1.8955.6377C27.8984,20.4666,26.6782,24,23,24Z"/><path d="M4,28V17H6V15H4V2H2V28a2,2,0,0,0,2,2H30V28Z"/><rect x="8" y="15" width="2" height="2"/><rect x="12" y="15" width="2" height="2"/><rect x="20" y="15" width="2" height="2"/><rect x="24" y="15" width="2" height="2"/><rect x="28" y="15" width="2" height="2"/></svg> Daily Peak`; 
                    ab.classList.add('active'); 
                }
            }
        });

        const mainBtn = document.getElementById('cm-global-chron-btn');
        if (mainBtn && !mainBtn.classList.contains('active')) {
            mainBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="display:inline-block; vertical-align:-2px;"><circle cx="5" cy="12" r="4"/><path d="M5 9v3h1.5M9 12h1.5M13.5 12h1M17.5 12h3"/><circle cx="12" cy="12" r="1.5"/><circle cx="16" cy="12" r="1.5"/><circle cx="22" cy="12" r="1.5"/></svg> Timeline`;
            mainBtn.classList.add('active');
        }
    }

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

    initDateFilter();
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
            if (myGen === window.CM_RENDER_GEN) showTotalZeroState("Please select an available rubric ledger to continue.");
            return;
        }

        console.log(`[Data Engine] Loading ledger payload: data/${owner}/${repo}/db/${repo}_ledger_${rubric}.csv`);
        const res = await fetch(`/api/data?owner=${owner}&repo=${repo}&rubric=${rubric}&token=${token}&force=${isForce ? 'true' : 'false'}&_t=${Date.now()}`);
        if (!res.ok) {
            if (myGen === window.CM_RENDER_GEN) showTotalZeroState();
            return;
        }

        const newData = await res.json();
        if (window.CM_CLOSE_IN_PROGRESS) return;

        // Gate: Drop response if generation drifted during our fetch round trip
        if (myGen !== window.CM_RENDER_GEN) return; 

        console.log(`[Data Engine] Fetched ${repo}/${rubric} | Array Size: ${Array.isArray(newData) ? newData.length : 'Not Array (Err)'}`);

        if (isForce || JSON.stringify(newData) !== JSON.stringify(window.MATRIX_PAYLOAD)) {
            window.MATRIX_PAYLOAD_RAW = newData;
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
        if (myGen === window.CM_RENDER_GEN) showTotalZeroState();
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
    window.MATRIX_PAYLOAD_RAW = null;
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

// --- Date Filtering Controller ---
function initDateFilter() {
    const toggle = document.getElementById('cm-date-toggle');
    const menu = document.getElementById('cm-date-menu');
    const label = document.getElementById('cm-date-label');
    const customPanel = document.getElementById('cm-date-custom-panel');
    const cancelBtn = document.getElementById('cm-date-cancel-btn');
    const startInput = document.getElementById('cm-date-start');
    const endInput = document.getElementById('cm-date-end');

    if (!toggle || !menu) return;

    const fmtShort = (d) => d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
    
    // Calculates reliable local 'YYYY-MM-DD' offset against UTC
    const getLocalYMD = () => {
        const d = new Date();
        d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
        return d.toISOString().split('T')[0];
    };

    function renderMenu() {
        const now = new Date();
        const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());

        const dayOfWeek = (startOfToday.getDay() + 6) % 7;
        const startThisWeek = new Date(startOfToday); startThisWeek.setDate(startOfToday.getDate() - dayOfWeek);
        const endThisWeek = new Date(startThisWeek); endThisWeek.setDate(startThisWeek.getDate() + 6); endThisWeek.setHours(23,59,59,999);

        const startThisMonth = new Date(now.getFullYear(), now.getMonth(), 1);
        const endThisMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0, 23,59,59,999);

        const currentQuarter = Math.floor(now.getMonth() / 3);
        const startThisQuarter = new Date(now.getFullYear(), currentQuarter * 3, 1);
        const endThisQuarter = new Date(now.getFullYear(), currentQuarter * 3 + 3, 0, 23,59,59,999);

        const startThisYear = new Date(now.getFullYear(), 0, 1);
        const endThisYear = new Date(now.getFullYear(), 11, 31, 23,59,59,999);

        const startLastDay = new Date(startOfToday); startLastDay.setDate(startOfToday.getDate() - 1);
        const endLastDay = new Date(startOfToday); endLastDay.setMilliseconds(-1);

        const startLastWeek = new Date(now.getTime() - (7 * 86400000));
        const endLastWeek = now;

        const startPast30 = new Date(now.getTime() - (30 * 86400000));
        const startPast90 = new Date(now.getTime() - (90 * 86400000));
        const startPast180 = new Date(now.getTime() - (180 * 86400000));
        const startPast365 = new Date(now.getTime() - (365 * 86400000));

        const groups = [
            {
                group: 'Current',
                opts: [
                    { id: 'this_week', label: 'This Week', start: startThisWeek.getTime()/1000, end: endThisWeek.getTime()/1000, span: `${fmtShort(startThisWeek)} - ${fmtShort(endThisWeek)}` },
                    { id: 'this_month', label: 'This Month', start: startThisMonth.getTime()/1000, end: endThisMonth.getTime()/1000, span: `${fmtShort(startThisMonth)} - ${fmtShort(endThisMonth)}` },
                    { id: 'this_quarter', label: 'This quarter', start: startThisQuarter.getTime()/1000, end: endThisQuarter.getTime()/1000, span: `${fmtShort(startThisQuarter)} - ${fmtShort(endThisQuarter)}` },
                    { id: 'this_year', label: 'This year', start: startThisYear.getTime()/1000, end: endThisYear.getTime()/1000, span: `${fmtShort(startThisYear)} - ${fmtShort(endThisYear)}` }
                ]
            },
            {
                group: 'Past',
                opts: [
                    { id: 'last_day', label: 'Last day', start: startLastDay.getTime()/1000, end: endLastDay.getTime()/1000, span: `${fmtShort(startLastDay)} - ${fmtShort(endLastDay)}` },
                    { id: 'last_week', label: 'Last 7 days', start: startLastWeek.getTime()/1000, end: endLastWeek.getTime()/1000, span: `${fmtShort(startLastWeek)} - ${fmtShort(endLastWeek)}` },
                    { id: 'past_30', label: 'Last 30 days', start: startPast30.getTime()/1000, end: now.getTime()/1000, span: `${fmtShort(startPast30)} - ${fmtShort(now)}` },
                    { id: 'past_90', label: 'Last 90 days', start: startPast90.getTime()/1000, end: now.getTime()/1000, span: `${fmtShort(startPast90)} - ${fmtShort(now)}` },
                    { id: 'past_180', label: 'Last 180 days', start: startPast180.getTime()/1000, end: now.getTime()/1000, span: `${fmtShort(startPast180)} - ${fmtShort(now)}` },
                    { id: 'past_365', label: 'Last 365 days', start: startPast365.getTime()/1000, end: now.getTime()/1000, span: `${fmtShort(startPast365)} - ${fmtShort(now)}` }
                ]
            },
            {
                group: 'Custom',
                isCustom: true
            }
        ];

        let html = '';
        
        // Pin "All history" to the very top if it is NOT the currently active default
        if (UI_STATE.dateFilter?.label && UI_STATE.dateFilter.label !== 'All history') {
            html += `
                <div style="padding:6px 4px 0 4px;">
                    <button class="cm-date-opt cm-preset-btn" data-start="" data-end="" data-label="All history" style="width:100%; text-align:left; background:transparent; border:none; padding:6px 10px; border-radius:4px; font-size:12px; font-weight:600; color:#d9d8d5; cursor:pointer; display:flex; justify-content:space-between; align-items:center;">
                        <span>Clear Filter (All History)</span>
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="opacity:0.6;"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                    </button>
                </div>
                <div style="border-top:1px solid rgba(255,255,255,0.08); margin:6px 0 2px 0;"></div>
            `;
        }

        groups.forEach(g => {
            if (g.isCustom) {
                html += `
                    <div style="padding:8px 10px 4px 10px; font-size:10px; color:#7a7874; text-transform:uppercase; letter-spacing:0.05em;">Custom</div>
                    <div style="padding:0 4px 4px 4px;"><button id="cm-date-custom-opt" class="cm-date-opt" style="width:100%; text-align:left; background:transparent; border:none; padding:7px 10px; border-radius:4px; font-size:12px; color:#d9d8d5; cursor:pointer; display:flex; justify-content:space-between; align-items:center;">
                        <span>Choose a range...</span><span style="font-size:10px; opacity:0.5;">→</span>
                    </button></div>
                `;
            } else {
                html += `
                    <div style="padding:8px 10px 4px 10px; font-size:10px; color:#7a7874; text-transform:uppercase; letter-spacing:0.05em;">${g.group}</div>
                    <div style="display:flex; flex-direction:column; padding:0 4px;">
                        ${g.opts.map(p => `
                            <button class="cm-date-opt cm-preset-btn ${UI_STATE.dateFilter?.label === p.label ? 'active' : ''}" data-start="${p.start ?? ''}" data-end="${p.end ?? ''}" data-label="${p.label}" style="width:100%; text-align:left; background:transparent; border:none; padding:6px 10px; border-radius:4px; font-size:12px; cursor:pointer; display:flex; justify-content:space-between; align-items:center;">
                                <span>${p.label}</span>
                                ${p.span ? `<span class="cm-date-span">${p.span}</span>` : ''}
                            </button>
                        `).join('')}
                    </div>
                `;
            }
        });
        menu.innerHTML = html;

        menu.querySelectorAll('.cm-preset-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const s = btn.dataset.start ? Number(btn.dataset.start) : null;
                const e = btn.dataset.end ? Number(btn.dataset.end) : null;
                applyFilter(s, e, btn.dataset.label === 'Clear Filter (All History)' ? 'All history' : btn.dataset.label);
                if (customPanel) customPanel.style.display = 'none';
                if (toggle) toggle.style.display = 'inline-flex';
            });
        });

        const customOpt = document.getElementById('cm-date-custom-opt');
        if (customOpt) {
            customOpt.addEventListener('click', () => {
                menu.style.display = 'none';
                if (toggle) toggle.style.display = 'none';
                if (customPanel) customPanel.style.display = 'inline-flex';
                
                // Pre-fill Custom Input constraints based on current UI_STATE bounds
                const tsToYMD = (ts) => {
                    const d = new Date(ts * 1000);
                    return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
                };

                if (UI_STATE.dateFilter?.start) {
                    startInput.value = tsToYMD(UI_STATE.dateFilter.start);
                } else {
                    let earliestTs = null;
                    const src = window.MATRIX_PAYLOAD_RAW || window.MATRIX_PAYLOAD;
                    if (src && src.length > 0) earliestTs = Math.min(...src.map(c => c.ts || Infinity));
                    startInput.value = (earliestTs && earliestTs !== Infinity) ? tsToYMD(earliestTs) : '';
                }
                
                if (UI_STATE.dateFilter?.end) {
                    endInput.value = tsToYMD(UI_STATE.dateFilter.end);
                } else {
                    endInput.value = getLocalYMD(); // Default to today
                }
                
                // Setup bounds based on current state (ensures max-date limits sync up immediately)
                syncDateConstraints(null);
            });
        }
    }

    function applyFilter(start, end, labelText) {
        UI_STATE.dateFilter = { start, end, label: labelText };
        if (label) label.textContent = labelText;
        menu.style.display = 'none';
        attemptRender();
    }
    window.CM_APPLY_DATE_FILTER = applyFilter;

    function applyCustomRange() {
        const sVal = startInput.value;
        const eVal = endInput.value;
        if (!sVal && !eVal) return;
        const sTs = sVal ? Math.floor(new Date(sVal + 'T00:00:00').getTime() / 1000) : null;
        const eTs = eVal ? Math.floor(new Date(eVal + 'T23:59:59').getTime() / 1000) : null;
        const customLabel = sVal && eVal ? `${sVal} to ${eVal}` : (sVal ? `From ${sVal}` : `Until ${eVal}`);
        applyFilter(sTs, eTs, customLabel);
    }

    function syncDateConstraints(changedInput) {
        if (!startInput || !endInput) return;
        const todayStr = getLocalYMD();
        
        // 1. Hard ceiling against selecting future dates
        startInput.max = startInput.max && startInput.max < todayStr ? startInput.max : todayStr;
        endInput.max = todayStr;

        // 2. Prevent logical overlapping (End cannot precede Start)
        if (startInput.value && endInput.value) {
            if (startInput.value > endInput.value) {
                if (changedInput === startInput) endInput.value = startInput.value;
                else startInput.value = endInput.value;
            }
        }

        // 3. Bind interactive min/max guardrails directly to HTML limits
        if (startInput.value) endInput.min = startInput.value;
        else endInput.removeAttribute('min');
        
        if (endInput.value) {
            startInput.max = endInput.value < todayStr ? endInput.value : todayStr;
        }
    }

    toggle.addEventListener('click', (e) => {
        e.stopPropagation();
        const isOpen = menu.style.display === 'flex';
        menu.style.display = isOpen ? 'none' : 'flex';
        if (!isOpen) renderMenu();
    });

    document.addEventListener('click', (e) => {
        if (!menu.contains(e.target) && !toggle.contains(e.target)) {
            menu.style.display = 'none';
        }
    });

    if (cancelBtn) {
        cancelBtn.addEventListener('click', () => {
            if (customPanel) customPanel.style.display = 'none';
            if (toggle) toggle.style.display = 'inline-flex';
            
            // Revert state variables & inputs
            startInput.value = '';
            endInput.value = '';
            startInput.removeAttribute('max');
            endInput.removeAttribute('min');
            
            // Re-apply "All history" specifically required by cancel action
            applyFilter(null, null, 'All history');
        });
    }

    // Bind native date picker execution blocks
    if (startInput) {
        startInput.max = getLocalYMD();
        startInput.addEventListener('click', () => { try { startInput.showPicker(); } catch(e){} });
        startInput.addEventListener('change', () => {
            syncDateConstraints(startInput);
            applyCustomRange();
            if (startInput.value && endInput && !endInput.value) {
                setTimeout(() => { try { endInput.showPicker(); } catch(e){} }, 50);
            }
        });
    }

    if (endInput) {
        endInput.max = getLocalYMD();
        endInput.addEventListener('click', () => { try { endInput.showPicker(); } catch(e){} });
        endInput.addEventListener('change', () => {
            syncDateConstraints(endInput);
            applyCustomRange();
        });
    }
}
