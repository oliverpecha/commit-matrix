// v0.1.11
import { hub } from "../core/eventHub.js?v=0.6.51";

async function postEngineControl(action) {
    const urlParams = new URLSearchParams(window.location.search);
    const repo = urlParams.get("repo") || "";
    const rubric = urlParams.get("rubric") || "cirsd";
    const resp = await fetch(`/api/engine/control?action=${action}&repo=${repo}&rubric=${rubric}`, { method: "POST" });
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
