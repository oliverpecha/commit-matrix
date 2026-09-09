import { TYPE_COLORS, SCOPE_COLORS } from '../constants/colors.js?v=0.1.165';

const formatTableDate = (ts) => {
    if (!ts) return "Unknown";
    const d = new Date(ts * 1000);
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" }) + ", '" + d.getFullYear().toString().slice(-2);
};

const parseCommit = (subject) => {
    const match = subject.match(/^([a-zA-Z]+)(?:\(([^)]+)\))?:\s*(.+)$/);
    if (match) return { type: match[1], scope: match[2] || "", desc: match[3] };
    return { type: "commit", scope: "", desc: subject };
};

const getTypeColor = (type) => TYPE_COLORS?.[String(type).toLowerCase()] || "#888888";
const getScopeColor = (scope) => SCOPE_COLORS?.[String(scope).toLowerCase()] || "#aaaaaa";


const TIER_ICONS = {
    'Pivotal': `<svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor" style="margin-right:6px;"><path d="M11.13 2.76a1 1 0 011.74 0l9.26 16.05a1 1 0 01-.87 1.5H2.74a1 1 0 01-.87-1.5l9.26-16.05z"/></svg>`,
    'Core': `<svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor" style="margin-right:6px;"><rect x="3" y="3" width="18" height="18" rx="4"/></svg>`,
    'Minor': `<svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor" style="margin-right:6px;"><rect x="4" y="10" width="16" height="4" rx="2"/></svg>`
};

export function getTableColumns() {
        return [
        { label: "#", key: "n", align: "left" },
        { label: "AUTHORED", key: "ts", align: "left" },
        { label: "TIER", key: "tot", align: "left" },
        { label: "TYPE", key: "p_type", align: "left" },
        { label: "SCOPE", key: "p_scope", align: "left" },
        { label: "SUBJECT", key: "p_desc", align: "left" },
        { label: "SCORE", key: "tot", align: "center" },
        { label: "C", key: "C", align: "center" },
        { label: "I", key: "I", align: "center" },
        { label: "R", key: "R", align: "center" },
        { label: "S", key: "S", align: "center" },
        { label: "D", key: "D", align: "center" },
        { label: "HASH", key: "h", align: "left" },
        { label: "+", key: "lines_added", align: "center" },
        { label: "-", key: "lines_deleted", align: "center" }
    ];
}

export function normalizeCommits(commits) {
    return (commits || []).map(c => {
        const p = parseCommit(c.s || c.subject || "");
        return {
            ...c,
            n: Number(c.n) || 0,
            ts: Number(c.ts) || 0,
            C: Number(c.C) || 0,
            I: Number(c.I) || 0,
            R: Number(c.R) || 0,
            S: Number(c.S) || 0,
            D: Number(c.D) || 0,
            tot: Number(c.tot) || 0,
            lines_added: Number(c.lines_added) || 0,
            lines_deleted: Number(c.lines_deleted) || 0,
            p_type: c.p_type || c.t || c.type || p.type,
            p_scope: c.p_scope || c.scope || p.scope,
            p_desc: c.p_desc || p.desc || c.s || c.subject || ""
        };
    });
}

export function sortDisplayData(displayData, currentSort) {
    displayData.sort((a, b) => {
        let valA = a[currentSort.col];
        let valB = b[currentSort.col];

        const numericColumns = ["n", "C", "I", "R", "S", "D", "tot", "lines_added", "lines_deleted", "ts"];
        if (numericColumns.includes(currentSort.col)) {
            valA = Number(valA) || 0;
            valB = Number(valB) || 0;
            return currentSort.asc ? (valA - valB) : (valB - valA);
        }

        if (valA === undefined || valA === null) valA = "";
        if (valB === undefined || valB === null) valB = "";
        if (typeof valA === "string") valA = valA.toLowerCase();
        if (typeof valB === "string") valB = valB.toLowerCase();

        if (valA < valB) return currentSort.asc ? -1 : 1;
        if (valA > valB) return currentSort.asc ? 1 : -1;
        return 0;
    });

    return displayData;
}

