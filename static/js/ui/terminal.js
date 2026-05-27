export async function triggerLedgerRefresh() {
    if (window.toggleDashboardLayout) {
        window.toggleDashboardLayout(true);
    }

    const rightCol = document.getElementById('cm-right-col');
    if (!rightCol) return console.error('Right column not found.');

    let termSlot = document.getElementById('cm-native-terminal-slot');
    if (!termSlot) {
        termSlot = document.createElement('div');
        termSlot.id = 'cm-native-terminal-slot';
        rightCol.prepend(termSlot); // Force it to the top if created late
    }
    // Reveal the terminal slot and strictly enforce the 350px height
    termSlot.style.cssText = 'display:flex; flex: 0 0 350px; min-height: 0; flex-direction:column; overflow:hidden;';

    // Notice the restored X button and min-height traps
    termSlot.innerHTML = `
    <div style="display:flex; flex-direction:column; background:#131314; border:1px solid rgba(255,255,255,0.08); padding:16px; font-family:monospace; border-radius:8px; height:100%; min-height:0; position:relative;">
        <div style="display:flex; justify-content:space-between; border-bottom:1px solid rgba(255,255,255,0.08); padding-bottom:12px; margin-bottom:12px; color:#aaa; font-family:Satoshi, sans-serif; font-size:13px; align-items:center; flex-shrink:0;">
            <span style="font-weight:bold; color:#4f98a3; display:flex; align-items:center; gap:6px;">🧬 Engine Telemetry</span>
            <div style="display:flex; align-items:center; gap:15px;">
                <span id="cm-terminal-status" class="processing-pulse" style="color:#ffb84d; font-weight:bold; display:flex; align-items:center; gap:10px;">PROCESSING</span>
                <svg id="cm-btn-pause" onclick="window.cmToggleEngine('pause')" style="cursor:pointer; width:14px; height:14px; fill:#777; transition:fill 0.2s;" viewBox="0 0 24 24" onmouseover="this.style.fill='#ffb84d'" onmouseout="this.style.fill='#777'"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>
                <svg id="cm-btn-play" onclick="window.cmToggleEngine('play')" style="cursor:pointer; width:14px; height:14px; fill:#777; transition:fill 0.2s; display:none;" viewBox="0 0 24 24" onmouseover="this.style.fill='#8ed068'" onmouseout="this.style.fill='#777'"><path d="M8 5v14l11-7z"/></svg>
                <svg onclick="window.location.reload()" style="cursor:pointer; width:16px; height:16px; fill:#777; transition:fill 0.2s;" viewBox="0 0 24 24" onmouseover="this.style.fill='#fff'" onmouseout="this.style.fill='#777'"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>
            </div>
        </div>
        <div id="cm-terminal-body" style="flex:1; min-height:0; overflow-y:auto; background:#070708; color:#a3e685; padding:12px; border-radius:6px; font-size:11px; line-height:1.6; border:1px solid rgba(255,255,255,0.04); white-space:pre-wrap; font-family:monospace;"></div>
        <div id="cm-auto-close-container" style="position:absolute; bottom:24px; left:50%; transform:translateX(-50%); display:none; flex-direction:column; align-items:center; background:#1e1e20; border:1px solid #444; border-radius:8px; padding:8px 16px; gap:6px; box-shadow:0 8px 24px rgba(0,0,0,0.8); z-index:9999;">
            <div style="display:flex; justify-content:space-between; align-items:center; width:100%; gap:16px;">
                <span id="cm-ac-text" style="color:#8ed068; font-size:11px; font-weight:bold;">Closing in <span id="cm-ac-secs"></span>s...</span>
                <button id="cm-cancel-autoclose" style="background:transparent; border:none; color:#ff4d4d; font-size:10px; font-weight:bold; cursor:pointer;">CANCEL</button>
            </div>
            <div style="width:120px; height:4px; background:rgba(255,255,255,0.1); border-radius:4px; overflow:hidden;">
                <div id="cm-auto-close-bar" style="width:100%; height:100%; background:#8ed068;"></div>
            </div>
        </div>
    </div>`;

    const termBody = document.getElementById('cm-terminal-body');
    const termStatus = document.getElementById('cm-terminal-status');
    let hasStreamErrors = false;

    const urlParams = new URLSearchParams(window.location.search);
    const repo = urlParams.get('repo');
    const token = urlParams.get('token');

    if(window.setTableStreamMode) window.setTableStreamMode(true);
    termBody.innerHTML = '🌐 Initializing live buffer stream link to CommitMatrix engine cluster...\n\n';

    try {
        const response = await fetch(`/api/scan?repo=${repo}&token=${token}`, { method: 'POST' });
        if (!response.ok) throw new Error(`HTTP ${response.status} Unauthorized`);

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            let chunk = decoder.decode(value, { stream: true });
            chunk = chunk.replace(/\x1B\[[0-9;]*[a-zA-Z]/g, '');
            termBody.innerHTML += chunk;
            termBody.scrollTop = termBody.scrollHeight;

            if (chunk.includes('❌ Error') || chunk.includes('ERROR:')) hasStreamErrors = true;

            if (chunk.includes('PROCESS_COMPLETE') || chunk.includes('Matrix is fully up to date') || chunk.includes('Aborting.') || chunk.includes('❌ FATAL ERROR') || chunk.includes('Traceback') || chunk.includes('SyntaxError')) {

                const isRealSuccess = (chunk.includes('PROCESS_COMPLETE') || chunk.includes('Matrix is fully up to date')) && !hasStreamErrors;
                const color = isRealSuccess ? '#8ed068' : '#ff4d4d';
                const msg = isRealSuccess ? 'COMPLETE' : (hasStreamErrors ? 'COMPLETED WITH ERRORS' : 'ABORTED');

                const autoCloseSeconds = window.MATRIX_TIME_AUTOCLOSE !== undefined ? window.MATRIX_TIME_AUTOCLOSE : 5;
                const shouldAutoClose = autoCloseSeconds > 0;

                termStatus.className = '';
                
                if (isRealSuccess && shouldAutoClose) {
                    termStatus.innerHTML = `<span style="color:${color};">${msg}</span>`;
                    const btnP = document.getElementById('cm-btn-pause');
                    const btnL = document.getElementById('cm-btn-play');
                    if(btnP) btnP.style.display = 'none';
                    if(btnL) btnL.style.display = 'none';
                    if(window.setTableStreamMode) window.setTableStreamMode(false); // Revert table sort

                    // Re-enable the reload timer (it was disabled, causing the infinite loop bug)
                    // The reload is SAFE now because the parser correctly skips already-scanned commits
                    window.cmReloadTimer = setTimeout(() => { window.location.reload(); }, autoCloseSeconds * 1000);
                    
                    const barContainer = document.getElementById('cm-auto-close-container');
                    const bar = document.getElementById('cm-auto-close-bar');
                    const acSecs = document.getElementById('cm-ac-secs');
                    
                    if (barContainer && bar) {
                        barContainer.style.display = 'flex';
                        bar.style.transition = `width ${autoCloseSeconds}s linear`;
                        
                        let sLeft = autoCloseSeconds;
                        if(acSecs) acSecs.innerText = sLeft;
                        const sInt = setInterval(()=>{
                            sLeft -= 1;
                            if (acSecs) acSecs.innerText = sLeft;
                            if(sLeft <= 0) clearInterval(sInt);
                        }, 1000);


                        document.getElementById('cm-cancel-autoclose').onclick = function() {
                            clearTimeout(window.cmReloadTimer);
                            clearInterval(sInt);
                            barContainer.style.display = 'none';
                            termStatus.innerHTML = `<span style="color:${color};">COMPLETE</span>`;
                        };
                    }
                } else {
                    termStatus.innerHTML = `<span style="color:${color}; font-weight:bold;">${msg}</span>`;
                if(window.setTableStreamMode) window.setTableStreamMode(false); // Revert table sort
                }
                return;
            }
        }
    } catch (err) {
        termBody.innerHTML += `\n❌ Stream Processing Interrupted: ${err.message}`;
        termStatus.className = '';
        termStatus.innerHTML = `<span style="color:#ff4b4b; font-weight:bold;">FAILED</span>`;
    }
}
window.triggerLedgerRefresh = triggerLedgerRefresh;

// --- ENGINE CONTROL STUB (Waiting on Agent 1) ---
window.cmToggleEngine = async function(action) {
    const urlParams = new URLSearchParams(window.location.search);
    fetch(`/api/engine/control?action=${action}&token=${urlParams.get('token')}`, {method:'POST'}).catch(e => console.warn('Backend control endpoint pending Agent 1.'));
    
    document.getElementById('cm-btn-pause').style.display = action === 'pause' ? 'none' : 'block';
    document.getElementById('cm-btn-play').style.display = action === 'pause' ? 'block' : 'none';
    
    const stat = document.getElementById('cm-terminal-status');
    if (action === 'pause') {
        stat.innerHTML = '<span style="color:#aaa;">PAUSED</span>';
        stat.classList.remove('processing-pulse');
    } else {
        stat.innerHTML = '<span style="color:#ffb84d;">PROCESSING</span>';
        stat.classList.add('processing-pulse');
    }
};
