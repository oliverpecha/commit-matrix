// Centralized Zero & Empty State Controller

function getDashboardElements() {
    const rows = document.querySelectorAll('.cm-row');
    const flexes = document.querySelectorAll('.cm-kpi-row, #cm-ledger-card');
    const actions = document.querySelectorAll('#cm-header-actions, .cm-header-actions, #cm-toolbar, .cm-toolbar, #cm-actions, .cm-actions');
    const wrap = document.getElementById("main-dashboard-wrap");
    return { rows, flexes, actions, wrap };
}

export function hideZeroStates() {
    const { rows, flexes, actions, wrap } = getDashboardElements();
    rows.forEach(el => el.style.display = '');
    flexes.forEach(el => el.style.display = '');
    actions.forEach(el => el.style.display = '');
    
    const zs = document.getElementById('cm-zero-state');
    if (zs) zs.remove();
    const fzs = document.getElementById('cm-filtered-zero-state');
    if (fzs) fzs.remove();
    if (wrap) wrap.style.opacity = "1";
}

export function showTotalZeroState(errorMsg = "") {
    const { rows, flexes, actions, wrap } = getDashboardElements();
    rows.forEach(el => el.style.display = 'none');
    flexes.forEach(el => el.style.display = 'none');
    actions.forEach(el => el.style.display = 'none');
    if (wrap) wrap.style.opacity = "1";

    const fzs = document.getElementById('cm-filtered-zero-state');
    if (fzs) fzs.remove();

    if (window.MATRIX_INVALID_OWNER || window.MATRIX_INVALID_REPO || window.MATRIX_INVALID_RUBRIC) return;

    let zs = document.getElementById('cm-zero-state');
    if (!zs && wrap) {
        zs = document.createElement("div");
        zs.id = "cm-zero-state";
        zs.style.cssText = "position:fixed; left:50%; top:45%; transform:translate(-50%, -50%); display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; font-family:Satoshi, sans-serif; z-index:50; width:100%;";
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

function findNearestCommit(commits, startTs, endTs) {
    if (!commits || commits.length === 0) return null;
    let nearest = null;
    let minDistance = Infinity;

    for (const c of commits) {
        const ts = Number(c.ts);
        if (!ts || isNaN(ts)) continue;
        let distance = 0;
        if (startTs && endTs) {
            if (ts < startTs) distance = startTs - ts;
            else if (ts > endTs) distance = ts - endTs;
            else distance = 0;
        } else if (startTs) {
            distance = Math.abs(ts - startTs);
        } else if (endTs) {
            distance = Math.abs(ts - endTs);
        }
        if (distance < minDistance) {
            minDistance = distance;
            nearest = c;
        }
    }
    return nearest;
}

export function showFilteredZeroState({ filter = {}, allCommits = [], onRevert = null, lastGoodFilter = null }) {
    const { rows, flexes, actions, wrap } = getDashboardElements();
    
    // Hide empty dashboard cards and tables, but keep top header/actions visible
    rows.forEach(el => el.style.display = 'none');
    flexes.forEach(el => el.style.display = 'none');
    actions.forEach(el => el.style.display = '');
    if (wrap) wrap.style.opacity = "1";

    const zs = document.getElementById('cm-zero-state');
    if (zs) zs.remove();

    let fzs = document.getElementById('cm-filtered-zero-state');
    if (!fzs && wrap) {
        fzs = document.createElement("div");
        fzs.id = "cm-filtered-zero-state";
        fzs.style.cssText = "position:fixed; left:50%; top:45%; transform:translate(-50%, -50%); display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; font-family:Satoshi, sans-serif; z-index:45; width:100%; max-width:520px; padding:20px;";
        wrap.insertBefore(fzs, wrap.firstChild);
    }

    const formatMMDDYYYY = (val) => {
        if (!val) return '';
        if (typeof val === 'string') {
            return val.replace(/\b(\d{4})-(\d{2})-(\d{2})\b/g, '$2/$3/$1');
        }
        const d = new Date(val > 1e11 ? val : val * 1000);
        const mm = String(d.getMonth() + 1).padStart(2, '0');
        const dd = String(d.getDate()).padStart(2, '0');
        const yyyy = d.getFullYear();
        return `${mm}/${dd}/${yyyy}`;
    };

    // Determine headline
    let headline = "No activity in selected window";
    if (filter.label && filter.label !== "Custom" && !filter.label.startsWith("From ") && !filter.label.includes(" to ") && !filter.label.includes(" - ")) {
        headline = `No activity for "${filter.label}"`;
    } else if (filter.label && (filter.label.includes(" to ") || filter.label.startsWith("From ") || filter.label.startsWith("Until "))) {
        headline = `No activity for "${formatMMDDYYYY(filter.label)}"`;
    } else if (filter.start || filter.end) {
        if (filter.start && filter.end) {
            headline = `No activity between ${formatMMDDYYYY(filter.start)} – ${formatMMDDYYYY(filter.end)}`;
        } else if (filter.start) {
            headline = `No activity since ${formatMMDDYYYY(filter.start)}`;
        } else if (filter.end) {
            headline = `No activity prior to ${formatMMDDYYYY(filter.end)}`;
        }
    }

    // Find nearest commit
    const nearest = findNearestCommit(allCommits, filter.start, filter.end);
    let nearestText = "";
    if (nearest) {
        const nDate = formatMMDDYYYY(nearest.ts);
        const ref = nearest.n ? `#${nearest.n}` : (nearest.h || nearest.hash_short || "").substring(0, 7);
        nearestText = `Nearest commit was on ${nDate} (${ref}).`;
    }

    const rawTarget = lastGoodFilter?.label || "All history";
    const revertTarget = formatMMDDYYYY(rawTarget);

    fzs.innerHTML = `
        <div style="font-size:42px; margin-bottom:16px; opacity:0.85;">📅</div>
        <h2 style="color:#e0e0e0; margin-bottom:8px; font-weight:600; font-size:20px; letter-spacing:0.3px;">${headline}</h2>
        <p style="color:#888; font-size:14px; line-height:1.5; margin-bottom:8px;">Commit data exists outside this filter.</p>
        ${nearestText ? `<p style="color:#7a7874; font-size:13px; font-family:monospace; margin-bottom:26px;">${nearestText}</p>` : '<div style="margin-bottom:20px;"></div>'}
        <button id="cm-revert-filter-btn" style="background:#222; border:1px solid rgba(255,255,255,0.18); color:#e0e0e0; padding:9px 22px; border-radius:6px; font-size:13px; font-weight:600; cursor:pointer; font-family:Satoshi, sans-serif; transition:all 0.2s;" onmouseover="this.style.background='#2c2c2c'; this.style.borderColor='rgba(255,255,255,0.3)'" onmouseout="this.style.background='#222'; this.style.borderColor='rgba(255,255,255,0.18)'">
            Revert to "${revertTarget}"
        </button>
    `;

    const btn = document.getElementById("cm-revert-filter-btn");
    if (btn && typeof onRevert === "function") {
        btn.onclick = onRevert;
    }
}
