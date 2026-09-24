import { formatTerminalChunk } from "../ui/terminalFormatter.js?v=0.1.431";
import { hub } from "../core/eventHub.js?v=0.1.431";
import { contextKey } from "../core/state.js?v=0.1.431";
import { UI_STATE } from "../core/state.js?v=0.1.431";
import { EVENTS } from "../core/state.js?v=0.1.431";
window.CM_ENGINE_CONTROLLABLE = window.CM_ENGINE_CONTROLLABLE || false;
window.CM_SCAN_IN_FLIGHT = window.CM_SCAN_IN_FLIGHT || false;

hub.on("ENGINE:SCAN_REQUESTED", async ({ repo, token, mode } = {}) => {
    console.log("[Trace] ENGINE:SCAN_REQUESTED triggered. Current UI_STATE.dateFilter:", JSON.stringify(window.UI_STATE?.dateFilter));
    if (window.CM_SCAN_IN_FLIGHT) return;
    window.CM_INCOMING_TOTAL = undefined;
    window.CM_INCOMING_REMAINING = undefined;
    window.CM_SCAN_IN_FLIGHT = true;
    if (window.setTableStreamMode) {
        window.setTableStreamMode(true, { asc: true });
    }
    const urlParams = new URLSearchParams(window.location.search);
    const ownerName = urlParams.get("owner") || window.MATRIX_OWNER || "";
    const repoName = repo || urlParams.get("repo") || "";
    const authToken = token || urlParams.get("token") || "";
    const rubricName = urlParams.get("rubric") || window.MATRIX_DEFAULT_RUBRIC || "unknown";

    const myContext = contextKey(repoName, rubricName);
    window.CM_SCAN_CONTEXT = myContext;
    window.CM_SCAN_MODE = mode || "docker";

    const abortCtrl = new AbortController();
    window.CM_SCAN_ABORT = abortCtrl;
    window.CM_ENGINE_CONTROLLABLE = false;

    const baselineIds = new Set(
        (window.MATRIX_PAYLOAD_RAW || window.MATRIX_PAYLOAD || []).map(c => c.h || c.hash)
    );
    UI_STATE.incomingBaselineIds = baselineIds;
    document.body.classList.add('incoming-boot');

    try {
        const endpoint = mode === "native" ? "/api/engine/tail" : "/api/scan";
        const response = await fetch(`${endpoint}?owner=${encodeURIComponent(ownerName)}&repo=${encodeURIComponent(repoName)}&rubric=${encodeURIComponent(rubricName)}&token=${encodeURIComponent(authToken)}`, {
            method: "POST",
            signal: abortCtrl.signal
        });

        if (!response.ok) {
            hub.emit("ENGINE:CHUNK_RECEIVED", {
                chunk: `\n❌ Stream Processing Interrupted: HTTP ${response.status}\n`
            });
            window.CM_SCAN_IN_FLIGHT = false;
            window.CM_SCAN_ABORT = null;
            hub.emit("ENGINE:SCAN_COMPLETE", { success: false });
            document.body.classList.remove('incoming-boot');
            if (window.setTableStreamMode) window.setTableStreamMode(false);
            return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let streamBuffer = "";
        let firstChunkSeen = false;

        while (true) {
            // Immediately drop loop execution on context drift
            if (window.CM_ACTIVE_CONTEXT && window.CM_ACTIVE_CONTEXT !== myContext) {
                reader.cancel();
                break;
            }

            const { value, done } = await reader.read();

            if (done) {
                if (!streamBuffer.includes("[__MATRIX_EOF_SUCCESS__]") && !streamBuffer.includes("[__MATRIX_EOF_FAIL")) {
                    window.CM_SCAN_IN_FLIGHT = false;
                    window.CM_SCAN_ABORT = null;
                    hub.emit("ENGINE:SCAN_COMPLETE", { success: false });
                    document.body.classList.remove('incoming-boot');
                } else {
                    window.CM_SCAN_IN_FLIGHT = false;
                    window.CM_SCAN_ABORT = null;
                }
                break;
            }

                        let chunk = decoder.decode(value, { stream: true });
            
            const progRegex = /\x1B\[1A\r.*?\[.*?\].*?(\d+)% \((\d+)\/(\d+) commits\)\x1B\[K\n?/g;
            let match;
            while ((match = progRegex.exec(chunk)) !== null) {
                if (window.cmUpdateTerminalProgress) window.cmUpdateTerminalProgress(parseInt(match[1]), parseInt(match[3]) - parseInt(match[2]));
            }
            // Strip it so the frontend text box never sees it
            chunk = chunk.replace(/\x1B\[1A\r.*?\[.*?\].*?\d+% \(\d+\/\d+ commits\)\x1B\[K\n?/g, "");

            chunk = formatTerminalChunk(chunk);

            streamBuffer += chunk;

            if (!firstChunkSeen && chunk.trim()) {
                firstChunkSeen = true;
                hub.emit("DATA:FIRST_CHUNK_RECEIVED");
            }

            window.cmSyncEngineUI = function() {
                if (!window.CM_ENGINE_CONTROLLABLE) return;
                const pauseBtn = document.getElementById('cm-btn-pause');
                const playBtn = document.getElementById('cm-btn-play');
                const stat = document.getElementById('cm-terminal-status');
                const isPaused = stat && stat.innerText.includes("PAUSED");
                
                if (window.CM_SCAN_MODE !== 'native') {
                    if (!isPaused) {
                        if (pauseBtn) { pauseBtn.style.display = 'block'; pauseBtn.style.opacity = '1'; pauseBtn.style.pointerEvents = 'auto'; }
                        if (playBtn) playBtn.style.display = 'none';
                    }
                } else {
                    if (pauseBtn) pauseBtn.style.display = 'none';
                    if (playBtn) playBtn.style.display = 'none';
                }
            };

            const isEngineStart = chunk.includes("🐳 ENGINE INITIALIZED") || chunk.includes("🐳 ACTIVE CONTAINER") || chunk.includes("PIPELINE ENGINE INITIALIZED");
            if (!window.CM_ENGINE_CONTROLLABLE && isEngineStart) {
                window.CM_ENGINE_CONTROLLABLE = true;
                window.cmSyncEngineUI();
            }


            // Parse initial queued and remaining incoming commit count
            const cleanText = chunk.replace(/\x1B\[[0-9;]*[a-zA-Z]/g, "");
            const qMatch = cleanText.match(/\((\d+)\s+commits?\s+queued\)/i);
            if (qMatch && window.CM_INCOMING_TOTAL === undefined) {
                window.CM_INCOMING_TOTAL = parseInt(qMatch[1], 10);
                window.CM_INCOMING_REMAINING = window.CM_INCOMING_TOTAL;
                hub.emit("DATA:INCOMING_TOTAL_LOCKED", { total: window.CM_INCOMING_TOTAL });
                if (window.attemptRender && window.UI_STATE && window.UI_STATE.dateFilter?.mode === 'incoming') window.attemptRender();
            }
            const rMatch = cleanText.match(/(\d+)\s+commits?\s+remaining/i);
            if (rMatch) {
                window.CM_INCOMING_REMAINING = parseInt(rMatch[1], 10);
                if (window.attemptRender && window.UI_STATE && window.UI_STATE.dateFilter?.mode === 'incoming') window.attemptRender();
            }

            const isDiskFlushTrigger = chunk.includes("__LEDGER_ROW_FLUSHED__") || chunk.includes("Repository ledger up to date");
            if (isDiskFlushTrigger) {
                if (document.body.classList.contains('incoming-boot')) {
                    document.body.classList.add('incoming-boot-leaving');
                    hub.emit("FILTER:ENTER_INCOMING");
                    setTimeout(() => {
                        document.body.classList.remove('incoming-boot');
                        document.body.classList.remove('incoming-boot-leaving');
                    }, 320);
                }
                if (window.triggerSilentRefresh) {
                    window.triggerSilentRefresh({ repo: repoName, rubric: rubricName, owner: new URLSearchParams(window.location.search).get('owner') || window.MATRIX_OWNER, force: true, gen: window.CM_RENDER_GEN });
                }
            }

            // Strip internal synchronization control signals before rendering to terminal
            chunk = chunk.replace(/\n?\[__LEDGER_ROW_FLUSHED__:\d+\]\n?/g, "");

            if (streamBuffer.includes("[__MATRIX_EOF_SUCCESS__]")) {
                const cleanChunk = chunk.split("[__MATRIX_EOF_SUCCESS__]").join("");
                if (cleanChunk) hub.emit("ENGINE:CHUNK_RECEIVED", { chunk: cleanChunk });
                window.CM_SCAN_IN_FLIGHT = false;
                window.CM_SCAN_ABORT = null;
                hub.emit("ENGINE:SCAN_COMPLETE", { success: true });
                document.body.classList.remove('incoming-boot');
                if (window.setTableStreamMode) window.setTableStreamMode(false);
                break;
            }

            if (streamBuffer.includes("[__MATRIX_EOF_FAIL")) {
                const cleanChunk = chunk.replace(/\[__MATRIX_EOF_.*__\]/g, "");
                if (cleanChunk) hub.emit("ENGINE:CHUNK_RECEIVED", { chunk: cleanChunk });
                window.CM_SCAN_IN_FLIGHT = false;
                window.CM_SCAN_ABORT = null;
                hub.emit("ENGINE:SCAN_COMPLETE", { success: false });
                document.body.classList.remove('incoming-boot');
                break;
            }

            hub.emit("ENGINE:CHUNK_RECEIVED", { chunk });
        }
    } catch (err) {
        if (err.name === 'AbortError') {
            console.log(`Scan aborted gracefully: user navigated away from ${myContext}`);
        } else {
            hub.emit("ENGINE:CHUNK_RECEIVED", {
                chunk: `\n❌ Stream Processing Interrupted: ${err.message}\n`
            });
        }
        window.CM_SCAN_IN_FLIGHT = false;
        window.CM_SCAN_ABORT = null;
        hub.emit("ENGINE:SCAN_COMPLETE", { success: false });
        document.body.classList.remove('incoming-boot');
    }
});

hub.on("ACTION:TOGGLE_ENGINE", async ({ action } = {}) => {
    if (!action) return;
    try {
        const data = await window.cmToggleEngine(action);
        if (data && data.status) {
            hub.emit("ENGINE:CONTROL_UPDATED", { action, status: data.status });
        }
    } catch (err) {
        console.warn("Engine toggle bridge failed.", err);
    }
});

window.cmToggleEngine = async function(action) {
    const pauseBtn = document.getElementById('cm-btn-pause');
    const playBtn = document.getElementById('cm-btn-play');
    const stat = document.getElementById('cm-terminal-status');
    const urlParams = new URLSearchParams(window.location.search);

    if (action === 'pause' && !window.CM_ENGINE_CONTROLLABLE) return null;

    try {
        const resp = await fetch(`/api/engine/control?action=${action}&owner=${urlParams.get('owner') || window.MATRIX_OWNER || ''}&repo=${urlParams.get('repo') || ''}&rubric=${urlParams.get('rubric') || 'unknown'}`, { method: 'POST' });
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

        return data;
    } catch (e) {
        console.warn('Backend control failed.', e);
        return null;
    }
};

hub.on("DATA:LEDGER_UPDATED", () => {
    if (window.cmSyncEngineUI) setTimeout(window.cmSyncEngineUI, 100);
});
