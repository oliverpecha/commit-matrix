import { LAYOUTS } from "../core/state.js?v=0.6.67";
import { ensureSideLayoutSlots, getWrap } from "./layoutSlots.js?v=0.6.67";
import { showZeroState, hideZeroState, showDashboard, hideDashboard } from "./layoutVisibility.js?v=0.6.67";

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
        return null;
    }

    return null;
}
