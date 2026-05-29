export function getDashElements() {
    return document.querySelectorAll('.cm-row, .cm-kpi-row, #cm-ledger-card');
}

export function showZeroState() {
    const zs = document.getElementById("cm-zero-state");
    if (zs) zs.style.display = "flex";
}

export function hideZeroState() {
    const zs = document.getElementById("cm-zero-state");
    if (zs) zs.style.display = "none";
}

export function showDashboard() {
    getDashElements().forEach(el => el.style.display = "");
}

export function hideDashboard() {
    getDashElements().forEach(el => el.style.display = "none");
}
