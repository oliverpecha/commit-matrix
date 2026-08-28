console.log('📦 Module Boot: repoManager.js loaded and active.');
import { hub } from "../core/eventHub.js?v=0.6.9";

hub.on("ACTION:REFRESH_LEDGER", () => {
    // If we are currently in invalid repo state, do not trigger a backend scan
    if (window.MATRIX_INVALID_REPO || window.MATRIX_SYSTEM_EMPTY) {
        console.warn("[repoManager] Refresh ignored: current repository is invalid or not found.");
        return;
    }
    const urlParams = new URLSearchParams(window.location.search);
    const repo = urlParams.get("repo") || "";
    const token = urlParams.get("token") || "";
    hub.emit("ENGINE:SCAN_REQUESTED", { repo, token });
});

hub.on("ACTION:ADD_REPO_REQUESTED", () => {
    hub.emit("UI:SHOW_CLI_INSTRUCTIONS");
});
