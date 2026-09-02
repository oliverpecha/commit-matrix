
import { hub } from "../core/eventHub.js?v=0.7.75";
import { EVENTS, UI_LABELS } from "../core/state.js?v=0.7.75";

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
    console.log("[CommitMatrix] 🚀 pageBoot.js v0.2.5 executing (Pure JS Edition)...");

    const payloadScript = document.getElementById("cm-page-payload");
    if (payloadScript) { window.MATRIX_DEFAULT_RUBRIC = JSON.parse(payloadScript.textContent).default_rubric || "unknown"; }
    if (payloadScript) {
        try {
            const payload = JSON.parse(payloadScript.textContent || "{}");
            // Decoupled progressive loading state
            window.MATRIX_CHART_PAYLOAD = payload.chart_data || [];
            window.MATRIX_PAYLOAD = payload.table_data || []; 
            
            window.MATRIX_TIME_AUTOCLOSE = payload.time_autoclose;
            window.MATRIX_SYSTEM_EMPTY = payload.system_empty || false;
            window.MATRIX_INVALID_OWNER = payload.invalid_owner || false;
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

    const THEME = window.UI_THEME;

    if (window.MATRIX_SYSTEM_EMPTY) {
        // Bulletproof the empty state: hide ALL other UI elements and render a full-viewport overlay
        document.head.insertAdjacentHTML('beforeend', '<style>body > *:not(#cm-zero-state-overlay):not(script) { display: none !important; }</style>');
        
        const overlay = document.createElement('div');
        overlay.id = 'cm-zero-state-overlay';
        overlay.style.cssText = 'position:fixed; top:0; left:0; width:100vw; height:100vh; background:#141414; z-index:999999; display:flex; flex-direction:column; align-items:center; justify-content:center; overflow:hidden;';
        
        overlay.innerHTML = `<div style="padding:40px 20px; text-align:center; color:#aaa; font-family:Satoshi, sans-serif;">
            <div style="font-size:48px; margin-bottom:16px;">🌌</div>
            <h2 style="color:#d9d8d5; margin-bottom:12px; font-weight:600;">Welcome to Commit-Matrix</h2>
            <p style="max-width:500px; margin:0 auto 24px auto; line-height:1.6; color:#888;">Let's get started by ingesting your first repository!</p>
            <button onclick="window.triggerAddRepo()" style="padding:12px 24px; background:rgba(79,152,163,0.1); border:1px solid #4f98a3; color:#4f98a3; border-radius:6px; cursor:pointer; font-weight:bold; font-size:15px; font-family:Satoshi, sans-serif; transition:all 0.2s ease; box-shadow: 0 4px 12px rgba(0,0,0,0.2);" onmouseover="this.style.background='rgba(79,152,163,0.2)';" onmouseout="this.style.background='rgba(79,152,163,0.1)';">+ Add Repository</button>
            <div style="margin-top:32px; padding-top:24px; border-top:1px solid rgba(255,255,255,0.05);">
                <p style="margin-bottom:12px; font-size:13px; color:#666;">Or ingest manually via host terminal:</p>
                <pre style="background:rgba(255,255,255,0.02); padding:12px 16px; border-radius:6px; color:#a38b4f; display:inline-block; text-align:left; font-family:monospace; border:1px solid rgba(163,139,79,0.2); font-size:12px;"><code>cd /path/to/your/repo
commit-matrix</code></pre>
            </div>
        </div>`;
        
        if (wrap) wrap.style.display = 'none';
        document.body.appendChild(overlay);
    } else if ((window.MATRIX_INVALID_OWNER || window.MATRIX_INVALID_REPO || window.MATRIX_INVALID_RUBRIC) && wrap) {
        document.querySelectorAll('#cm-header-actions, .cm-header-actions, #cm-toolbar, .cm-toolbar, #cm-actions, .cm-actions, #cm-repo-controls').forEach(el => el.remove());
        
        let titleText = "Not Found";
        let bodyText = "The requested resource could not be found.";
        let actionHtml = "";
        let themeColor = "#e06c75";
        const currentOwner = urlParams.get("owner") || "";

        if (window.MATRIX_INVALID_OWNER) {
            themeColor = THEME.owner.color;
            titleText = "Owner Not Found";
            bodyText = `The owner <code style="color:${THEME.owner.color}; background:${THEME.owner.bg}; padding:2px 6px; border-radius:4px;">${currentOwner}</code> does not exist on the server yet.`;
            actionHtml = `<div style="margin-top:24px;"><button onclick="window.triggerAddRepo()" style="padding:10px 16px; background:transparent; border:1px dashed ${THEME.owner.color}; color:${THEME.owner.color}; border-radius:4px; cursor:pointer; font-weight:bold; font-family:Satoshi, sans-serif; transition:all 0.2s ease;" onmouseover="this.style.background='${THEME.owner.bg}';" onmouseout="this.style.background='transparent';">+ Add Repository</button></div>`;
        } else if (window.MATRIX_INVALID_REPO) {
            themeColor = THEME.repo.color;
            titleText = currentRepo ? "Repository Not Found" : "No Repository Selected";
            bodyText = currentRepo 
                ? `The repository <code style="color:${THEME.repo.color}; background:${THEME.repo.bg}; padding:2px 6px; border-radius:4px;">${currentRepo}</code> does not exist under this owner yet.` 
                : `Please select a repository from the top menu.`;
            actionHtml = `<div style="margin-top:24px;"><button onclick="window.triggerAddRepo()" style="padding:10px 16px; background:transparent; border:1px dashed ${THEME.repo.color}; color:${THEME.repo.color}; border-radius:4px; cursor:pointer; font-weight:bold; font-family:Satoshi, sans-serif; transition:all 0.2s ease;" onmouseover="this.style.background='${THEME.repo.bg}';" onmouseout="this.style.background='transparent';">+ Add Repository</button></div>`;
        } else if (window.MATRIX_INVALID_RUBRIC) {
            themeColor = THEME.rubric.color;
            titleText = "Invalid Rubric";
            bodyText = `The rubric <code style="color:${THEME.rubric.color}; background:${THEME.rubric.bg}; padding:2px 6px; border-radius:4px;">${currentRubric}</code> does not exist yet.`;
            actionHtml = `<div style="margin-top:24px;"><button onclick="window.triggerOwnRubric()" style="padding:10px 16px; background:transparent; border:1px dashed ${THEME.rubric.color}; color:${THEME.rubric.color}; border-radius:4px; cursor:pointer; font-weight:bold; font-family:Satoshi, sans-serif; transition:all 0.2s ease;" onmouseover="this.style.background='${THEME.rubric.bg}';" onmouseout="this.style.background='transparent';">+ Create Own Rubric</button></div>`;
        }

        wrap.innerHTML = `<style>header, #cm-header, .cm-header-nav, .cm-top-nav, nav, .header-container { display: none !important; }</style><div style="padding:80px 20px; text-align:center; color:#aaa; font-family:Satoshi, sans-serif;">
            <h2 style="color:${themeColor}; margin-bottom:12px;">${titleText}</h2>
            <p>${bodyText}</p>
            ${actionHtml}
            <p style="margin-top:24px; font-size:13px; opacity:0.7;">Otherwise select a valid configuration from the top menu.</p>
        </div>`;
    }

    // --- Listen to Context Changes & Init Observers ---
    try {
        const { initInfiniteScroll } = await import("../ui/tableRender.js?v=0.7.75");
        if (!window.MATRIX_SYSTEM_EMPTY && !window.MATRIX_INVALID_REPO) {
            const p = new URLSearchParams(window.location.search);
            initInfiniteScroll(p.get("repo") || "commit-matrix", 100);
        }

        const { hub } = await import("../core/eventHub.js?v=0.7.75");
        window.hub = hub; // Ensure inline handlers like (Add Repo) retain access
        
        hub.on("CONTEXT_CHANGED", (payload) => {
        console.log(`[CommitMatrix] 🔄 Context rotated to ${payload.repo}. State sync delegated to app.js...`);
    });
    } catch (e) {
        console.error("[CommitMatrix] Failed to hook Event Hub in pageBoot.js", e);
    }
})();