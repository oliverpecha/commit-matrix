document.addEventListener("DOMContentLoaded", function() {
    const serverHasData = Array.isArray(window.MATRIX_PAYLOAD) && window.MATRIX_PAYLOAD.length > 0;
    if (serverHasData) return;

    const wrap = document.getElementById("main-dashboard-wrap");
    if (!wrap) return;

    const elementsToHide = wrap.querySelectorAll(".cm-row, .cm-kpi-row, #cm-ledger-card");
    elementsToHide.forEach(el => el.style.display = "none");

    const zs = document.createElement("div");
    zs.id = "cm-zero-state";
    zs.style.cssText = "position:fixed; left:50%; top:45%; transform:translate(-50%, -50%); display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; font-family:Satoshi, sans-serif; z-index:50; width:100%; pointer-events:none;";

    zs.innerHTML = `
        <div style="font-size:52px; margin-bottom:20px; opacity:0.8;">🌌</div>
        <h2 style="color:#e0e0e0; margin-bottom:12px; font-weight:600; letter-spacing:0.5px;">Ledger Empty</h2>
        <p style="color:#888; max-width:420px; margin-bottom:30px; line-height:1.6; font-size:15px;">Awaiting Telemetry.</p>
        <button id="cm-init-btn" class="cm-fbtn" style="pointer-events:auto; position:relative; overflow:hidden; background:rgba(79,152,163,0.05); border:1px solid rgba(79,152,163,0.4); padding:12px 28px; font-size:15px; font-weight:bold; cursor:pointer; color:#4f98a3; border-radius:6px; box-shadow: 0 4px 12px rgba(0,0,0,0.2);">
            <div id="cm-btn-progress" style="position:absolute; top:0; left:0; height:100%; width:100%; background:rgba(79,152,163,0.25); transition: width 5s linear; transform-origin: left;"></div>
            <span style="position:relative; z-index:1;" id="cm-btn-text">🚀 Initialize the engine</span>
        </button>
    `;

    wrap.insertBefore(zs, wrap.firstChild);

    setTimeout(() => {
        const pBar = document.getElementById("cm-btn-progress");
        if (pBar) pBar.style.width = "0%";
    }, 50);

    const triggerInit = () => {
        const t = document.getElementById("cm-btn-text");
        window.CM_ZERO_AUTO_INIT_USED = window.CM_ZERO_AUTO_INIT_USED || false;
        if (window.CM_ZERO_AUTO_INIT_USED) return;
        window.CM_ZERO_AUTO_INIT_USED = true;
        if (t) t.textContent = "🚀 Initializing...";
        if (window.hub) window.hub.emit("ACTION:REFRESH_LEDGER");
    };

    const btn = document.getElementById("cm-init-btn");
    if (btn) {
        btn.addEventListener("click", triggerInit);
    }

    let timeLeft = 5;
    const interval = setInterval(() => {
        timeLeft -= 1;
        if (timeLeft <= 0) {
            clearInterval(interval);
            triggerInit();
        }
    }, 1000);
});
