import { UI_STATE } from "../core/state.js?v=0.1.436";
import { getLiveSort, setLiveSort, syncHeaderCarets } from "./tableState.js?v=0.1.436";
import { getTableColumns, normalizeCommits, sortDisplayData, renderTableRowsBatched, initInfiniteScroll, syncTableHeaders } from "./tableRender.js?v=0.1.436";
export function renderTable(commits) {
    const thead = document.getElementById("cm-thead");
    const tbody = document.getElementById("cm-tbody");
    if (!thead || !tbody) return;

    const columns = getTableColumns();

    syncTableHeaders();

    if (!window.__THEAD_BOUND) {
        thead.addEventListener("click", (e) => {
            const th = e.target.closest("th[data-col]");
            if (!th) return;
            if (window.CM_SIDE_STREAM_ACTIVE) return;

            const colKey = th.getAttribute("data-col");
            const currentSort = getLiveSort();
            
            if (currentSort.col === colKey) {
                setLiveSort({ col: colKey, asc: !currentSort.asc });
            } else {
                setLiveSort({ col: colKey, asc: false });
            }

            syncHeaderCarets(columns);
            renderTable(window.CM_CURRENT_FILTERED_PAYLOAD || window.MATRIX_PAYLOAD || []);
        });
        window.__THEAD_BOUND = true;
    }

    const currentSort = getLiveSort();
    syncHeaderCarets(columns);

        // Force clear the table body on render to prevent the massive attached DOM leak
    tbody.innerHTML = '';
    
    // Discard stale SSR payload that lacks subjects so the API can backfill perfectly
    if (commits && commits.length > 0 && !commits[0].s && !commits[0].subject) {
        commits = [];
        if (window.MATRIX_PAYLOAD) window.MATRIX_PAYLOAD = [];
    }
    
    const searchInput = document.getElementById("cm-ledger-search");
    const clearBtn = document.getElementById("cm-search-clear");

    if (searchInput && !window.__SEARCH_BOUND) {
        searchInput.addEventListener("input", () => {
            if (clearBtn) clearBtn.style.display = searchInput.value.length > 0 ? "block" : "none";
            renderTable(window.CM_CURRENT_FILTERED_PAYLOAD || window.MATRIX_PAYLOAD || []);
        });
        if (clearBtn) {
            clearBtn.addEventListener("click", () => {
                searchInput.value = "";
                clearBtn.style.display = "none";
                renderTable(window.CM_CURRENT_FILTERED_PAYLOAD || window.MATRIX_PAYLOAD || []);
            });
        }
        window.__SEARCH_BOUND = true;
    }

    if (clearBtn && searchInput) {
        clearBtn.style.display = searchInput.value.length > 0 ? "block" : "none";
    }

    let filteredCommits = commits;
    if (searchInput && searchInput.value.trim()) {
        const q = searchInput.value.trim().toLowerCase();
        filteredCommits = commits.filter(c => JSON.stringify(c).toLowerCase().includes(q));
    }
    
    const displayData = sortDisplayData(normalizeCommits(filteredCommits), currentSort);
    
    if (displayData.length === 0) {
        const isFilterActive = !!(UI_STATE.dateFilter?.start || UI_STATE.dateFilter?.end || (searchInput && searchInput.value.trim()));
        const isIncoming = UI_STATE.dateFilter?.mode === 'incoming';
        const emptyMsg = isIncoming
            ? "Waiting for incoming commits from the active scan..."
            : (isFilterActive ? "No commits match the selected filter or search window." : "No commits recorded in this ledger.");
        tbody.innerHTML = `<tr><td colspan="100%" style="text-align:center; padding:56px 16px; color:#7a7874; font-size:13px; font-weight:500;">${emptyMsg}</td></tr>`;
    } else {
        const batchSize = UI_STATE.dateFilter?.mode === 'incoming' ? Math.max(100, displayData.length) : 100;
        renderTableRowsBatched(displayData, "cm-tbody", batchSize, true);
    }
    
    const repo = new URLSearchParams(window.location.search).get("repo") || "";
    const rawPayload = window.MATRIX_PAYLOAD_RAW || window.MATRIX_PAYLOAD || [];
    const rawOffset = rawPayload.length > 0 ? rawPayload.length : commits.length;
    const df = UI_STATE.dateFilter || { start: null, end: null };
    initInfiniteScroll(repo, rawOffset, df.start, df.end);
}

window.setTableStreamMode = function(isActive, opts = {}) {
    window.CM_SIDE_STREAM_ACTIVE = !!isActive;

    if (typeof opts.asc === "boolean") {
        window.CM_SIDE_STREAM_ASC = opts.asc;
    }

    if (!isActive) {
        setLiveSort({ col: "n", asc: false });
    }

    renderTable(window.CM_CURRENT_FILTERED_PAYLOAD || window.MATRIX_PAYLOAD || []);
};
