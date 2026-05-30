import { APP_STATES, LAYOUTS } from "./state.js";

export function getLedgerCount() {
    return Array.isArray(window.MATRIX_PAYLOAD) ? window.MATRIX_PAYLOAD.length : 0;
}

export function hasLedgerData() {
    return getLedgerCount() > 0;
}

export function deriveLayout(state) {
    const ledgerCount = getLedgerCount();

    if (state === APP_STATES.ZERO) return LAYOUTS.ZERO_LAYOUT;

    if ([APP_STATES.INGESTION_BOOT, APP_STATES.INGESTION_STREAMING_FIRST].includes(state)) {
        return LAYOUTS.TERMINAL_SLOT_LAYOUT;
    }

    if ([APP_STATES.INGESTION_STREAMING_WITH_LEDGER, APP_STATES.DASHBOARD_STREAMING, APP_STATES.COMPLETE_PENDING_CLOSE].includes(state)) {
        return ledgerCount > 0 ? LAYOUTS.SIDE_LAYOUT : LAYOUTS.TERMINAL_SLOT_LAYOUT;
    }

    if (state === APP_STATES.PAUSED) {
        return ledgerCount > 0 ? LAYOUTS.SIDE_LAYOUT : LAYOUTS.TERMINAL_SLOT_LAYOUT;
    }

    if (state === APP_STATES.FAILED) {
        return ledgerCount > 0 ? LAYOUTS.SIDE_LAYOUT : LAYOUTS.TERMINAL_SLOT_LAYOUT;
    }

    return ledgerCount > 0 ? LAYOUTS.DASHBOARD_LAYOUT : LAYOUTS.ZERO_LAYOUT;
}
