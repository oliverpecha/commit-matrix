import { formatTerminalChunk } from "../ui/terminalFormatter.js";
import { hub } from "../core/eventHub.js";

window.CM_ENGINE_CONTROLLABLE = window.CM_ENGINE_CONTROLLABLE || false;

hub.on("ENGINE:SCAN_REQUESTED", async ({ repo, token } = {}) => {
    const urlParams = new URLSearchParams(window.location.search);
    const repoName = repo || urlParams.get("repo") || "commit-matrix";
    const authToken = token || urlParams.get("token") || "";

    window.CM_ENGINE_CONTROLLABLE = false;

    try {
        const response = await fetch(`/api/scan?repo=${encodeURIComponent(repoName)}&token=${encodeURIComponent(authToken)}`, {
            method: "POST"
        });

        if (!response.ok) {
            hub.emit("ENGINE:CHUNK_RECEIVED", {
                chunk: `\n❌ Stream Processing Interrupted: HTTP ${response.status}\n`
            });
            hub.emit("ENGINE:SCAN_COMPLETE", { success: false });
            return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let streamBuffer = "";
        let firstChunkSeen = false;

        while (true) {
            const { value, done } = await reader.read();

            if (done) {
                if (!streamBuffer.includes("[__MATRIX_EOF_SUCCESS__]") && !streamBuffer.includes("[__MATRIX_EOF_FAIL")) {
                    hub.emit("ENGINE:SCAN_COMPLETE", { success: false });
                }
                break;
            }

            let chunk = decoder.decode(value, { stream: true });
            chunk = formatTerminalChunk(chunk);

            streamBuffer += chunk;

            if (!firstChunkSeen && chunk.trim()) {
                firstChunkSeen = true;
                hub.emit("DATA:FIRST_CHUNK_RECEIVED");
            }

            if (!window.CM_ENGINE_CONTROLLABLE && chunk.includes("🐳 ENGINE INITIALIZED CONTAINER")) {
                window.CM_ENGINE_CONTROLLABLE = true;
            }

            if (chunk.includes("Queued for ledger flush") && window.triggerSilentRefresh) {
                window.triggerSilentRefresh();
            }

            if (streamBuffer.includes("[__MATRIX_EOF_SUCCESS__]")) {
                const cleanChunk = chunk.split("[__MATRIX_EOF_SUCCESS__]").join("");
                if (cleanChunk) hub.emit("ENGINE:CHUNK_RECEIVED", { chunk: cleanChunk });
                hub.emit("ENGINE:SCAN_COMPLETE", { success: true });
                break;
            }

            if (streamBuffer.includes("[__MATRIX_EOF_FAIL")) {
                const cleanChunk = chunk.replace(/\[__MATRIX_EOF_.*__\]/g, "");
                if (cleanChunk) hub.emit("ENGINE:CHUNK_RECEIVED", { chunk: cleanChunk });
                hub.emit("ENGINE:SCAN_COMPLETE", { success: false });
                break;
            }

            hub.emit("ENGINE:CHUNK_RECEIVED", { chunk });
        }
    } catch (err) {
        hub.emit("ENGINE:CHUNK_RECEIVED", {
            chunk: `\n❌ Stream Processing Interrupted: ${err.message}\n`
        });
        hub.emit("ENGINE:SCAN_COMPLETE", { success: false });
    }
});

window.cmToggleEngine = async function(action) {
    const pauseBtn = document.getElementById('cm-btn-pause');
    const playBtn = document.getElementById('cm-btn-play');
    const stat = document.getElementById('cm-terminal-status');
    const urlParams = new URLSearchParams(window.location.search);

    if (action === 'pause' && !window.CM_ENGINE_CONTROLLABLE) return;

    try {
        const resp = await fetch(`/api/engine/control?action=${action}&repo=${urlParams.get('repo') || 'commit-matrix'}`, { method: 'POST' });
        const data = await resp.json();

        if (action === 'pause' && data.status === 'paused') {
            if (pauseBtn) pauseBtn.style.display = 'none';
            if (playBtn) playBtn.style.display = 'block';
            if (stat) {
                stat.innerHTML = '<span style="color:#aaa;">PAUSED</span>';
                stat.classList.remove('processing-pulse');
            }
        } else if (action === 'play' && data.status === 'running') {
            if (pauseBtn) {
                pauseBtn.style.display = 'block';
                pauseBtn.style.opacity = '1';
            }
            if (playBtn) playBtn.style.display = 'none';
            if (stat) {
                stat.innerHTML = '<span style="color:#ffb84d;">PROCESSING</span>';
                stat.classList.add('processing-pulse');
            }
        }
    } catch (e) {
        console.warn('Backend control failed.', e);
    }
};
