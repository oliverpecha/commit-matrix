export function toggleDashboardLayout(forceSide = false) {
    const wrap = document.getElementById("main-dashboard-wrap");
    if (!wrap) return;

    const isCurrentlySide = wrap.dataset.layout === "side";

    if (isCurrentlySide && !forceSide) {
        // Gracefully un-wrap the DOM layout instead of reloading the page
        wrap.dataset.layout = "";
        wrap.style.display = "";
        wrap.style.gridTemplateColumns = "";
        wrap.style.alignItems = "";
        wrap.style.gap = "";
        wrap.style.height = "";
        wrap.style.overflow = "";

        const leftCol = document.getElementById("cm-left-col");
        const rightCol = document.getElementById("cm-right-col");

        if (leftCol && rightCol) {
            const allChildren = [...Array.from(leftCol.children), ...Array.from(rightCol.children)];
            allChildren.forEach(child => {
                if (child.id === "cm-native-terminal-slot") {
                    child.remove(); // Remove the injected terminal slot
                } else {
                    if (child.id === "cm-ledger-card") {
                        child.style.flex = "";
                        child.style.minHeight = "";
                        child.style.height = "";
                        child.style.display = "";
                        child.style.flexDirection = "";
                        const tblWrap = child.querySelector(".cm-tbl-wrap");
                        if (tblWrap) {
                            tblWrap.style.flex = "";
                            tblWrap.style.height = "";
                            tblWrap.style.maxHeight = "";
                            tblWrap.style.overflowY = "";
                        }
                    }
                    wrap.appendChild(child); // Push components back to the main container
                }
            });
            leftCol.remove();
            rightCol.remove();
        }
        return;
    }

    if (!isCurrentlySide) {
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
        rightCol.style.cssText = "display:flex; flex-direction:column; gap:12px; height:100%; overflow:hidden;";

        const termSlot = document.createElement("div");
        termSlot.id = "cm-native-terminal-slot";
        termSlot.style.cssText = "display:none; flex: 0 0 350px; min-height: 0; flex-direction:column; overflow:hidden;";
        rightCol.appendChild(termSlot);

        const children = Array.from(wrap.children);
        children.forEach(child => {
            if (child.id === "cm-ledger-card") {
                const isHidden = child.style.display === "none";
                child.style.cssText = "flex: 0 0 auto; min-height: 0; height: fit-content; display:flex; flex-direction:column;";
                if (isHidden) child.style.display = "none";
                const tblWrap = child.querySelector(".cm-tbl-wrap");
                if (tblWrap) {
                    tblWrap.style.maxHeight = "560px";
                    tblWrap.style.overflowY = "auto";
                }
                rightCol.appendChild(child);
            } else {
                leftCol.appendChild(child);
            }
        });

        wrap.appendChild(leftCol);
        wrap.appendChild(rightCol);
    }
}

window.cmRevertDashboardLayout = () => toggleDashboardLayout(false);