export function renderTableRows(displayData) {
    const repo = new URLSearchParams(window.location.search).get("repo") || "";
    
    if (displayData && displayData.length > 0 && !window._DEBUG_COLOR_LOGGED) {
        window._DEBUG_COLOR_LOGGED = true;
        console.log("🎨 Table Color Mapping Debug:");
        console.table(displayData.slice(0, 10).map(c => ({
            Row: c.n,
            Type: c.p_type,
            TypeColor: getTypeColor(c.p_type),
            Scope: c.p_scope,
            ScopeColor: getScopeColor(c.p_scope)
        })));
    }

    return displayData.map((c) => {
        const tc = getTypeColor(c.p_type);
        const sc = getScopeColor(c.p_scope);
        const tierMap = { 'Critical': 'Pivotal', 'Significant': 'Core', 'Routine': 'Minor' };
        const displayTier = tierMap[c.tier] || c.tier || "N/A";
        const trC = displayTier === "Pivotal" ? "#D43BC6" : displayTier === "Core" ? "#36B8D8" : "#6F8197";
        
        
        const tStyle = tc === "#888888" ? `color:${tc}; font-size:11px; font-weight:700;` : `color:${tc}; border:1px solid ${tc}66; background:${tc}1A; padding:3px 8px; border-radius:4px; font-size:11px; font-weight:700; display:inline-block; line-height:1.2;`;
        const sStyle = sc === "#aaaaaa" ? `color:${sc}; font-size:11px; font-weight:700;` : `color:${sc}; border:1px solid ${sc}66; background:${sc}1A; padding:3px 8px; border-radius:4px; font-size:11px; font-weight:700; display:inline-block; line-height:1.2;`;

        return `
        <tr style="border-bottom: 1px solid rgba(255,255,255,0.02); transition: background 0.2s;" onmouseover="this.style.background='rgba(255,255,255,0.03)'" onmouseout="this.style.background='transparent'">
            <td style="padding:12px 8px; color:#7a7874; font-size:12px;">${c.n || "-"}</td>
            <td style="padding:12px 8px; color:#aaa; font-size:12px; white-space:nowrap;">
                <a target="_blank" rel="noopener noreferrer" href="https://github.com/oliverpecha/${repo}/commit/${c.h || c.hash_short}" style="color:inherit; text-decoration:none;" title="View Commit">${formatTableDate(c.ts)}</a>
            </td>
            <td style="padding:12px 8px;">
                <span style="color:${trC}; border:1px solid ${trC}; background:${trC}1A; padding:4px 12px; border-radius:20px; font-size:11px; font-weight:700; display:inline-flex; align-items:center; line-height:1.2;">${TIER_ICONS[displayTier] || ''}${displayTier}</span>
            </td>
            <td style="padding:12px 8px;"><span style="${tStyle}">${c.p_type}</span></td>
            <td style="padding:12px 8px;">${c.p_scope ? `<span style="${sStyle}">${c.p_scope}</span>` : ""}</td>
            <td style="padding:12px 8px; color:#ddd; font-size:13px; max-width:280px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${c.p_desc}">
                <a target="_blank" rel="noopener noreferrer" href="https://github.com/oliverpecha/${repo}/commit/${c.h || c.hash_short}" style="color:inherit; text-decoration:none; display:block; overflow:hidden; text-overflow:ellipsis;" title="View Commit">${c.p_desc}</a>
            </td>
            <td style="padding:12px 8px; text-align:center; font-weight:400; color:#fff; font-size:13px;">${c.tot}</td>
            <td style="padding:12px 8px; text-align:center; color:#5c91e0; font-weight:700; font-size:12px;">${c.C}</td>
            <td style="padding:12px 8px; text-align:center; color:#c99ef0; font-weight:700; font-size:12px;">${c.I}</td>
            <td style="padding:12px 8px; text-align:center; color:#ffb84d; font-weight:700; font-size:12px;">${c.R}</td>
            <td style="padding:12px 8px; text-align:center; color:#8ed068; font-weight:700; font-size:12px;">${c.S}</td>
            <td style="padding:12px 8px; text-align:center; color:#ff4b4b; font-weight:700; font-size:12px;">${c.D}</td>
            <td style="padding:12px 8px;">
                <a class="bp-hash" target="_blank" rel="noopener noreferrer" href="https://github.com/oliverpecha/${repo}/commit/${c.h || c.hash_short}" title="View Commit">${(c.h || c.hash_short || "").toString().substring(0, 7)}</a>
            </td>
            <td style="padding:12px 8px; text-align:center; color:#7a7874; font-size:12px;">+${c.lines_added}</td>
            <td style="padding:12px 8px; text-align:center; color:#7a7874; font-size:12px;">-${c.lines_deleted}</td>
        </tr>`;
    }).join("");
}


