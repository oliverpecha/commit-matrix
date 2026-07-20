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
