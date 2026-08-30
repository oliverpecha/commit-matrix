
import { hub } from "../core/eventHub.js?v=0.6.51";
import { EVENTS, UI_LABELS } from "../core/state.js?v=0.6.51";

// Hydrate header button
document.addEventListener("DOMContentLoaded", () => {
    const syncBtn = document.getElementById("cm-sync-btn");
    if (syncBtn) {
        syncBtn.innerHTML = UI_LABELS.SYNC_BTN_ACTIVE;
        syncBtn.addEventListener("click", () => {
            syncBtn.innerHTML = UI_LABELS.SYNC_BTN_LOADING;
            hub.emit(EVENTS.SYNC_REQUESTED);
            setTimeout(() => syncBtn.innerHTML = UI_LABELS.SYNC_BTN_ACTIVE, 3000);
        });
    }
});
(async function initPageBoot() {
    console.log("[CommitMatrix] 🚀 pageBoot.js v0.2.3 executing (Pure JS Edition)...");

    const payloadScript = document.getElementById("cm-page-payload");
    if (payloadScript) {
        try {
            const payload = JSON.parse(payloadScript.textContent || "{}");
            // Decoupled progressive loading state
            window.MATRIX_CHART_PAYLOAD = payload.chart_data || [];
            window.MATRIX_PAYLOAD = payload.table_data || []; 
            
            window.MATRIX_TIME_AUTOCLOSE = payload.time_autoclose;
            window.MATRIX_SYSTEM_EMPTY = payload.system_empty || false;
            window.MATRIX_INVALID_REPO = payload.invalid_repo || false;
            window.MATRIX_INVALID_RUBRIC = payload.invalid_rubric || false;
        } catch (err) {
            window.MATRIX_PAYLOAD = [];
        }
    }

    

    // --- Bulletproof JS Event Delegation ---
    document.addEventListener("click", function(e) {
        const rToggle = e.target.closest("#cm-repo-toggle");
        const uToggle = e.target.closest("#cm-user-toggle");
        const rMenu = document.getElementById("DISABLE_cm-repo-menu");
        const uMenu = document.getElementById("DISABLE_cm-user-menu");

        // Toggle Repo Menu
        if (rToggle && rMenu) {
            e.preventDefault();
            e.stopPropagation();
            console.log("[CommitMatrix] 🖱️ Repo Toggle activated via closest()");
            const isOpen = rMenu.style.display === "flex";
            rMenu.style.display = isOpen ? "none" : "flex";
            if (uMenu) uMenu.style.display = "none";
            return;
        }

        // Toggle User Menu
        if (uToggle && uMenu) {
            e.preventDefault();
            e.stopPropagation();
            console.log("[CommitMatrix] 🖱️ User Toggle activated via closest()");
            const isOpen = uMenu.style.display === "flex";
            uMenu.style.display = isOpen ? "none" : "flex";
            if (rMenu) rMenu.style.display = "none";
            return;
        }

        // Global Click-away Closer
        if (rMenu && !rMenu.contains(e.target)) rMenu.style.display = "none";
        if (uMenu && !uMenu.contains(e.target)) uMenu.style.display = "none";
    });

    // --- Render Empty/Invalid UI States ---
    const wrap = document.getElementById("main-dashboard-wrap");
    
    const urlParams = new URLSearchParams(window.location.search);
    const currentRepo = urlParams.get("repo") || "";
    const currentRubric = urlParams.get("rubric") || "";

    if (window.MATRIX_SYSTEM_EMPTY && wrap) {
        wrap.innerHTML = `<div style="padding:80px 20px; text-align:center; color:#aaa; font-family:Satoshi, sans-serif;">
            <h2 style="color:#d9d8d5; margin-bottom:12px;">Welcome to CommitMatrix</h2>
            <p style="margin-bottom:24px;">Your telemetry engine is online, but no repositories were found.</p>
            <button onclick="window.hub.emit('ACTION:ADD_REPO_REQUESTED')" style="padding:10px 20px; background:rgba(79,152,163,0.15); border:1px solid rgba(79,152,163,0.4); color:#4f98a3; border-radius:6px; cursor:pointer; font-weight:bold;">+ Add First Repository</button>
        </div>`;
    } else if ((window.MATRIX_INVALID_REPO || window.MATRIX_INVALID_RUBRIC) && wrap) {
        let titleText = "Not Found";
        let bodyText = "The requested resource could not be found.";

        if (window.MATRIX_INVALID_RUBRIC) {
            titleText = "Invalid Rubric";
            bodyText = `The rubric <code style="color:#e06c75; background:rgba(224,108,117,0.1); padding:2px 6px; border-radius:4px;">${currentRubric}</code> does not exist on the server.`;
        } else if (window.MATRIX_INVALID_REPO) {
            titleText = currentRepo ? "Repository Not Found" : "No Repository Selected";
            bodyText = currentRepo 
                ? `The path <code style="color:#e06c75; background:rgba(224,108,117,0.1); padding:2px 6px; border-radius:4px;">${currentRepo}</code> does not exist or lacks a telemetry database.` 
                : `Please select a repository from the top menu.`;
        }

        wrap.innerHTML = `<div style="padding:80px 20px; text-align:center; color:#aaa; font-family:Satoshi, sans-serif;">
            <h2 style="color:#e06c75; margin-bottom:12px;">${titleText}</h2>
            <p>${bodyText}</p>
            <p style="margin-top:16px; font-size:13px; opacity:0.7;">Select a valid configuration from the top menu.</p>
        </div>`;
    }

    // --- Listen to Context Changes & Init Observers ---
    try {
        const { initInfiniteScroll } = await import("../ui/tableRender.js?v=0.6.51");
        if (!window.MATRIX_SYSTEM_EMPTY && !window.MATRIX_INVALID_REPO) {
            const p = new URLSearchParams(window.location.search);
            initInfiniteScroll(p.get("repo") || "commit-matrix", 100);
        }

        const { hub } = await import("../core/eventHub.js?v=0.6.51");
        window.hub = hub; // Ensure inline handlers like (Add Repo) retain access
        
        hub.on("CONTEXT_CHANGED", (payload) => {
        console.log(`[CommitMatrix] 🔄 Context rotated to ${payload.repo}. State sync delegated to app.js...`);
    });
    } catch (e) {
        console.error("[CommitMatrix] Failed to hook Event Hub in pageBoot.js", e);
    }
})();