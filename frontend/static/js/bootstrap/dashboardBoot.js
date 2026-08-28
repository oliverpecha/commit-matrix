import { hub } from "../core/eventHub.js?v=0.6.9";

const UI_THEME = {
    account: {
        title: "Account",
        color: "#8ab4f0",
        bg: "rgba(138,180,240,0.1)",
        border: "rgba(138,180,240,0.2)",
        toggleId: "cm-user-toggle",
        labelId: "cm-active-user",
        menuId: "cm-user-menu"
    },
    repo: {
        title: "Repository",
        color: "#8ed068",
        bg: "rgba(142,208,104,0.1)",
        border: "rgba(142,208,104,0.2)",
        toggleId: "cm-repo-toggle",
        labelId: "cm-active-repo-name",
        menuId: "cm-repo-menu"
    },
    rubric: {
        title: "Rubric",
        color: "#a38b4f",
        bg: "rgba(163,120,79,0.1)",
        border: "rgba(163,120,79,0.2)",
        toggleId: "cm-rubric-toggle",
        labelId: "cm-active-rubric-name",
        menuId: "cm-rubric-menu"
    }
};

const showScrollableModal = (title, contentText, color = "#a38b4f") => {
    const existing = document.getElementById("cm-modal-overlay");
    if (existing) existing.remove();

    const overlay = document.createElement("div");
    overlay.id = "cm-modal-overlay";
    overlay.style.cssText = "position:fixed; inset:0; background:rgba(0,0,0,0.75); backdrop-filter:blur(4px); z-index:100000; display:flex; align-items:center; justify-content:center; padding:24px; opacity:0; transition:opacity 0.2s ease-in-out;";

    const modal = document.createElement("div");
    modal.style.cssText = `background:#131314; border:1px solid ${color}; border-radius:10px; width:100%; max-width:820px; max-height:85vh; display:flex; flex-direction:column; box-shadow:0 20px 50px rgba(0,0,0,0.85); font-family:Satoshi, sans-serif; overflow:hidden;`;

    const header = document.createElement("div");
    header.style.cssText = "padding:14px 18px; display:flex; align-items:center; justify-content:space-between; border-bottom:1px solid rgba(255,255,255,0.08); background:rgba(255,255,255,0.02);";
    header.innerHTML = `
        <div style="display:flex; align-items:center; gap:8px;">
            <span style="font-size:11px; text-transform:uppercase; letter-spacing:0.05em; color:${color}; font-weight:700;">Own Rubric Template</span>
            <span style="color:#555; font-size:13px;">—</span>
            <span style="font-size:13px; color:#ddd; font-family:monospace;">${title}</span>
        </div>
        <button id="cm-modal-close-btn" style="background:transparent; border:none; color:#888; font-size:22px; line-height:1; cursor:pointer; padding:2px 8px; border-radius:4px;">&times;</button>
    `;

    const body = document.createElement("div");
    body.style.cssText = `padding:16px 20px; overflow-y:auto; flex-grow:1; scrollbar-width:thin; scrollbar-color:${color} rgba(255,255,255,0.05);`;

    const pre = document.createElement("pre");
    pre.style.cssText = "margin:0; white-space:pre-wrap; word-break:break-word; font-family:ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size:12px; line-height:1.6; color:#d1d5db;";
    pre.textContent = contentText;
    body.appendChild(pre);

    const footer = document.createElement("div");
    footer.style.cssText = "padding:10px 18px; background:#0a0e14; border-top:1px solid rgba(255,255,255,0.05); display:flex; justify-content:space-between; align-items:center; font-size:11px; color:#777;";
    footer.innerHTML = `
        <span>Save new rubrics as <code>rubrics/&lt;name&gt;.md</code> and restart scanner</span>
        <button id="cm-modal-close-footer" style="padding:6px 14px; background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.1); color:#ccc; border-radius:4px; cursor:pointer; font-size:11px;">Close</button>
    `;

    modal.appendChild(header);
    modal.appendChild(body);
    modal.appendChild(footer);
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    const closeModal = () => {
        overlay.style.opacity = "0";
        setTimeout(() => overlay.remove(), 200);
        document.removeEventListener("keydown", handleKey);
    };

    const handleKey = (e) => {
        if (e.key === "Escape") closeModal();
    };

    header.querySelector("#cm-modal-close-btn").addEventListener("click", closeModal);
    footer.querySelector("#cm-modal-close-footer").addEventListener("click", closeModal);
    overlay.addEventListener("click", (e) => {
        if (e.target === overlay) closeModal();
    });
    document.addEventListener("keydown", handleKey);

    requestAnimationFrame(() => {
        overlay.style.opacity = "1";
    });
};

