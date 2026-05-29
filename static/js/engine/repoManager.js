console.log('📦 Module Boot: repoManager.js loaded and active.');
import { hub } from "../core/eventHub.js";

hub.on("ACTION:REFRESH_LEDGER", () => {
    const urlParams = new URLSearchParams(window.location.search);
    const repo = urlParams.get("repo") || "commit-matrix";
    const token = urlParams.get("token") || "";
    hub.emit("ENGINE:SCAN_REQUESTED", { repo, token });
});

hub.on("ACTION:TOGGLE_ENGINE", async (payload) => {
    const { action } = payload;
    const urlParams = new URLSearchParams(window.location.search);
    hub.emit("ENGINE:CONTROL_UPDATING", { action });
    try {
        const resp = await fetch(`/api/engine/control?action=${action}&token=${urlParams.get("token")}`, { method: "POST" });
        const data = await resp.json();
        hub.emit("ENGINE:CONTROL_UPDATED", { action, status: data.status });
    } catch (e) { hub.emit("ENGINE:CONTROL_UPDATED", { action, status: "error" }); }
});

hub.on("ACTION:ADD_REPO_REQUESTED", () => {
    hub.emit("UI:SHOW_CLI_INSTRUCTIONS");
});