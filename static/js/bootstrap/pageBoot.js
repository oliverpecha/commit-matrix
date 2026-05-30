document.addEventListener("DOMContentLoaded", function() {
    const payloadScript = document.getElementById("cm-page-payload");
    if (payloadScript) {
        try {
            const payload = JSON.parse(payloadScript.textContent || "{}");
            window.MATRIX_PAYLOAD = payload.commits_data || [];
            window.MATRIX_TIME_AUTOCLOSE = payload.time_autoclose;
        } catch (err) {
            console.warn("Failed to parse cm-page-payload", err);
            window.MATRIX_PAYLOAD = window.MATRIX_PAYLOAD || [];
        }
    }

    const urlParams = new URLSearchParams(window.location.search);
    const repoSpan = document.getElementById("cm-active-repo");
    if (repoSpan) {
        repoSpan.textContent = urlParams.get("repo") || "commit-matrix";
    }
});
