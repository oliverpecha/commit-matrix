export function getEngineControlFlags() {
    const isControllable = !!window.CM_ENGINE_CONTROLLABLE;
    const state = window.CM_APP_STATE || "ZERO";

    const terminalClosedStates = new Set(["ZERO", "DASHBOARD_READY"]);
    const endedStates = new Set(["COMPLETE_PENDING_CLOSE", "FAILED"]);
    const pausedStates = new Set(["PAUSED"]);

    return {
        showPause: isControllable && !terminalClosedStates.has(state) && !endedStates.has(state) && !pausedStates.has(state),
        showPlay: isControllable && pausedStates.has(state),
        showClose: !window.CM_CLOSE_IN_PROGRESS,
    };
}
