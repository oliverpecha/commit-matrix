import { hub } from "../core/eventHub.js";
import { APP_STATES } from "../core/state.js";
import {
    getAppState,
    setAppState,
    syncInitialAppState,
    beginScanState,
    onFirstChunkState,
    onLedgerAvailableState,
    onPauseState,
    onPlayState,
    onCompleteState,
    onFailureState,
} from "../core/appStateCtrl.js";
import { renderTerminalShell } from "./terminalShell.js";
import { scheduleAutoClose, resetCloseLifecycle } from "./terminalLifecycle.js";
import { getEngineControlFlags } from "../engine/engineControlPolicy.js";

function bindShellControls(shell) {
    if (!shell) return;
    shell.closeBtn.onclick = () => hub.emit("ACTION:CLOSE_TERMINAL");
    shell.pauseBtn.onclick = () => hub.emit("ACTION:TOGGLE_ENGINE", { action: "pause" });
    shell.playBtn.onclick = () => hub.emit("ACTION:TOGGLE_ENGINE", { action: "play" });
}

function syncShellControls() {
    const flags = getEngineControlFlags();
    const pauseBtn = document.getElementById("cm-btn-pause");
    const playBtn = document.getElementById("cm-btn-play");
    const closeBtn = document.getElementById("cm-btn-close");

    if (pauseBtn) pauseBtn.style.display = flags.showPause ? "block" : "none";
    if (playBtn) playBtn.style.display = flags.showPlay ? "block" : "none";
    if (closeBtn) closeBtn.style.display = flags.showClose ? "block" : "none";
}

function captureShellSnapshot() {
    return {
        bodyHtml: document.getElementById("cm-terminal-body")?.innerHTML || "",
        statusHtml: document.getElementById("cm-terminal-status")?.innerHTML || "",
    };
}

function restoreShellSnapshot(snapshot) {
    if (!snapshot) return;

    const body = document.getElementById("cm-terminal-body");
    const status = document.getElementById("cm-terminal-status");

    if (body && snapshot.bodyHtml) {
        body.innerHTML = snapshot.bodyHtml;
        body.scrollTop = body.scrollHeight;
    }

    if (status && snapshot.statusHtml) {
        status.innerHTML = snapshot.statusHtml;
    }
}

function renderShellForCurrentState() {
    const snapshot = captureShellSnapshot();
    const termSlot = setAppState(getAppState());
    if (!termSlot) return null;
    const shell = renderTerminalShell(termSlot);
    restoreShellSnapshot(snapshot);
    bindShellControls(shell);
    syncShellControls();
    return shell;
}

function appendChunk(chunk) {
    const body = document.getElementById("cm-terminal-body");
    if (!body) return;
    body.innerHTML += chunk.replace(/\[__MATRIX_EOF_.*__\]/g, "");
    body.scrollTop = body.scrollHeight;
}

hub.on("UI:SHOW_CLI_INSTRUCTIONS", () => {
    setAppState(Array.isArray(window.MATRIX_PAYLOAD) && window.MATRIX_PAYLOAD.length > 0 ? APP_STATES.DASHBOARD_STREAMING : APP_STATES.INGESTION_BOOT);
    const termSlot = setAppState(getAppState());
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
    resetCloseLifecycle();
    beginScanState();
    renderShellForCurrentState();
});

hub.on("DATA:FIRST_CHUNK_RECEIVED", () => {
    onFirstChunkState();
    renderShellForCurrentState();
});

hub.on("DATA:LEDGER_CONFIRMED", () => {
    onLedgerAvailableState();
    syncShellControls();
});

hub.on("ENGINE:CHUNK_RECEIVED", ({ chunk }) => {
    appendChunk(chunk);

    if (chunk.includes("🐳 ENGINE INITIALIZED CONTAINER")) {
        window.CM_ENGINE_CONTROLLABLE = true;
        syncShellControls();
    }

    if (chunk.includes("Queued for ledger flush")) {
        onLedgerAvailableState();
        renderShellForCurrentState();
    }
});

hub.on("ENGINE:CONTROL_UPDATED", ({ action, status }) => {
    const statusEl = document.getElementById("cm-terminal-status");

    if (action === "pause" && status === "paused") {
        onPauseState();
        if (statusEl) statusEl.innerHTML = `<span style="color:#aaa;">PAUSED</span>`;
    }

    if (action === "play" && status === "running") {
        onPlayState();
        if (statusEl) statusEl.innerHTML = `<span style="color:#ffb84d;">PROCESSING</span>`;
    }

    syncShellControls();
});

hub.on("ENGINE:SCAN_COMPLETE", ({ success }) => {
    const statusEl = document.getElementById("cm-terminal-status");

    if (success) {
        onCompleteState();
        if (statusEl) statusEl.innerHTML = `<span style="color:#8ed068;">COMPLETE</span>`;
        if (window.triggerSilentRefresh) window.triggerSilentRefresh();
        syncShellControls();
        scheduleAutoClose(window.MATRIX_TIME_AUTOCLOSE ?? 5);
    } else {
        onFailureState();
        if (statusEl) statusEl.innerHTML = `<span style="color:#ff4d4d;">FAILED</span>`;
        syncShellControls();
    }
});

document.addEventListener("DOMContentLoaded", () => {
    syncInitialAppState();
});
