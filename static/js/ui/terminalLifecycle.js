import { hub } from "../core/eventHub.js";
import { showAutoCloseToast, clearAutoCloseToast } from "./autoCloseToast.js";

let closeInFlight = false;
let closeTimer = null;

export function clearCloseTimer() {
    if (closeTimer) {
        clearTimeout(closeTimer);
        closeTimer = null;
    }
}

export function resetCloseLifecycle() {
    closeInFlight = false;
    window.CM_CLOSE_IN_PROGRESS = false;
    clearCloseTimer();
    clearAutoCloseToast(document.getElementById("cm-terminal-toast-slot"));
}

export function closeTerminalPanel() {
    if (closeInFlight) return;
    closeInFlight = true;
    window.CM_CLOSE_IN_PROGRESS = true;
    clearCloseTimer();
    clearAutoCloseToast(document.getElementById("cm-terminal-toast-slot"));
    window.location.reload();
}

export function cancelAutoClose() {
    clearCloseTimer();
    clearAutoCloseToast(document.getElementById("cm-terminal-toast-slot"));
}

export function scheduleAutoClose(seconds) {
    const toastSlot = document.getElementById("cm-terminal-toast-slot");

    const closeIfLedgerExists = () => {
        const hasLedger = Array.isArray(window.MATRIX_PAYLOAD) && window.MATRIX_PAYLOAD.length > 0;
        if (hasLedger) {
            closeTerminalPanel();
        } else {
            window.CM_ZERO_AUTO_INIT_USED = true;
            cancelAutoClose();
        }
    };

    clearCloseTimer();

    showAutoCloseToast(
        toastSlot,
        seconds,
        () => closeIfLedgerExists(),
        () => cancelAutoClose()
    );

    closeTimer = setTimeout(() => closeIfLedgerExists(), seconds * 1000);
}

hub.on("ENGINE:EXIT_REQUESTED", () => {
    cancelAutoClose();
    closeTerminalPanel();
});
