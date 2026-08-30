export const UI_STATE = {
    stack: false,
    trend: false,
    heat: false,
    frag: false,
    churn: false,
    blast: false,
    conv: false,
    avgTrend: 2,
    avgFrag: 2,
    avgChurn: 2,
    avgBlast: 2
};

export const APP_STATES = {
    ZERO: "ZERO",
    INGESTION_BOOT: "INGESTION_BOOT",
    INGESTION_STREAMING_FIRST: "INGESTION_STREAMING_FIRST",
    INGESTION_STREAMING_WITH_LEDGER: "INGESTION_STREAMING_WITH_LEDGER",
    DASHBOARD_READY: "DASHBOARD_READY",
    DASHBOARD_STREAMING: "DASHBOARD_STREAMING",
    PAUSED: "PAUSED",
    COMPLETE_PENDING_CLOSE: "COMPLETE_PENDING_CLOSE",
    FAILED: "FAILED"
};

export const LAYOUTS = {
    ZERO_LAYOUT: "ZERO_LAYOUT",
    TERMINAL_SLOT_LAYOUT: "TERMINAL_SLOT_LAYOUT",
    SIDE_LAYOUT: "SIDE_LAYOUT",
    DASHBOARD_LAYOUT: "DASHBOARD_LAYOUT"
};

window.CM_APP_STATE = window.CM_APP_STATE || APP_STATES.ZERO;

export const EVENTS = {
    SYNC_REQUESTED: "ACTION:REFRESH_LEDGER", // Legacy event name preserved for backend compat
    CLOSE_REQUESTED: "ACTION:CLOSE_TERMINAL"
};

const ICON_SYNC = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="display:inline-block; vertical-align:-2px; margin-right:6px;"><polyline points="23 4 23 10 17 10"></polyline><polyline points="1 20 1 14 7 14"></polyline><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path></svg>`;
const ICON_SPINNER = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="display:inline-block; vertical-align:-2px; margin-right:6px;"><circle cx="12" cy="12" r="10" stroke-opacity="0.25"></circle><path d="M12 2a10 10 0 0 1 10 10"><animateTransform attributeName="transform" type="rotate" from="0 12 12" to="360 12 12" dur="1s" repeatCount="indefinite"/></path></svg>`;

export const UI_LABELS = {
    SYNC_BTN_ACTIVE: `${ICON_SYNC}Sync Data`,
    SYNC_BTN_LOADING: `${ICON_SPINNER}Initializing...`
};

window.CM_RENDER_GEN = 0;
window.CM_ACTIVE_CONTEXT = null; // "repo::rubric"
window.CM_SCAN_ABORT = null;     // AbortController for active telemetry stream
window.CM_SCAN_CONTEXT = null;   // "repo::rubric" the current scan belongs to

export function contextKey(repo, rubric) {
    return `${repo}::${rubric}`;
}

export function bumpGeneration(repo, rubric) {
    window.CM_RENDER_GEN++;
    window.CM_ACTIVE_CONTEXT = contextKey(repo, rubric);
    
    if (window.CM_CANVAS_RO) { window.CM_CANVAS_RO.disconnect(); window.CM_CANVAS_RO = null; }
    if (window.CM_SCROLL_ABORT) { window.CM_SCROLL_ABORT.abort(); window.CM_SCROLL_ABORT = null; }
    if (window.CM_TABLE_OBSERVER) { window.CM_TABLE_OBSERVER.disconnect(); window.CM_TABLE_OBSERVER = null; }
    
    if (window.CM_SCAN_ABORT && window.CM_SCAN_CONTEXT !== window.CM_ACTIVE_CONTEXT) {
        window.CM_SCAN_ABORT.abort();
        window.CM_SCAN_ABORT = null;
        window.CM_SCAN_IN_FLIGHT = false;
    }
    
    return window.CM_RENDER_GEN;
}
