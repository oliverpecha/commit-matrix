export function getWrap() {
    return document.getElementById("main-dashboard-wrap");
}

export function ensureSideLayoutSlots() {
    const wrap = getWrap();
    if (!wrap) return null;

    const existingSlot = document.getElementById("cm-native-terminal-slot");
    if (existingSlot) return existingSlot;

    wrap.dataset.layout = "side";
    wrap.style.display = "grid";
    wrap.style.gridTemplateColumns = "minmax(0, 2fr) minmax(0, 1.2fr)";
    wrap.style.alignItems = "stretch";
    wrap.style.gap = "12px";
    wrap.style.height = "calc(100vh - 75px)";
    wrap.style.overflow = "hidden";

    const leftCol = document.createElement("div");
    leftCol.id = "cm-left-col";
    leftCol.style.cssText = "display:flex; flex-direction:column; gap:12px; overflow-y:auto; height:100%; padding-right:8px; padding-bottom:16px;";

    const rightCol = document.createElement("div");
    rightCol.id = "cm-right-col";
    rightCol.className = "cm-right-col";
    rightCol.style.cssText = "display:flex; flex-direction:column; gap:12px; height:100%; overflow:hidden;";

    const termSlot = document.createElement("div");
    termSlot.id = "cm-native-terminal-slot";
    termSlot.style.cssText = "display:flex; flex:0 0 350px; min-height:0; flex-direction:column; overflow:hidden;";
    rightCol.appendChild(termSlot);

    const children = Array.from(wrap.children);
    children.forEach(child => {
        if (child.id === "cm-ledger-card") {
            child.style.cssText = "flex:1; min-height:0; display:flex; flex-direction:column;";
            const tblWrap = child.querySelector(".cm-tbl-wrap");
            if (tblWrap) {
                tblWrap.style.flex = "1";
                tblWrap.style.overflowY = "auto";
            }
            rightCol.appendChild(child);
        } else if (!["cm-zero-state", "cm-left-col", "cm-right-col", "cm-terminal-shell"].includes(child.id)) {
            leftCol.appendChild(child);
        }
    });

    wrap.appendChild(leftCol);
    wrap.appendChild(rightCol);
    return termSlot;
}
