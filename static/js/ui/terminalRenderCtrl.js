import { renderTerminalShell } from "./terminalShell.js";

export function captureShellSnapshot() {
    return {
        bodyHtml: document.getElementById("cm-terminal-body")?.innerHTML || "",
        statusHtml: document.getElementById("cm-terminal-status")?.innerHTML || "",
    };
}

export function restoreShellSnapshot(snapshot) {
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

export function bindShellControls(shell, hub) {
    if (!shell) return;
    shell.closeBtn.onclick = () => hub.emit("ACTION:CLOSE_TERMINAL");
    shell.pauseBtn.onclick = () => hub.emit("ACTION:TOGGLE_ENGINE", { action: "pause" });
    shell.playBtn.onclick = () => hub.emit("ACTION:TOGGLE_ENGINE", { action: "play" });
}

export function renderShell(termSlot, hub) {
    if (!termSlot) return null;
    const snapshot = captureShellSnapshot();
    const shell = renderTerminalShell(termSlot);
    if (!shell) return null;
    restoreShellSnapshot(snapshot);
    bindShellControls(shell, hub);
    return shell;
}

export function appendTerminalChunk(chunk) {
    const body = document.getElementById("cm-terminal-body");
    if (!body) return false;
    body.innerHTML += chunk.replace(/\[__MATRIX_EOF_.*__\]/g, "");
    body.scrollTop = body.scrollHeight;
    return true;
}

export function showPauseButton() {
    const pauseBtn = document.getElementById("cm-btn-pause");
    if (pauseBtn) pauseBtn.style.display = "block";
}

export function setTerminalPaused() {
    const statusEl = document.getElementById("cm-terminal-status");
    const pauseBtn = document.getElementById("cm-btn-pause");
    const playBtn = document.getElementById("cm-btn-play");

    if (statusEl) statusEl.innerHTML = `<span style="color:#aaa;">PAUSED</span>`;
    if (pauseBtn) pauseBtn.style.display = "none";
    if (playBtn) playBtn.style.display = "block";
}

export function setTerminalProcessing() {
    const statusEl = document.getElementById("cm-terminal-status");
    const pauseBtn = document.getElementById("cm-btn-pause");
    const playBtn = document.getElementById("cm-btn-play");

    if (statusEl) statusEl.innerHTML = `<span style="color:#ffb84d;">PROCESSING</span>`;
    if (pauseBtn) pauseBtn.style.display = "block";
    if (playBtn) playBtn.style.display = "none";
}

export function setTerminalComplete() {
    const statusEl = document.getElementById("cm-terminal-status");
    const pauseBtn = document.getElementById("cm-btn-pause");
    const playBtn = document.getElementById("cm-btn-play");

    if (statusEl) statusEl.innerHTML = `<span style="color:#8ed068;">COMPLETE</span>`;
    if (pauseBtn) pauseBtn.style.display = "none";
    if (playBtn) playBtn.style.display = "none";
}

export function setTerminalFailed() {
    const statusEl = document.getElementById("cm-terminal-status");
    const pauseBtn = document.getElementById("cm-btn-pause");
    const playBtn = document.getElementById("cm-btn-play");

    if (statusEl) statusEl.innerHTML = `<span style="color:#ff4d4d;">FAILED</span>`;
    if (pauseBtn) pauseBtn.style.display = "none";
    if (playBtn) playBtn.style.display = "none";
}
