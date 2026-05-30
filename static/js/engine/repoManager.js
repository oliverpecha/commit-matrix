console.log('📦 Module Boot: repoManager.js loaded and active.');
import { hub } from "../core/eventHub.js";

hub.on("ACTION:REFRESH_LEDGER", () => {
    const urlParams = new URLSearchParams(window.location.search);
    const repo = urlParams.get("repo") || "commit-matrix";
    const token = urlParams.get("token") || "";
    hub.emit("ENGINE:SCAN_REQUESTED", { repo, token });
});

hub.on("ACTION:ADD_REPO_REQUESTED", () => {
    hub.emit("UI:SHOW_CLI_INSTRUCTIONS");
});
