export async function triggerLedgerRefresh() {
    const urlParams = new URLSearchParams(window.location.search);
    const repo = urlParams.get('repo');
    const token = urlParams.get('token');
    
    const oldModal = document.getElementById('cm-terminal-modal');
    if (oldModal) oldModal.remove();
    
    document.body.insertAdjacentHTML('beforeend', `
    <div id="cm-terminal-modal" style="display:flex; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.85); z-index:100000; align-items:center; justify-content:center; backdrop-filter: blur(4px);">
        <div style="background:#131314; border:1px solid rgba(255,255,255,0.08); width:85%; max-width:800px; border-radius:8px; padding:20px; font-family:monospace; box-shadow:0 20px 40px rgba(0,0,0,0.6);">
            <div style="display:flex; justify-content:space-between; border-bottom:1px solid rgba(255,255,255,0.08); padding-bottom:12px; margin-bottom:15px; color:#aaa; font-family:Satoshi, sans-serif; font-size:13px; align-items:center;">
                <span style="font-weight:bold; color:#4f98a3; display:flex; align-items:center; gap:6px;">🧬 CommitMatrix Live Engine Telemetry Terminal</span>
                <div style="display:flex; align-items:center; gap:15px;">
                    <span id="cm-terminal-status" style="color:#ffb84d; font-weight:bold;">PROCESSING</span>
                    <span onclick="document.getElementById('cm-terminal-modal').remove()" style="cursor:pointer; color:#777; font-weight:bold;">[ X ]</span>
                </div>
            </div>
            <div id="cm-terminal-body" style="height:350px; overflow-y:auto; background:#070708; color:#a3e685; padding:15px; border-radius:6px; font-size:12px; line-height:1.6; border:1px solid rgba(255,255,255,0.04); white-space:pre-wrap; font-family:monospace;"></div>
        </div>
    </div>`);
    
    const termBody = document.getElementById('cm-terminal-body');
    const termStatus = document.getElementById('cm-terminal-status');
    
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
            
            // Replaces the auto-reload with a manual user-controlled button
            if (chunk.includes('PROCESS_COMPLETE')) {
                termStatus.innerHTML = '<button onclick="window.location.reload()" style="background:#8ed068; color:#000; border:none; padding:4px 12px; border-radius:4px; cursor:pointer; font-weight:bold; font-size:11px;">RELOAD DASHBOARD</button>';
                return;
            }
            if (chunk.includes('ERROR:')) {
                termStatus.textContent = 'FAILED';
                termStatus.style.color = '#ff4b4b';
                return;
            }
        }
    } catch (err) {
        termBody.innerHTML += `\n❌ Stream Processing Interrupted: ${err.message}`;
        termStatus.textContent = 'ERROR';
        termStatus.style.color = '#ff4b4b';
    }
}

window.triggerLedgerRefresh = triggerLedgerRefresh;
