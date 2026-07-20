export function renderCliOverlay(termSlot, hub) {
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

    const closeBtn = document.getElementById("cm-btn-close-cli");
    if (closeBtn) closeBtn.onclick = () => hub.emit("ACTION:CLOSE_TERMINAL");
}
