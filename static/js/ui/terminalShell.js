export function renderTerminalShell(termSlot) {
    if (!termSlot) return null;

    termSlot.innerHTML = `
    <div style="display:flex; flex-direction:column; background:#131314; border:1px solid rgba(255,255,255,0.08); padding:16px; font-family:monospace; border-radius:8px; height:100%; min-height:0; position:relative;">
        <div style="display:flex; justify-content:space-between; border-bottom:1px solid rgba(255,255,255,0.08); padding-bottom:12px; margin-bottom:12px; color:#aaa; font-family:Satoshi, sans-serif; font-size:13px; align-items:center; flex-shrink:0;">
            <span style="display:flex; align-items:center; gap:8px; font-weight:700; color:#6fc7d6;">
                <span style="font-size:15px;">🧬</span><span>Engine Telemetry</span>
            </span>
            <div style="display:flex; align-items:center; gap:14px;">
                <span id="cm-terminal-status" class="processing-pulse" style="color:#ffb84d; font-weight:bold; display:flex; align-items:center; gap:10px;">PROCESSING</span>
                <svg id="cm-btn-pause" style="display:none; cursor:pointer; width:14px; height:14px; fill:#777; transition:fill 0.2s, opacity 0.2s;" viewBox="0 0 24 24" onmouseover="this.style.fill='#ffb84d'" onmouseout="this.style.fill='#777'"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>
                <svg id="cm-btn-play" style="display:none; cursor:pointer; width:14px; height:14px; fill:#777; transition:fill 0.2s;" viewBox="0 0 24 24" onmouseover="this.style.fill='#8ed068'" onmouseout="this.style.fill='#777'"><path d="M8 5v14l11-7z"/></svg>
                <svg id="cm-btn-close" style="cursor:pointer; width:16px; height:16px; fill:#777; transition:fill 0.2s;" viewBox="0 0 24 24" onmouseover="this.style.fill='#fff'" onmouseout="this.style.fill='#777'"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>
            </div>
        </div>
        <div id="cm-terminal-body" style="flex:1; min-height:0; overflow-y:auto; background:#070708; color:#a3e685; padding:12px; border-radius:6px; font-size:11px; line-height:1.6; border:1px solid rgba(255,255,255,0.04); white-space:pre-wrap; font-family:monospace;">🌐 Initializing live buffer stream link...\n\n</div>
        <div id="cm-terminal-toast-slot" style="position:absolute; left:50%; bottom:18px; transform:translateX(-50%); z-index:9999;"></div>
    </div>`;
    return {
        status: document.getElementById("cm-terminal-status"),
        body: document.getElementById("cm-terminal-body"),
        pauseBtn: document.getElementById("cm-btn-pause"),
        playBtn: document.getElementById("cm-btn-play"),
        closeBtn: document.getElementById("cm-btn-close"),
        toastSlot: document.getElementById("cm-terminal-toast-slot"),
    };
}
