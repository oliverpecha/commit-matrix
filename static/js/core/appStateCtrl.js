import { APP_STATES } from "./state.js";
import { applyLayout } from "../ui/layoutCtrl.js";
import { deriveLayout, hasLedgerData } from "./layoutPolicy.js";

window.CM_APP_STATE = window.CM_APP_STATE || APP_STATES.ZERO;

export function getAppState() {
    return window.CM_APP_STATE || APP_STATES.ZERO;
}

export function setAppState(state) {
    window.CM_APP_STATE = state;
    return applyLayout(deriveLayout(state));
}

export function syncInitialAppState() {
    return setAppState(hasLedgerData() ? APP_STATES.DASHBOARD_READY : APP_STATES.ZERO);
}

export function beginScanState() {
    return setAppState(hasLedgerData() ? APP_STATES.DASHBOARD_STREAMING : APP_STATES.INGESTION_BOOT);
}

export function onFirstChunkState() {
    if (!hasLedgerData()) {
        return setAppState(APP_STATES.INGESTION_STREAMING_FIRST);
    }
    return setAppState(APP_STATES.DASHBOARD_STREAMING);
}

export function onLedgerAvailableState() {
    return setAppState(hasLedgerData() ? APP_STATES.INGESTION_STREAMING_WITH_LEDGER : APP_STATES.INGESTION_STREAMING_FIRST);
}

export function onPauseState() {
    return setAppState(APP_STATES.PAUSED);
}

export function onPlayState() {
    return setAppState(hasLedgerData() ? APP_STATES.DASHBOARD_STREAMING : APP_STATES.INGESTION_STREAMING_FIRST);
}

export function onCompleteState() {
    return setAppState(hasLedgerData() ? APP_STATES.COMPLETE_PENDING_CLOSE : APP_STATES.ZERO);
}

export function onFailureState() {
    return setAppState(APP_STATES.FAILED);
}
