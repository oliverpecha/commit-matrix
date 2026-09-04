// v0.1.12
import { hub } from "../core/eventHub.js?v=0.7.75";

async function postEngineControl(action) {
    const urlParams = new URLSearchParams(window.location.search);
    const repo = urlParams.get("repo") || "";
    const rubric = urlParams.get("rubric") || window.MATRIX_DEFAULT_RUBRIC || "unknown";
    const resp = await fetch(`/api/engine/control?action=${action}&owner=${urlParams.get("owner") || window.MATRIX_OWNER || ""}&repo=${repo}&rubric=${rubric}`, { method: "POST" });
    return resp.json();
}

function getScanRequestPayload() {
    const urlParams = new URLSearchParams(window.location.search);
    const payload = { repo: urlParams.get("repo") || "" };
    if (urlParams.get("rubric")) payload.rubric = urlParams.get("rubric");
    if (urlParams.get("token")) payload.token = urlParams.get("token");
    return payload;
}


hub.on("ACTION:CLOSE_TERMINAL", () => {
    postEngineControl("stop");
    hub.emit("ENGINE:EXIT_REQUESTED");
});

hub.on("ACTION:REFRESH_LEDGER", () => {
    if (window.MATRIX_INVALID_REPO || window.MATRIX_SYSTEM_EMPTY) {
        console.warn("[engineControl] Refresh ignored: current repository is invalid or not found.");
        return;
    }
    hub.emit("ENGINE:SCAN_REQUESTED", getScanRequestPayload());
});
