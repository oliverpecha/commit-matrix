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
    <div style="display:flex; flex-direction:column; background:#131314; border:1px solid rgba(255,255,255,0.08); padding:16px; font-family:monospace; border-radius:8px; height:100%; min-height:0;">
        <div style="display:flex; justify-content:space-between; border-bottom:1px solid rgba(255,255,255,0.08); padding-bottom:12px; margin-bottom:12px; color:#aaa; font-family:Satoshi, sans-serif; font-size:13px; align-items:center; flex-shrink:0;">
            <span style="font-weight:bold; color:#4f98a3; display:flex; align-items:center; gap:6px;">🧬 Engine Telemetry</span>
            <div style="display:flex; align-items:center; gap:15px;">
                <span id="cm-terminal-status" class="processing-pulse" style="color:#ffb84d; font-weight:bold;">PROCESSING</span>
                <svg onclick="window.location.reload()" style="cursor:pointer; width:16px; height:16px; fill:#777; transition:fill 0.2s;" viewBox="0 0 24 24" onmouseover="this.style.fill='#fff'" onmouseout="this.style.fill='#777'"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>
            </div>
        </div>
        <div id="cm-terminal-body" style="flex:1; min-height:0; overflow-y:auto; background:#070708; color:#a3e685; padding:12px; border-radius:6px; font-size:11px; line-height:1.6; border:1px solid rgba(255,255,255,0.04); white-space:pre-wrap; font-family:monospace;"></div>
        <div id="cm-auto-close-container" style="position:relative; width:100%; height:4px; background:rgba(255,255,255,0.05); border-radius:4px; overflow:hidden; margin-top:10px; display:none; flex-shrink:0;">
            <div id="cm-auto-close-bar" style="width:100%; height:100%; background:#8ed068;"></div>
        </div>
    </div>`;

    const termBody = document.getElementById('cm-terminal-body');
    const termStatus = document.getElementById('cm-terminal-status');
    let hasStreamErrors = false;

    const urlParams = new URLSearchParams(window.location.search);
    const repo = urlParams.get('repo');
    const token = urlParams.get('token');

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
                termStatus.innerHTML = `<span style="color:${color}; font-weight:bold;">${msg}</span>`;

                if (isRealSuccess && shouldAutoClose) {
                    const barContainer = document.getElementById('cm-auto-close-container');
                    const bar = document.getElementById('cm-auto-close-bar');
                    if (barContainer && bar) {
                        barContainer.style.display = 'block';
                        bar.style.transition = `width ${autoCloseSeconds}s linear`;
                        setTimeout(() => { bar.style.width = '0%'; }, 50);
                        setTimeout(() => { window.location.reload(); }, autoCloseSeconds * 1000);
                    }
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
