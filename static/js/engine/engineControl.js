import { hub } from "../core/eventHub.js";

async function postEngineControl(action) {
    const urlParams = new URLSearchParams(window.location.search);
    const repo = urlParams.get("repo") || "commit-matrix";
    const resp = await fetch(`/api/engine/control?action=${action}&repo=${repo}`, { method: "POST" });
    return resp.json();
}

function getScanRequestPayload() {
    const urlParams = new URLSearchParams(window.location.search);
    return {
        repo: urlParams.get("repo") || "commit-matrix",
        rubric: urlParams.get("rubric") || "",
        token: urlParams.get("token") || "",
    };
}


hub.on("ACTION:CLOSE_TERMINAL", () => {
    hub.emit("ENGINE:EXIT_REQUESTED");
});

hub.on("ACTION:REFRESH_LEDGER", () => {
    hub.emit("ENGINE:SCAN_REQUESTED", getScanRequestPayload());
});
