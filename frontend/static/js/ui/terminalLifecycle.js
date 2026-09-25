import { hub } from "../core/eventHub.js?v=0.1.436";
import { showAutoCloseToast, clearAutoCloseToast } from "./autoCloseToast.js?v=0.1.436";
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
    
    // 1. Emit the close event to restore the Date Filter state
    hub.emit("ACTION:CLOSE_TERMINAL");
    
    // 2. Gracefully hide the terminal UI and restore DOM layout
    setTimeout(() => {
        const slots = ["cm-terminal-slot", "cm-native-terminal-slot", "cm-terminal-overlay"];
        slots.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.style.display = "none";
        });
        document.body.classList.remove("incoming-boot", "incoming-boot-leaving");
        
        // Inline robust layout restoration
        const wrap = document.getElementById("main-dashboard-wrap");
        const leftCol = document.getElementById("cm-left-col");
        const rightCol = document.getElementById("cm-right-col");
        
        if (wrap && leftCol && rightCol) {
            wrap.dataset.layout = "";
            wrap.style.display = "";
            wrap.style.gridTemplateColumns = "";
            wrap.style.alignItems = "";
            wrap.style.gap = "";
            wrap.style.height = "";
            wrap.style.overflow = "";
            
            const allChildren = [...Array.from(leftCol.children), ...Array.from(rightCol.children)];
            allChildren.forEach(child => {
                if (child.id === "cm-native-terminal-slot") {
                    child.remove(); // Safely discard terminal UI slot
                } else {
                    if (child.id === "cm-ledger-card") {
                        child.style.flex = "";
                        child.style.minHeight = "";
                        child.style.height = "";
                        child.style.display = "";
                        child.style.flexDirection = "";
                        const tblWrap = child.querySelector(".cm-tbl-wrap");
                        if (tblWrap) {
                            tblWrap.style.flex = "";
                            tblWrap.style.height = "";
                            tblWrap.style.maxHeight = "";
                            tblWrap.style.overflowY = "";
                        }
                    }
                    wrap.appendChild(child); // Push back to main container
                }
            });
            leftCol.remove();
            rightCol.remove();
            
            // Force charts to adapt to their new full-width containers
            setTimeout(() => {
                window.dispatchEvent(new Event('resize'));
                if (typeof window.attemptRender === 'function') {
                    window.attemptRender();
                }
            }, 50); // Yield a frame for the DOM to settle
        }

        // Un-flag so future syncs work on the same page
        setTimeout(() => {
            window.CM_CLOSE_IN_PROGRESS = false;
            closeInFlight = false;
        }, 300);
    }, 150);
}

export function cancelAutoClose() {
    clearCloseTimer();
    clearAutoCloseToast(document.getElementById("cm-terminal-toast-slot"));
}

export function scheduleAutoClose(seconds) {
    const toastSlot = document.getElementById("cm-terminal-toast-slot");

    const closeIfLedgerExists = () => {
        const hasLedger = (Array.isArray(window.MATRIX_CHART_PAYLOAD) && window.MATRIX_CHART_PAYLOAD.length > 0) || (Array.isArray(window.MATRIX_PAYLOAD) && window.MATRIX_PAYLOAD.length > 0);
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

hub.on("CONTEXT_CHANGED", () => {
    if (window.CM_CLOSE_IN_PROGRESS || closeInFlight) return;
    cancelAutoClose();
    // Do not hard reload the page, just clear the terminal state flag
    window.CM_CLOSE_IN_PROGRESS = false;
    closeInFlight = false;
});
