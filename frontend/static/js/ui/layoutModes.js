import { LAYOUTS } from "../core/state.js?v=0.1.436";
import { ensureSideLayoutSlots, getWrap } from "./layoutSlots.js?v=0.1.436";
import { showZeroState, hideZeroState, showDashboard, hideDashboard } from "./layoutVisibility.js?v=0.1.436";
export function applyLayoutMode(layout) {
    const wrap = getWrap();
    if (!wrap) return null;

    if (layout === LAYOUTS.ZERO_LAYOUT) {
        showZeroState();
        hideDashboard();
        document.body.classList.remove("side-mode-active");
        wrap.dataset.layout = "default";
        return null;
    }

    if (layout === LAYOUTS.TERMINAL_SLOT_LAYOUT) {
        hideZeroState();
        hideDashboard();
        document.body.classList.add("side-mode-active");
        return ensureSideLayoutSlots();
    }

    if (layout === LAYOUTS.SIDE_LAYOUT) {
        hideZeroState();
        showDashboard();
        document.body.classList.add("side-mode-active");
        return ensureSideLayoutSlots();
    }

    if (layout === LAYOUTS.DASHBOARD_LAYOUT) {
        hideZeroState();
        showDashboard();
        document.body.classList.remove("side-mode-active");
        wrap.dataset.layout = "default";

        wrap.style.display = "";
        wrap.style.gridTemplateColumns = "";
        wrap.style.alignItems = "";
        wrap.style.height = "";
        wrap.style.overflow = "";

        const leftCol = document.getElementById("cm-left-col");
        const rightCol = document.getElementById("cm-right-col");
        const ledgerCard = document.getElementById("cm-ledger-card");

        if (leftCol || rightCol) {
            const children = [
                ...(leftCol ? Array.from(leftCol.children) : []),
                ...(rightCol ? Array.from(rightCol.children).filter(c => c.id !== "cm-native-terminal-slot") : [])
            ];
            children.forEach(child => wrap.appendChild(child));
            if (leftCol) leftCol.remove();
            if (rightCol) rightCol.remove();
        }

        if (ledgerCard) {
            ledgerCard.style.cssText = "flex:none";
            const tblWrap = ledgerCard.querySelector(".cm-tbl-wrap");
            if (tblWrap) {
                tblWrap.style.flex = "";
                tblWrap.style.height = "";
                tblWrap.style.maxHeight = "560px";
                tblWrap.style.overflowY = "auto";
            }
        }

        return null;
    }

    return null;
}
