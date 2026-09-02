import { APP_STATES } from "./state.js?v=0.7.75";
import { applyLayout } from "../ui/layoutCtrl.js?v=0.7.75";
import { deriveLayout, hasLedgerData } from "./layoutPolicy.js?v=0.7.75";

window.CM_APP_STATE = window.CM_APP_STATE || APP_STATES.ZERO;

function isEffectivelyEmpty() {
    return window.MATRIX_SYSTEM_EMPTY === true || !hasLedgerData();
}

export function getAppState() {
    return window.CM_APP_STATE || APP_STATES.ZERO;
}

export function setAppState(state) {
    window.CM_APP_STATE = state;
    return applyLayout(deriveLayout(state));
}

export function syncInitialAppState() {
    if (window.MATRIX_SYSTEM_EMPTY) {
        window.CM_APP_STATE = 'SYSTEM_EMPTY';
        return; // Abort standard layout application to prevent UI overlapping with pageBoot's Welcome Screen
    }
    return setAppState(hasLedgerData() ? APP_STATES.DASHBOARD_READY : APP_STATES.ZERO);
}

export function beginScanState() {
    return setAppState(!isEffectivelyEmpty() ? APP_STATES.DASHBOARD_STREAMING : APP_STATES.INGESTION_BOOT);
}

export function onFirstChunkState() {
    if (isEffectivelyEmpty()) {
        return setAppState(APP_STATES.INGESTION_STREAMING_FIRST);
    }
    return setAppState(APP_STATES.DASHBOARD_STREAMING);
}

export function onLedgerAvailableState() {
    return setAppState(!isEffectivelyEmpty() ? APP_STATES.INGESTION_STREAMING_WITH_LEDGER : APP_STATES.INGESTION_STREAMING_FIRST);
}

export function onPauseState() {
    return setAppState(APP_STATES.PAUSED);
}

export function onPlayState() {
    return setAppState(!isEffectivelyEmpty() ? APP_STATES.DASHBOARD_STREAMING : APP_STATES.INGESTION_STREAMING_FIRST);
}

export function onCompleteState() {
    return setAppState(!isEffectivelyEmpty() ? APP_STATES.COMPLETE_PENDING_CLOSE : APP_STATES.ZERO);
}

export function onFailureState() {
    return setAppState(APP_STATES.FAILED);
}

export function hasSeenLedger() {
    return !isEffectivelyEmpty();
}

export function markLedgerSeen() {
    return setAppState(APP_STATES.INGESTION_STREAMING_WITH_LEDGER);
}

export function initAppStateFromLedger() {
    return syncInitialAppState();
}
