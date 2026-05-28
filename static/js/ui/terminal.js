window.CM_ENGINE_CONTROLLABLE = window.CM_ENGINE_CONTROLLABLE || false;

export async function triggerLedgerRefresh() {
    if (window.toggleDashboardLayout) {
        window.toggleDashboardLayout(true);
    }

    const rightCol =
        document.querySelector('.cm-right-col') ||
        document.getElementById('cm-right-col') ||
        document.querySelector('#cm-dashboard .cm-col:last-child') ||
        document.querySelector('.cm-main-grid > div:last-child') ||
        document.querySelector('main .cm-col:last-child');

    if (!rightCol) {
        console.error('Right column not found.');
        return;
    }

    let termSlot = document.getElementById('cm-native-terminal-slot');
    if (termSlot) {
        termSlot.remove();
    }

    termSlot = document.createElement('div');
    termSlot.id = 'cm-native-terminal-slot';
    rightCol.prepend(termSlot);

    let autoCloseInterval = null;
    let closeInFlight = false;
    window.CM_ENGINE_CONTROLLABLE = false;

    const enterSideMode = () => {
        window.CM_TERMINAL_OPEN = true;
        window.CM_TERMINAL_HOLD_SORT = false;
        window.CM_FORCE_ASC_IN_SIDE_MODE = true;
        termSlot.style.cssText = 'display:flex; flex: 0 0 350px; min-height: 0; flex-direction:column; overflow:hidden;';
        if (window.toggleDashboardLayout) window.toggleDashboardLayout(true);
        if (window.setTableStreamMode) window.setTableStreamMode(true);
    };

    const closeTerminalPanel = () => {
        if (closeInFlight) return;
        closeInFlight = true;

        window.CM_CLOSE_IN_PROGRESS = true;
        window.CM_TERMINAL_OPEN = false;
        window.CM_TERMINAL_HOLD_SORT = false;
        window.CM_FORCE_ASC_IN_SIDE_MODE = false;
        window.CM_ENGINE_CONTROLLABLE = false;

        if (window.cmCloseTimer) {
            clearTimeout(window.cmCloseTimer);
            window.cmCloseTimer = null;
        }
        if (autoCloseInterval) {
            clearInterval(autoCloseInterval);
            autoCloseInterval = null;
        }

        const barContainer = document.getElementById('cm-auto-close-container');
        if (barContainer) barContainer.style.display = 'none';

        if (window.setTableStreamMode) {
            window.setTableStreamMode(false);
        }

        window.location.reload();
    };

    termSlot.innerHTML = `
    <div style="display:flex; flex-direction:column; background:#131314; border:1px solid rgba(255,255,255,0.08); padding:16px; font-family:monospace; border-radius:8px; height:100%; min-height:0; position:relative;">
        <div style="display:flex; justify-content:space-between; border-bottom:1px solid rgba(255,255,255,0.08); padding-bottom:12px; margin-bottom:12px; color:#aaa; font-family:Satoshi, sans-serif; font-size:13px; align-items:center; flex-shrink:0;">
            <span style="display:flex; align-items:center; gap:8px; font-family:Satoshi, sans-serif; font-weight:700; font-size:13px; letter-spacing:0.1px; color:#6fc7d6;">
                <span style="font-size:15px; line-height:1;">🧬</span>
                <span style="color:#6fc7d6; text-shadow:0 0 10px rgba(111,199,214,0.08);">Engine Telemetry</span>
            </span>
            <div style="display:flex; align-items:center; gap:14px;">
                <span id="cm-terminal-status" class="processing-pulse" style="color:#ffb84d; font-weight:bold; display:flex; align-items:center; gap:10px;">PROCESSING</span>
                <svg id="cm-btn-pause" onclick="window.cmToggleEngine('pause')" style="display:block; opacity:0.35; cursor:pointer; width:14px; height:14px; fill:#777; transition:fill 0.2s, opacity 0.2s;" viewBox="0 0 24 24" onmouseover="if(this.style.opacity!=='0.35') this.style.fill='#ffb84d'" onmouseout="this.style.fill='#777'"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>
                <svg id="cm-btn-play" onclick="window.cmToggleEngine('play')" style="cursor:pointer; width:14px; height:14px; fill:#777; transition:fill 0.2s; display:none;" viewBox="0 0 24 24" onmouseover="this.style.fill='#8ed068'" onmouseout="this.style.fill='#777'"><path d="M8 5v14l11-7z"/></svg>
                <svg id="cm-btn-close" style="cursor:pointer; width:16px; height:16px; fill:#777; transition:fill 0.2s;" viewBox="0 0 24 24" onmouseover="this.style.fill='#fff'" onmouseout="this.style.fill='#777'"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>
            </div>
        </div>
        <div id="cm-terminal-body" style="flex:1; min-height:0; overflow-y:auto; background:#070708; color:#a3e685; padding:12px; border-radius:6px; font-size:11px; line-height:1.6; border:1px solid rgba(255,255,255,0.04); white-space:pre-wrap; font-family:monospace;"></div>
        <div id="cm-auto-close-container" style="display:none; position:absolute; left:50%; bottom:18px; transform:translateX(-50%); width:220px; padding:10px 14px 10px; border-radius:14px; background:#1c1c1d; border:1px solid rgba(255,255,255,0.14); box-shadow:0 10px 26px rgba(0,0,0,0.30); flex-direction:column; gap:8px; z-index:30;">
            <div style="display:flex; align-items:flex-start; justify-content:space-between; gap:12px;">
                <span style="color:#9fe870; font-size:11px; line-height:1.05; font-weight:800; letter-spacing:0.35px;">Closing in <span id="cm-ac-secs">5</span>s...</span>
                <button id="cm-cancel-autoclose" style="color:#ff6b6b; font-size:11px; font-weight:900; letter-spacing:0.6px; text-transform:uppercase; cursor:pointer; background:none; border:none; padding:0; line-height:1; white-space:nowrap;">Cancel</button>
            </div>
            <div style="height:7px; background:rgba(255,255,255,0.08); border-radius:999px; overflow:hidden;">
                <div id="cm-auto-close-bar" style="height:100%; width:100%; background:#8ed068; border-radius:999px;"></div>
            </div>
        </div>
    </div>`;

    const termBody = document.getElementById('cm-terminal-body');
    const termStatus = document.getElementById('cm-terminal-status');
    const closeBtn = document.getElementById('cm-btn-close');

    if (closeBtn) closeBtn.onclick = closeTerminalPanel;

    const urlParams = new URLSearchParams(window.location.search);
    const repo = urlParams.get('repo');
    const token = urlParams.get('token');

    enterSideMode();

    const zs = document.getElementById('cm-zero-state');
    if (zs) zs.remove();

    termBody.innerHTML = '🌐 Initializing live buffer stream link to CommitMatrix engine cluster...\n\n';

    const pauseBtn = document.getElementById('cm-btn-pause');
    const playBtn = document.getElementById('cm-btn-play');
    if (pauseBtn) {
        pauseBtn.style.display = 'block';
        pauseBtn.style.opacity = '0.35';
    }
    if (playBtn) playBtn.style.display = 'none';

    try {
        const response = await fetch(`/api/scan?repo=${repo}&token=${token}`, { method: 'POST' });
        if (!response.ok) throw new Error(`HTTP ${response.status} Unauthorized`);

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        let streamBuffer = '';
        let sawExplicitSuccess = false;
        let streamSettled = false;

        const settleTerminal = (label, color, { autoClose = false, refresh = false } = {}) => {
            if (streamSettled) return;
            streamSettled = true;

            termStatus.className = '';
            termStatus.innerHTML = `<span style="color:${color}; font-weight:bold;">${label}</span>`;

            const btnP = document.getElementById('cm-btn-pause');
            const btnL = document.getElementById('cm-btn-play');
            if (btnP) btnP.style.display = 'none';
            if (btnL) btnL.style.display = 'none';

            if (refresh && window.triggerSilentRefresh) {
                window.triggerSilentRefresh();
            }

            if (!autoClose) return;

            window.CM_TERMINAL_HOLD_SORT = true;
            window.CM_FORCE_ASC_IN_SIDE_MODE = true;
            if (window.setTableStreamMode) window.setTableStreamMode(true);

            const autoCloseSeconds = window.MATRIX_TIME_AUTOCLOSE !== undefined ? window.MATRIX_TIME_AUTOCLOSE : 5;
            if (autoCloseSeconds <= 0) return;

            const barContainer = document.getElementById('cm-auto-close-container');
            const bar = document.getElementById('cm-auto-close-bar');
            const acSecs = document.getElementById('cm-ac-secs');

            if (barContainer && bar) {
                barContainer.style.display = 'flex';
                bar.style.transition = `width ${autoCloseSeconds}s linear`;
                bar.style.width = '100%';

                let sLeft = autoCloseSeconds;
                if (acSecs) acSecs.innerText = sLeft;

                autoCloseInterval = setInterval(() => {
                    sLeft -= 1;
                    if (acSecs) acSecs.innerText = sLeft;
                    if (sLeft <= 0) {
                        clearInterval(autoCloseInterval);
                        autoCloseInterval = null;
                    }
                }, 1000);

                document.getElementById('cm-cancel-autoclose').onclick = function() {
                    if (window.cmCloseTimer) {
                        clearTimeout(window.cmCloseTimer);
                        window.cmCloseTimer = null;
                    }
                    if (autoCloseInterval) {
                        clearInterval(autoCloseInterval);
                        autoCloseInterval = null;
                    }
                    barContainer.style.display = 'none';
                    window.CM_TERMINAL_HOLD_SORT = true;
                    window.CM_FORCE_ASC_IN_SIDE_MODE = true;
                    if (window.setTableStreamMode) window.setTableStreamMode(true);
                };

                setTimeout(() => { bar.style.width = '0%'; }, 50);
            }

            window.cmCloseTimer = setTimeout(() => {
                closeTerminalPanel();
            }, autoCloseSeconds * 1000);
        };

        while (true) {
            const { value, done } = await reader.read();

            if (done) {
                if (!sawExplicitSuccess && !streamSettled) {
                    settleTerminal('INTERRUPTED', '#ffb84d', { autoClose: false, refresh: false });
                }
                break;
            }

            let chunk = decoder.decode(value, { stream: true });
            chunk = chunk.replace(/\x1B\[[0-9;]*[a-zA-Z]/g, '');
            streamBuffer += chunk;

            if (!window.CM_ENGINE_CONTROLLABLE && chunk.includes('🚀 Spawning ephemeral analyzer container:')) {
                window.CM_ENGINE_CONTROLLABLE = true;
                if (pauseBtn) pauseBtn.style.opacity = '1';
            }

            if (chunk.includes('Queued for ledger flush') && window.triggerSilentRefresh) {
                window.triggerSilentRefresh();
            }

            if (streamBuffer.includes('[__MATRIX_EOF_SUCCESS__]')) {
                sawExplicitSuccess = true;
                chunk = chunk.replace(/\[__MATRIX_EOF_SUCCESS__\]/g, '');
                termBody.innerHTML += chunk;
                termBody.scrollTop = termBody.scrollHeight;
                settleTerminal('COMPLETE', '#8ed068', { autoClose: true, refresh: true });
                break;
            } else if (streamBuffer.includes('[__MATRIX_EOF_FAIL')) {
                chunk = chunk.replace(/\[__MATRIX_EOF_.*__\]/g, '');
                termBody.innerHTML += chunk;
                termBody.scrollTop = termBody.scrollHeight;
                window.CM_TERMINAL_HOLD_SORT = true;
                window.CM_FORCE_ASC_IN_SIDE_MODE = true;
                if (window.setTableStreamMode) window.setTableStreamMode(true);
                settleTerminal('FAILED', '#ff4d4d', { autoClose: false, refresh: false });
                break;
            }

            termBody.innerHTML += chunk;
            termBody.scrollTop = termBody.scrollHeight;
        }
    } catch (err) {
        termBody.innerHTML += `\n❌ Stream Processing Interrupted: ${err.message}`;
        termStatus.className = '';
        termStatus.innerHTML = `<span style="color:#ff4b4b; font-weight:bold;">FAILED</span>`;
        window.CM_TERMINAL_HOLD_SORT = true;
        window.CM_FORCE_ASC_IN_SIDE_MODE = true;
        if (window.setTableStreamMode) window.setTableStreamMode(true);
    }
}
window.triggerLedgerRefresh = triggerLedgerRefresh;

window.cmToggleEngine = async function(action) {
    const pauseBtn = document.getElementById('cm-btn-pause');
    const playBtn = document.getElementById('cm-btn-play');
    const stat = document.getElementById('cm-terminal-status');
    const urlParams = new URLSearchParams(window.location.search);

    if (action === 'pause' && !window.CM_ENGINE_CONTROLLABLE) {
        stat.innerHTML = '<span style="color:#aaa;">ENGINE STARTING</span>';
        stat.classList.remove('processing-pulse');
        return;
    }

    try {
        const resp = await fetch(`/api/engine/control?action=${action}&token=${urlParams.get('token')}`, { method: 'POST' });
        const data = await resp.json();

        if (action === 'pause' && data.status === 'paused') {
            if (pauseBtn) pauseBtn.style.display = 'none';
            if (playBtn) playBtn.style.display = 'block';
            stat.innerHTML = '<span style="color:#aaa;">PAUSED</span>';
            stat.classList.remove('processing-pulse');
        } else if (action === 'play' && data.status === 'running') {
            if (pauseBtn) {
                pauseBtn.style.display = 'block';
                pauseBtn.style.opacity = '1';
            }
            if (playBtn) playBtn.style.display = 'none';
            stat.innerHTML = '<span style="color:#ffb84d;">PROCESSING</span>';
            stat.classList.add('processing-pulse');
        } else if (data.status === 'starting') {
            stat.innerHTML = '<span style="color:#aaa;">ENGINE STARTING</span>';
            stat.classList.remove('processing-pulse');
        } else if (data.status === 'no_active_engine') {
            stat.innerHTML = '<span style="color:#ff4d4d;">NO ACTIVE ENGINE</span>';
            stat.classList.remove('processing-pulse');
        } else {
            stat.innerHTML = '<span style="color:#ff4d4d;">CONTROL FAILED</span>';
            stat.classList.remove('processing-pulse');
        }
    } catch (e) {
        console.warn('Backend control failed.', e);
        stat.innerHTML = '<span style="color:#ff4d4d;">CONTROL FAILED</span>';
        stat.classList.remove('processing-pulse');
    }
};
