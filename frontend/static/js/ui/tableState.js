window.CM_SIDE_STREAM_ACTIVE = window.CM_SIDE_STREAM_ACTIVE || false;
window.CM_SIDE_STREAM_ASC = window.CM_SIDE_STREAM_ASC ?? true;
window.CM_TABLE_SORT = window.CM_TABLE_SORT || { col: "n", asc: false };

export function getLiveSort() {
    if (window.CM_SIDE_STREAM_ACTIVE) {
        return { col: "n", asc: !!window.CM_SIDE_STREAM_ASC };
    }
    return window.CM_TABLE_SORT || { col: "n", asc: false };
}

export function setLiveSort(sort) {
    window.CM_TABLE_SORT = { ...sort };
}

export function syncHeaderCarets(columns) {
    const thead = document.getElementById("cm-thead");
    if (!thead || thead.children.length === 0) return;

    const currentSort = getLiveSort();

    Array.from(thead.children[0].children).forEach((childTh, idx) => {
        const icon = childTh.querySelector(".sort-icon");
        if (!icon) return;

        if (columns[idx].key === currentSort.col) {
            childTh.style.color = "#fff";
            icon.style.opacity = "1";
            icon.textContent = currentSort.asc ? "▲" : "▼";
        } else {
            childTh.style.color = "#7a7874";
            icon.textContent = "";
        }
    });
}
