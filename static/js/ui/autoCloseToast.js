let autoCloseInterval = null;

export function showAutoCloseToast(slot, seconds, onClose, onCancel) {
    if (!slot || seconds <= 0) return;

    slot.innerHTML = `
    <div id="cm-auto-close-container" style="width:220px; padding:10px 14px 10px; border-radius:14px; background:#1c1c1d; border:1px solid rgba(255,255,255,0.14); box-shadow:0 10px 26px rgba(0,0,0,0.30); display:flex; flex-direction:column; gap:8px;">
        <div style="display:flex; align-items:flex-start; justify-content:space-between; gap:12px;">
            <span style="color:#9fe870; font-size:11px; font-weight:800;">Closing in <span id="cm-ac-secs">${seconds}</span>s...</span>
            <button id="cm-cancel-autoclose" style="color:#ff6b6b; font-size:11px; font-weight:900; text-transform:uppercase; cursor:pointer; background:none; border:none; padding:0;">Cancel</button>
        </div>
        <div style="height:7px; background:rgba(255,255,255,0.08); border-radius:999px; overflow:hidden;">
            <div id="cm-auto-close-bar" style="height:100%; width:100%; background:#8ed068; border-radius:999px;"></div>
        </div>
    </div>`;

    const bar = document.getElementById("cm-auto-close-bar");
    const secs = document.getElementById("cm-ac-secs");
    const cancel = document.getElementById("cm-cancel-autoclose");

    if (bar) {
        bar.style.transition = `width ${seconds}s linear`;
        setTimeout(() => { bar.style.width = "0%"; }, 50);
    }

    let remaining = seconds;
    autoCloseInterval = setInterval(() => {
        remaining -= 1;
        if (secs) secs.innerText = remaining;
        if (remaining <= 0) {
            clearInterval(autoCloseInterval);
            onClose();
        }
    }, 1000);

    if (cancel) {
        cancel.onclick = () => {
            clearInterval(autoCloseInterval);
            slot.innerHTML = "";
            if (onCancel) onCancel();
        };
    }
}

export function clearAutoCloseToast(slot) {
    if (autoCloseInterval) clearInterval(autoCloseInterval);
    if (slot) slot.innerHTML = "";
}
