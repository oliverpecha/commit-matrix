import { hub } from "../core/eventHub.js";
import { APP_STATES } from "../core/state.js";
import {
    getAppState,
    setAppState,
    markLedgerSeen,
    hasSeenLedger,
    initAppStateFromLedger,
} from "../core/appStateCtrl.js";
import { renderCliOverlay } from "./terminalCliOverlay.js";
import {
    renderShell,
    appendTerminalChunk,
    showPauseButton,
    setTerminalPaused,
    setTerminalProcessing,
    setTerminalComplete,
    setTerminalFailed,
} from "./terminalRenderCtrl.js";
import {
    resetCloseLifecycle,
    scheduleAutoClose,
    cancelAutoClose,
} from "./terminalLifecycle.js";

function renderShellForCurrentState() {
    const termSlot = setAppState(getAppState());
    return renderShell(termSlot, hub);
}

hub.on("UI:SHOW_CLI_INSTRUCTIONS", () => {
    setAppState(hasSeenLedger() ? APP_STATES.DASHBOARD_STREAMING : APP_STATES.INGESTION_BOOT);
    const termSlot = setAppState(getAppState());
    renderCliOverlay(termSlot, hub);
});

hub.on("ENGINE:SCAN_REQUESTED", () => {
    resetCloseLifecycle();
    setAppState(hasSeenLedger() ? APP_STATES.DASHBOARD_STREAMING : APP_STATES.INGESTION_BOOT);
    renderShellForCurrentState();
});

hub.on("DATA:FIRST_CHUNK_RECEIVED", () => {
    if (!hasSeenLedger()) {
        setAppState(APP_STATES.INGESTION_STREAMING_FIRST);
        renderShellForCurrentState();
    }
});

hub.on("ENGINE:CHUNK_RECEIVED", ({ chunk }) => {
    const appended = appendTerminalChunk(chunk);
    if (!appended) return;

    if (chunk.includes("🐳 ENGINE INITIALIZED CONTAINER")) {
        showPauseButton();
    }

    if (chunk.includes("Queued for ledger flush")) {
        markLedgerSeen();
        if ([APP_STATES.INGESTION_BOOT, APP_STATES.INGESTION_STREAMING_FIRST].includes(getAppState())) {
            setAppState(APP_STATES.INGESTION_STREAMING_WITH_LEDGER);
            renderShellForCurrentState();
        }
    }
});

hub.on("ENGINE:CONTROL_UPDATED", ({ action, status }) => {
    if (action === "pause" && status === "paused") {
        setAppState(APP_STATES.PAUSED);
        setTerminalPaused();
    }

    if (action === "play" && status === "running") {
        setAppState(hasSeenLedger() ? APP_STATES.DASHBOARD_STREAMING : APP_STATES.INGESTION_STREAMING_FIRST);
        setTerminalProcessing();
    }
});

hub.on("ENGINE:SCAN_COMPLETE", ({ success }) => {
    if (success) {
        setAppState(APP_STATES.COMPLETE_PENDING_CLOSE);
        setTerminalComplete();
        if (window.triggerSilentRefresh) window.triggerSilentRefresh();
        scheduleAutoClose(window.MATRIX_TIME_AUTOCLOSE ?? 5);
    } else {
        setAppState(APP_STATES.FAILED);
        setTerminalFailed();
    }
});

hub.on("ENGINE:EXIT_REQUESTED", () => {
    cancelAutoClose();
});

document.addEventListener("DOMContentLoaded", () => {
    initAppStateFromLedger();
    setAppState(getAppState());
});
