import { getLiveSort, setLiveSort, syncHeaderCarets } from "./tableState.js";
import { getTableColumns, normalizeCommits, sortDisplayData, renderTableRows } from "./tableRender.js";

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
            th.innerHTML = `${col.label} <span class="sort-icon" style="font-size:10px; margin-left:4px;"></span>`;

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

    const displayData = sortDisplayData(normalizeCommits(commits), currentSort);
    tbody.innerHTML = renderTableRows(displayData);
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
