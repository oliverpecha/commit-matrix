import { hub } from "../core/eventHub.js";

hub.on("ACTION:TOGGLE_ENGINE", async ({ action }) => {
    const urlParams = new URLSearchParams(window.location.search);
    hub.emit("ENGINE:CONTROL_UPDATING", { action });

    try {
        const resp = await fetch(`/api/engine/control?action=${action}&repo=${urlParams.get('repo') || 'commit-matrix'}`, {
            method: "POST"
        });
        const data = await resp.json();
        hub.emit("ENGINE:CONTROL_UPDATED", { action, status: data.status });
    } catch (e) {
        hub.emit("ENGINE:CONTROL_UPDATED", { action, status: "error" });
    }
});

hub.on("ACTION:CLOSE_TERMINAL", () => {
    hub.emit("ENGINE:EXIT_REQUESTED");
});