export function renderTableRowsBatched(displayData, tbodyId = "cm-tbody", batchSize = 100, replace = true) {
    const tbody = document.getElementById(tbodyId);
    if (!tbody) return;
    const currentGen = window.CM_RENDER_GEN;
    if (replace) tbody.innerHTML = "";

    let index = 0;

    function renderBatch() {
        if (currentGen !== window.CM_RENDER_GEN) return;
        const fragment = document.createDocumentFragment();
        const end = Math.min(index + batchSize, displayData.length);
        const batch = displayData.slice(index, end);

        const tempDiv = document.createElement('tbody');
        tempDiv.innerHTML = renderTableRows(batch);
        
        while(tempDiv.firstChild) {
            fragment.appendChild(tempDiv.firstChild);
        }

        tbody.appendChild(fragment);
        index = end;

        if (index < displayData.length) {
            requestAnimationFrame(renderBatch);
        }
    }
    requestAnimationFrame(renderBatch);
}

export function initInfiniteScroll(repo, initialOffset = 100) {
    if (window.CM_SCROLL_ABORT) window.CM_SCROLL_ABORT.abort();
    if (window.CM_TABLE_OBSERVER) window.CM_TABLE_OBSERVER.disconnect();
    window.CM_SCROLL_ABORT = new AbortController();

    let offset = initialOffset;
    const limit = 200;
    let isLoading = false;
    let hasMore = true;

    const observer = new IntersectionObserver(async (entries) => {
        if (entries[0].isIntersecting && !isLoading && hasMore) {
            isLoading = true;
            try {
                const rubric = new URLSearchParams(window.location.search).get("rubric") || window.MATRIX_DEFAULT_RUBRIC || "unknown";
                const res = await fetch(`/api/ledger?repo=${repo}&rubric=${rubric}&offset=${offset}&limit=${limit}`, { signal: window.CM_SCROLL_ABORT.signal });
                const data = await res.json();
                
                if (!data || data.length === 0) {
                    hasMore = false;
                } else {
                    if (window.MATRIX_PAYLOAD) {
                        window.MATRIX_PAYLOAD = window.MATRIX_PAYLOAD.concat(data);
                    }
                    // --- AUTOMATED SORT VALIDATION ---
                    let _fractures = 0;
                    let _lastVal = Infinity;
                    let _payload = window.MATRIX_PAYLOAD || [];
                    for (let i = 0; i < _payload.length; i++) {
                        let _currentVal = parseInt(_payload[i]['#']);
                        if (!isNaN(_currentVal)) {
                            if (_currentVal === _lastVal) { console.error(`❌ DUPLICATE DETECTED: #${_currentVal} loaded multiple times.`); _fractures++; } else if (_currentVal > _lastVal) {
                                if (_fractures < 5) console.warn(`⚠️ UI Fracture at index ${i}: #${_currentVal} came after #${_lastVal}`);
                                _fractures++;
                            } else if (_lastVal !== Infinity && _lastVal - _currentVal > 1) {
                                if (_fractures < 5) console.warn(`⚠️ UI Gap at index ${i}: skipped from #${_lastVal} to #${_currentVal}`);
                                _fractures++;
                            }
                            _lastVal = _currentVal;
                        }
                    }
                    if (_fractures === 0) {
                        console.log(`✅ SUCCESS: Frontend payload (${_payload.length} rows) is in perfect descending order!`);
                    } else {
                        console.error(`❌ FAILED: Found ${_fractures} sorting anomalies in the frontend payload.`);
                    }
                    // ---------------------------------
                    const normalized = normalizeCommits(data);
                    renderTableRowsBatched(normalized, "cm-tbody", 100, false);
                    offset += data.length;
                }
            } catch (e) {
                if (e.name !== "AbortError") console.error("Ledger pagination failed", e);
            }
            isLoading = false;
        }
    }, { rootMargin: '300px' });

    const sentinel = document.getElementById('cm-table-sentinel');
    window.CM_TABLE_OBSERVER = observer;
    if (sentinel) observer.observe(sentinel);
}
