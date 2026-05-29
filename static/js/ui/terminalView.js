import { hub } from "../core/eventHub.js";
import { APP_STATES, LAYOUTS } from "../core/state.js";
import { applyLayout } from "./layoutCtrl.js";
import { renderTerminalShell } from "./terminalShell.js";
import { showAutoCloseToast, clearAutoCloseToast } from "./autoCloseToast.js";

let closeInFlight = false;
let closeTimer = null;
let firstLedgerSeen = false;

const stateToLayout = (state) => {
    if (state === APP_STATES.ZERO) return LAYOUTS.ZERO_LAYOUT;
    if ([APP_STATES.INGESTION_BOOT, APP_STATES.INGESTION_STREAMING_FIRST].includes(state)) return LAYOUTS.TERMINAL_SLOT_LAYOUT;
    if ([APP_STATES.INGESTION_STREAMING_WITH_LEDGER, APP_STATES.DASHBOARD_STREAMING, APP_STATES.PAUSED, APP_STATES.COMPLETE_PENDING_CLOSE].includes(state)) return LAYOUTS.SIDE_LAYOUT;
    if (state === APP_STATES.FAILED) return firstLedgerSeen ? LAYOUTS.SIDE_LAYOUT : LAYOUTS.TERMINAL_SLOT_LAYOUT;
    return LAYOUTS.DASHBOARD_LAYOUT;
};

const setAppState = (state) => {
    window.CM_APP_STATE = state;
    return applyLayout(stateToLayout(state));
};

const closeTerminalPanel = () => {
    if (closeInFlight) return;
    closeInFlight = true;
    window.CM_CLOSE_IN_PROGRESS = true;
    if (closeTimer) clearTimeout(closeTimer);
    hub.emit("ENGINE:EXIT_REQUESTED");
    window.location.reload();
};

const renderShellForCurrentState = () => {
    const termSlot = setAppState(window.CM_APP_STATE);
    if (!termSlot) return null;
    const shell = renderTerminalShell(termSlot);
    if (!shell) return null;

    shell.closeBtn.onclick = () => hub.emit("ACTION:CLOSE_TERMINAL");
    shell.pauseBtn.onclick = () => hub.emit("ACTION:TOGGLE_ENGINE", { action: "pause" });
    shell.playBtn.onclick = () => hub.emit("ACTION:TOGGLE_ENGINE", { action: "play" });
    return shell;
};

hub.on("UI:SHOW_CLI_INSTRUCTIONS", () => {
    window.CM_APP_STATE = firstLedgerSeen ? APP_STATES.DASHBOARD_STREAMING : APP_STATES.INGESTION_BOOT;
    const termSlot = setAppState(window.CM_APP_STATE);
    if (!termSlot) return;

    termSlot.innerHTML = `
    <div style="display:flex; flex-direction:column; background:#131314; border:1px solid rgba(255,255,255,0.08); padding:16px; font-family:monospace; border-radius:8px; height:100%; min-height:0; position:relative;">
        <div style="display:flex; justify-content:space-between; border-bottom:1px solid rgba(255,255,255,0.08); padding-bottom:12px; margin-bottom:12px; color:#aaa; font-family:Satoshi, sans-serif; font-size:13px; align-items:center; flex-shrink:0;">
            <span style="display:flex; align-items:center; gap:8px; font-weight:700; color:#8ab4f0;"><span style="font-size:15px;">⚡</span><span>CLI Ingestion Mode</span></span>
            <svg id="cm-btn-close-cli" style="cursor:pointer; width:16px; height:16px; fill:#777;" viewBox="0 0 24 24"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>
        </div>
        <div style="flex:1; min-height:0; overflow-y:auto; background:#070708; color:#a3e685; padding:16px; border-radius:6px; font-size:12px; line-height:1.6; border:1px solid rgba(255,255,255,0.04); white-space:pre-wrap; font-family:monospace;">
<span style="color:#8ab4f0;">> Waiting for local engine execution...</span>

To ingest a new repository, open your host terminal and run:

<span style="color:#fff; font-weight:bold; background:rgba(255,255,255,0.1); padding:2px 6px; border-radius:4px;">cd /path/to/your/repo</span>
<span style="color:#fff; font-weight:bold; background:rgba(255,255,255,0.1); padding:2px 6px; border-radius:4px;">commit-matrix</span>

<span style="color:#777;">(The dashboard will automatically detect the new ledger once analysis completes.)</span>
        </div>
    </div>`;
    document.getElementById("cm-btn-close-cli").onclick = () => hub.emit("ACTION:CLOSE_TERMINAL");
});

hub.on("ENGINE:SCAN_REQUESTED", () => {
    closeInFlight = false;
    window.CM_APP_STATE = firstLedgerSeen ? APP_STATES.DASHBOARD_STREAMING : APP_STATES.INGESTION_BOOT;
    clearAutoCloseToast(document.getElementById("cm-terminal-toast-slot"));
    renderShellForCurrentState();
});

