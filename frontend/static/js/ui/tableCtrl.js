import { getLiveSort, setLiveSort, syncHeaderCarets } from "./tableState.js?v=0.1.234";
import { getTableColumns, normalizeCommits, sortDisplayData, renderTableRowsBatched, initInfiniteScroll } from "./tableRender.js?v=0.1.234";
export function renderTable(commits) {
    const thead = document.getElementById("cm-thead");
    const tbody = document.getElementById("cm-tbody");
    if (!thead || !tbody) return;

    const columns = getTableColumns();

    if (thead.children.length === 0) {
        const tr = document.createElement("tr");
        columns.forEach(col => {
            const th = document.createElement("th");
            th.style.cssText = `text-align:${col.align}; padding:12px 8px; color:#7a7874; font-size:10px; font-weight:800; letter-spacing:1px; border-bottom:1px solid rgba(255,255,255,0.05); cursor:pointer; user-select:none; white-space:nowrap; transition: color 0.2s;`;
            const ttKeyMap = {
                'c': 'cirsd_C', 'i': 'cirsd_I', 'r': 'cirsd_R', 's': 'cirsd_S', 'd': 'cirsd_D',
                'n': 'table_n', 'tot': 'table_tot', 'score': 'table_tot', 'la': 'table_la', 'ld': 'table_ld'
            };
            const ttKey = ttKeyMap[col.key] || ttKeyMap[(col.key || '').toLowerCase()];
            const labelHtml = ttKey ? `<span class="info-hover" data-key="${ttKey}">${col.label}</span>` : col.label;
            th.innerHTML = `${labelHtml} <span class="sort-icon" style="font-size:10px; margin-left:4px;"></span>`;

            th.onclick = () => {
                if (window.CM_SIDE_STREAM_ACTIVE) return;

                const currentSort = getLiveSort();
                if (currentSort.col === col.key) {
                    setLiveSort({ col: col.key, asc: !currentSort.asc });
                } else {
                    setLiveSort({ col: col.key, asc: false });
                }

                syncHeaderCarets(columns);
                renderTable(window.MATRIX_PAYLOAD || []);
            };

            tr.appendChild(th);
        });
        thead.appendChild(tr);
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
    const displayData = sortDisplayData(normalizeCommits(commits), currentSort);
    renderTableRowsBatched(displayData, "cm-tbody", 100, true);
    
    const repo = new URLSearchParams(window.location.search).get("repo") || "";
    initInfiniteScroll(repo, commits.length);
}

window.setTableStreamMode = function(isActive, opts = {}) {
    window.CM_SIDE_STREAM_ACTIVE = !!isActive;

    if (typeof opts.asc === "boolean") {
        window.CM_SIDE_STREAM_ASC = opts.asc;
    }

    if (!isActive) {
        setLiveSort({ col: "n", asc: false });
    }

    renderTable(window.MATRIX_PAYLOAD || []);
};