window.triggerAddRepo = () => hub.emit("ACTION:ADD_REPO_REQUESTED");
window.triggerOwnRubric = async () => {
    try {
        const res = await fetch("/api/rubrics/guide?_t=" + Date.now());
        if (res.ok) {
            const data = await res.json();
            showScrollableModal(data.title || "RUBRIC_AUTHORING_GUIDE.md", data.content || "No guide content available.", UI_THEME.rubric.color);
            return;
        }
    } catch (_) {}
    showScrollableModal("RUBRIC_AUTHORING_GUIDE.md", "# Rubric Authoring Guide\n\nGuide file could not be loaded from API.", UI_THEME.rubric.color);
};

const initDashboard = async () => {
    const initialParams = new URLSearchParams(window.location.search);
    const initialOrg = initialParams.get("org");
    const initialRepo = initialParams.get("repo");
    const initialRubric = initialParams.get("rubric");

    Object.values(UI_THEME).forEach(cfg => {
        const toggleEl = document.getElementById(cfg.toggleId);
        const labelEl = document.getElementById(cfg.labelId);
        
        if (toggleEl) {
            toggleEl.style.background = cfg.bg;
            toggleEl.style.border = `1px solid ${cfg.border}`;
            toggleEl.style.color = cfg.color;
            
            toggleEl.querySelectorAll("svg").forEach(svg => {
                svg.style.stroke = cfg.color;
                svg.setAttribute("stroke", cfg.color);
            });
        }
        
        // Synchronous Pre-Hydration: Use URL params immediately to prevent FOUC
        let defaultText = cfg.title;
        if (cfg === UI_THEME.account && initialOrg) defaultText = initialOrg;
        if (cfg === UI_THEME.repo && initialRepo) defaultText = initialRepo;
        if (cfg === UI_THEME.rubric && initialRubric) defaultText = initialRubric.toUpperCase();

        if (labelEl && !labelEl.dataset.hydrated) {
            labelEl.textContent = defaultText;
            labelEl.dataset.hydrated = "true";
        } else if (!labelEl && toggleEl) {
            const spans = toggleEl.getElementsByTagName("span");
            if (spans.length > 0 && !spans[0].dataset.hydrated) {
                spans[0].textContent = defaultText;
                spans[0].dataset.hydrated = "true";
            }
        }
    });

    const closeAll = () => {
        Object.values(UI_THEME).forEach(cfg => {
            const menuEl = document.getElementById(cfg.menuId);
            if (menuEl) menuEl.style.display = "none";
        });
    };

    Object.values(UI_THEME).forEach(cfg => {
        const toggleEl = document.getElementById(cfg.toggleId);
        const menuEl = document.getElementById(cfg.menuId);
        if (toggleEl && menuEl) {
            const newToggle = toggleEl.cloneNode(true);
            toggleEl.replaceWith(newToggle);
            newToggle.addEventListener("click", (e) => {
                e.stopPropagation(); e.preventDefault();
                const isOpen = menuEl.style.display === "flex";
                closeAll();
                if (!isOpen) menuEl.style.display = "flex";
            });
            menuEl.addEventListener("click", (e) => e.stopPropagation());
        }
    });
    document.addEventListener("click", closeAll);

    const urlParams = new URLSearchParams(window.location.search);
    const activeRepo = urlParams.get("repo") || "";
    const activeRubric = urlParams.get("rubric") || "cirsd";
    const currentToken = urlParams.get("token") || "";

    try {
        const [reposRes, rubricsRes] = await Promise.all([
            fetch("/api/repos?_t=" + Date.now()),
            fetch("/api/rubrics?_t=" + Date.now())
        ]);
        const reposData = await reposRes.json();
        const rubricsData = await rubricsRes.json();

        const orgs = reposData.organizations || [];
        const allRepos = reposData.repos || [];
        const validRubrics = (rubricsData.rubrics || []).filter(r => r.id !== r.id.toUpperCase());

        const updLabel = (cfg, text) => {
            const el = document.getElementById(cfg.labelId);
            if (el) {
                el.textContent = text;
                el.dataset.hydrated = "true";
            } else {
                const toggle = document.getElementById(cfg.toggleId);
                if (toggle && toggle.children.length > 0) {
                    const spans = toggle.getElementsByTagName("span");
                    if (spans.length > 0) {
                        spans[0].textContent = text;
                        spans[0].dataset.hydrated = "true";
                    }
                }
            }
        };

        const updateContext = (paramKey, paramValue, displayLabel, themeCfg) => {
            const urlParams = new URLSearchParams(window.location.search);
            urlParams.set(paramKey, paramValue);
            
            // Context Isolation: Re-sync dependent children
            if (paramKey === "org") {
                const orgRepos = allRepos.filter(r => r.org === paramValue);
                if (orgRepos.length > 0) urlParams.set("repo", orgRepos[0].name);
            }
            
            history.pushState({}, '', '?' + urlParams.toString());
            updLabel(themeCfg, displayLabel);
            closeAll();
            hydrateState();
            hub.emit("CONTEXT_CHANGED", Object.fromEntries(urlParams.entries()));
        };

        const renderList = (cfg, items, activeId, idKey, labelKey, paramKey, footerHtml) => {
            const menu = document.getElementById(cfg.menuId);
            if (!menu) return;
            let html = `<div style="padding:12px; border-bottom:1px solid rgba(255,255,255,0.05); flex-grow:1; overflow-y:auto; max-height:400px; display:flex; flex-direction:column;">
                <div style="font-size:10px; color:#7a7874; text-transform:uppercase; letter-spacing:0.05em; margin-bottom:8px; font-family:Satoshi, sans-serif;">${cfg.title}</div>`;
            
            if (!items || items.length === 0) {
                html += `<div style="color:#666; font-size:12px; font-family:monospace; padding:8px;">No data</div>`;
            } else {
                items.forEach(item => {
                    const isSelected = String(item[idKey]) === String(activeId);
                    const labelStr = item[labelKey];
                    const valStr = item[idKey];
                    
                    if (isSelected) {
                        html += `
                        <div style="padding:8px 10px; margin-bottom:4px; border-radius:4px; background:${cfg.bg}; border:1px solid ${cfg.border}; color:${cfg.color}; font-family:monospace; font-size:12px; display:flex; align-items:center; justify-content:space-between; cursor:default;">
                            <span>${labelStr}</span><div style="width:6px; height:6px; background:${cfg.color}; border-radius:50%; box-shadow:0 0 4px ${cfg.color};"></div>
                        </div>`;
                    } else {
                        html += `
                        <div class="cm-menu-item" data-val="${valStr}" data-label="${labelStr}" data-param="${paramKey}" 
                             style="padding:8px 10px; margin-bottom:4px; border-radius:4px; color:#aaa; font-family:monospace; font-size:12px; display:flex; align-items:center; cursor:pointer; transition:background 0.2s;" 
                             onmouseover="this.style.background='rgba(255,255,255,0.05)'" onmouseout="this.style.background='transparent'">
                            <span>${labelStr}</span>
                        </div>`;
                    }
                });
            }
            html += `</div>${footerHtml || ""}`;
            menu.innerHTML = html;

            menu.querySelectorAll('.cm-menu-item').forEach(el => {
                el.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    updateContext(el.dataset.param, el.dataset.val, el.dataset.label, cfg);
                });
            });
        };

        const hydrateState = () => {
            const urlParams = new URLSearchParams(window.location.search);
            const activeRepo = urlParams.get("repo") || "";
            const activeRubric = urlParams.get("rubric") || "cirsd";
            
            let activeOrg = "";
            const activeRepoObj = allRepos.find(r => r.name === activeRepo);
            if (activeRepoObj) activeOrg = activeRepoObj.org;
            else if (orgs.length > 0) activeOrg = orgs[0].org;

            const createBtn = (cfg, actionStr, labelStr) => `<div style="padding:8px; background:#0a0e14; margin-top:auto;"><button onclick="${actionStr}" style="width:100%; padding:8px; background:transparent; border:1px dashed ${cfg.border}; color:${cfg.color}; border-radius:4px; cursor:pointer; font-weight:bold; font-size:11px; transition:all 0.2s ease; font-family:Satoshi, sans-serif;" onmouseover="this.style.background='${cfg.bg}';" onmouseout="this.style.background='transparent';">+ ${labelStr}</button></div>`;

            renderList(UI_THEME.account, orgs, activeOrg, "org", "org", "org", createBtn(UI_THEME.account, "window.triggerAddRepo()", "Add Repository"));
            renderList(UI_THEME.repo, allRepos.filter(r => r.org === activeOrg), activeRepo, "name", "name", "repo", createBtn(UI_THEME.repo, "window.triggerAddRepo()", "Add Repository"));
            renderList(UI_THEME.rubric, validRubrics, activeRubric, "id", "name", "rubric", createBtn(UI_THEME.rubric, "window.triggerOwnRubric()", "Own Rubric"));

            const requestedRepoMissing = activeRepo && !activeRepoObj;
            const isInvalidState = requestedRepoMissing || window.MATRIX_INVALID_REPO || window.MATRIX_SYSTEM_EMPTY;

            if (isInvalidState) {
                updLabel(UI_THEME.account, UI_THEME.account.title);
                updLabel(UI_THEME.repo, UI_THEME.repo.title);
                updLabel(UI_THEME.rubric, UI_THEME.rubric.title);
            } else {
                updLabel(UI_THEME.account, activeOrg || UI_THEME.account.title);
                updLabel(UI_THEME.repo, activeRepoObj ? activeRepoObj.name : UI_THEME.repo.title);
                const rObj = validRubrics.find(r => String(r.id) === String(activeRubric));
                updLabel(UI_THEME.rubric, rObj ? rObj.name.toUpperCase() : UI_THEME.rubric.title);
            }
        };

        hydrateState();

        window.addEventListener("popstate", () => {
            hydrateState();
            hub.emit("CONTEXT_CHANGED", Object.fromEntries(new URLSearchParams(window.location.search).entries()));
        });
    } catch (e) {
        console.error("Menu hydration failed:", e);
    }
};

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initDashboard);
} else {
    initDashboard();
}