hub.on("DATA:FIRST_CHUNK_RECEIVED", () => {
    if (!firstLedgerSeen) {
        window.CM_APP_STATE = APP_STATES.INGESTION_STREAMING_FIRST;
        renderShellForCurrentState();
    }
});

hub.on("ENGINE:CHUNK_RECEIVED", ({ chunk }) => {
    const body = document.getElementById("cm-terminal-body");
    if (!body) return;

    body.innerHTML += chunk.replace(/\[__MATRIX_EOF_.*__\]/g, "");
    body.scrollTop = body.scrollHeight;

    if (chunk.includes("🐳 ENGINE INITIALIZED CONTAINER")) {
        const pauseBtn = document.getElementById("cm-btn-pause");
        if (pauseBtn) pauseBtn.style.display = "block";
    }

    if (chunk.includes("Queued for ledger flush")) {
        firstLedgerSeen = true;
        if ([APP_STATES.INGESTION_BOOT, APP_STATES.INGESTION_STREAMING_FIRST].includes(window.CM_APP_STATE)) {
            window.CM_APP_STATE = APP_STATES.INGESTION_STREAMING_WITH_LEDGER;
            renderShellForCurrentState();
            const body2 = document.getElementById("cm-terminal-body");
            if (body2 && !body2.innerHTML.trim()) body2.innerHTML = body.innerHTML;
        }
    }
});

hub.on("ENGINE:CONTROL_UPDATED", ({ action, status }) => {
    const statusEl = document.getElementById("cm-terminal-status");
    const pauseBtn = document.getElementById("cm-btn-pause");
    const playBtn = document.getElementById("cm-btn-play");

    if (action === "pause" && status === "paused") {
        window.CM_APP_STATE = APP_STATES.PAUSED;
        if (statusEl) statusEl.innerHTML = `<span style="color:#aaa;">PAUSED</span>`;
        if (pauseBtn) pauseBtn.style.display = "none";
        if (playBtn) playBtn.style.display = "block";
    }

    if (action === "play" && status === "running") {
        window.CM_APP_STATE = firstLedgerSeen ? APP_STATES.DASHBOARD_STREAMING : APP_STATES.INGESTION_STREAMING_FIRST;
        if (statusEl) statusEl.innerHTML = `<span style="color:#ffb84d;">PROCESSING</span>`;
        if (pauseBtn) pauseBtn.style.display = "block";
        if (playBtn) playBtn.style.display = "none";
    }
});

hub.on("ENGINE:SCAN_COMPLETE", ({ success }) => {
    const statusEl = document.getElementById("cm-terminal-status");
    const pauseBtn = document.getElementById("cm-btn-pause");
    const playBtn = document.getElementById("cm-btn-play");
    const toastSlot = document.getElementById("cm-terminal-toast-slot");

    if (pauseBtn) pauseBtn.style.display = "none";
    if (playBtn) playBtn.style.display = "none";

    if (success) {
        window.CM_APP_STATE = APP_STATES.COMPLETE_PENDING_CLOSE;
        if (statusEl) statusEl.innerHTML = `<span style="color:#8ed068;">COMPLETE</span>`;
        if (window.triggerSilentRefresh) window.triggerSilentRefresh();

        const closeIfLedgerExists = () => {
            const hasLedger = Array.isArray(window.MATRIX_PAYLOAD) && window.MATRIX_PAYLOAD.length > 0;
            if (hasLedger) {
                closeTerminalPanel();
            } else {
                window.CM_ZERO_AUTO_INIT_USED = true;
            }
        };

        showAutoCloseToast(
            toastSlot,
            window.MATRIX_TIME_AUTOCLOSE ?? 5,
            () => closeIfLedgerExists(),
            () => {}
        );

        closeTimer = setTimeout(() => closeIfLedgerExists(), (window.MATRIX_TIME_AUTOCLOSE ?? 5) * 1000);
    } else {
        window.CM_APP_STATE = APP_STATES.FAILED;
        if (statusEl) statusEl.innerHTML = `<span style="color:#ff4d4d;">FAILED</span>`;
    }
});

hub.on("ENGINE:EXIT_REQUESTED", () => {
    clearAutoCloseToast(document.getElementById("cm-terminal-toast-slot"));
});

document.addEventListener("DOMContentLoaded", () => {
    const hasLedger = Array.isArray(window.MATRIX_PAYLOAD) && window.MATRIX_PAYLOAD.length > 0;
    firstLedgerSeen = hasLedger;
    window.CM_APP_STATE = hasLedger ? APP_STATES.DASHBOARD_READY : APP_STATES.ZERO;
    setAppState(window.CM_APP_STATE);
});
