import { hub } from "../core/eventHub.js?v=0.1.24";

const UI_THEME = window.UI_THEME;

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
    const initialOwner = initialParams.get("owner");
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
        if (cfg === UI_THEME.owner && initialOwner) defaultText = initialOwner;
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
    const activeRubric = urlParams.get("rubric") || "";
    const currentToken = urlParams.get("token") || "";

    try {
        window.fetchRubricsForRepo = async (repoName) => {
            const res = await fetch(`/api/rubrics?owner=${typeof owner !== "undefined" ? owner : (window.MATRIX_OWNER || "local")}&repo=${repoName}&_t=` + Date.now());
            const data = await res.json();
            // Explicitly filter out system documentation files
            const rawRubrics = (data.rubrics || []).filter(r => !['RUBRIC_AUTHORING_GUIDE', 'README'].includes((r.id || '').toUpperCase()));
            const existing = rawRubrics.filter(r => r.has_data).sort((a, b) => a.name.localeCompare(b.name));
            const unexisting = rawRubrics.filter(r => !r.has_data).sort((a, b) => a.name.localeCompare(b.name));
            let finalRubrics = [...existing];
            if (existing.length > 0 && unexisting.length > 0) finalRubrics.push({ id: "__DIVIDER__", isDivider: true });
            return finalRubrics.concat(unexisting);
        };

        const [reposRes] = await Promise.all([
            fetch("/api/repos?_t=" + Date.now())
        ]);
        const reposData = await reposRes.json();

        const loadedOwners = reposData.owners || [];
        const allRepos = reposData.repos || [];
        console.log('[Menu Hydration] Owners loaded:', loadedOwners.map(o => o.owner).join(', '));
        console.log('[Menu Hydration] Repos loaded:', allRepos.map(r => r.name).join(', '));

        

                let fetchRepo = activeRepo;
        if (!fetchRepo && allRepos.length > 0) fetchRepo = allRepos[0].name;
        window.VALID_RUBRICS = await window.fetchRubricsForRepo(fetchRepo);
        console.log('[Menu Hydration] Rubrics loaded for active repo:', window.VALID_RUBRICS.map(r => r.name || r.id || r).join(', '));

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

        const updateContext = async (paramKey, paramValue, displayLabel, themeCfg) => {
            const urlParams = new URLSearchParams(window.location.search);
            urlParams.set(paramKey, paramValue);
            
            // Context Isolation: Re-sync dependent children
            if (paramKey === "owner") {
                const ownerRepos = allRepos.filter(r => r.owner === paramValue);
                if (ownerRepos.length > 0) urlParams.set("repo", ownerRepos[0].name);
            }
            
            if (paramKey === "owner" || paramKey === "repo") {
                const newRepo = urlParams.get("repo");
                window.VALID_RUBRICS = await window.fetchRubricsForRepo(newRepo);
        console.log('[Menu Hydration] Rubrics loaded for active repo:', window.VALID_RUBRICS.map(r => r.name || r.id || r).join(', '));
                const existing = window.VALID_RUBRICS.filter(r => r.has_data === true);
                const currentRubricId = urlParams.get("rubric");
                
                // Try to preserve the current rubric if it's available in the new repo
                const isCurrentAvailable = existing.some(r => r.id === currentRubricId);
                
                if (!isCurrentAvailable) {
                    // 💥 Prevent auto-selecting physical files if the system is completely empty
                    if (!window.MATRIX_SYSTEM_EMPTY) {
                        const firstTarget = existing.length > 0 ? existing[0] : window.VALID_RUBRICS.find(r => !r.isDivider);
                        if (firstTarget) urlParams.set("rubric", firstTarget.id);
                    }
                }
            }
            
            // If recovering from a destructive error state, force a hard reload to reconstruct the DOM canvases.
            if (window.MATRIX_SYSTEM_EMPTY || window.MATRIX_INVALID_OWNER || window.MATRIX_INVALID_REPO || window.MATRIX_INVALID_RUBRIC) {
                window.location.href = '?' + urlParams.toString();
                return;
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
                    if (item.isDivider) {
                        html += `<div style="height:1px; background:rgba(255,255,255,0.08); margin:8px 10px;"></div>`;
                        return;
                    }

                    const isSelected = String(item[idKey]) === String(activeId);
                    const labelStr = item[labelKey];
                    const valStr = item[idKey];
                    
                    if (isSelected) {
                        const dotColor = cfg.menuId === "cm-rubric-menu" ? (item.has_data === false ? "#ff4a4a" : "#34d399") : cfg.color;
                        html += `
                        <div style="padding:8px 10px; margin-bottom:4px; border-radius:4px; background:${cfg.bg}; border:1px solid ${cfg.border}; color:${cfg.color}; font-family:monospace; font-size:12px; display:flex; align-items:center; justify-content:space-between; cursor:default;">
                            <span>${labelStr}</span><div style="width:6px; height:6px; background:${dotColor}; border-radius:50%; box-shadow:0 0 4px ${dotColor};"></div>
                        </div>`;
                    } else {
                        let dotHtml = "";
                        let baseStyle = "padding:8px 10px; margin-bottom:4px; border-radius:4px; font-family:monospace; font-size:12px; display:flex; align-items:center; cursor:pointer; transition:background 0.2s;";
                        let textStyle = "color:#aaa;";
                        
                        if (cfg.menuId === "cm-rubric-menu" && item.has_data === false) {
                            dotHtml = `<div style="width:6px; height:6px; background:#444; border-radius:50%; margin-left:auto;" title="No ledger data"></div>`;
                            textStyle = "color:#666; opacity:0.6;";
                        }
                        
                        html += `
                        <div class="cm-menu-item" data-val="${valStr}" data-label="${labelStr}" data-param="${paramKey}" 
                             style="${baseStyle} ${textStyle}" 
                             onmouseover="this.style.background='rgba(255,255,255,0.05)'" onmouseout="this.style.background='transparent'">
                            <span>${labelStr}</span>${dotHtml}
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
            // 💥 URL SANITIZER: Defeat browser autocomplete. If system is empty, strip all URL parameters.
            if (window.MATRIX_SYSTEM_EMPTY && window.location.search) {
                window.history.replaceState({}, document.title, window.location.pathname);
            }
            const urlParams = new URLSearchParams(window.location.search);
            const activeRepo = urlParams.get("repo") || "";
            let activeRubric = urlParams.get("rubric");

            if (!activeRubric && window.VALID_RUBRICS && window.VALID_RUBRICS.length > 0) {
                const existing = window.VALID_RUBRICS.filter(r => r.has_data === true);
                if (existing.length > 0) {
                    activeRubric = existing[0].id;
                    urlParams.set("rubric", activeRubric);
                    window.history.replaceState({}, '', '?' + urlParams.toString());
                }
            }
            
            let activeOwner = urlParams.get("owner") || "";
            const activeRepoObj = allRepos.find(r => r.name === activeRepo);
            if (activeRepoObj) activeOwner = activeRepoObj.owner;
            else if (!activeOwner && loadedOwners.length > 0) activeOwner = loadedOwners[0].owner;

            const createBtn = (cfg, actionStr, labelStr) => `<div style="padding:8px; background:#0a0e14; margin-top:auto;"><button onclick="${actionStr}" style="width:100%; padding:8px; background:transparent; border:1px dashed ${cfg.border}; color:${cfg.color}; border-radius:4px; cursor:pointer; font-weight:bold; font-size:11px; transition:all 0.2s ease; font-family:Satoshi, sans-serif;" onmouseover="this.style.background='${cfg.bg}';" onmouseout="this.style.background='transparent';">+ ${labelStr}</button></div>`;

            const requestedRepoMissing = activeRepo && !activeRepoObj;
            
            let repoList = allRepos.filter(r => r.owner === activeOwner);
            let rubricList = window.VALID_RUBRICS || [];
            let highlightOwner = activeOwner;
            let highlightRepo = activeRepo;
            let highlightRubric = activeRubric;

            // Cascade clearing: If a parent is invalid, all children and active highlights must be cleared
            if (window.MATRIX_SYSTEM_EMPTY || window.MATRIX_INVALID_OWNER) {
                repoList = [];
                rubricList = [];
                highlightOwner = "";
                highlightRepo = "";
                highlightRubric = "";
            } else if (window.MATRIX_INVALID_REPO || requestedRepoMissing) {
                rubricList = [];
                highlightRepo = "";
                highlightRubric = "";
            } else if (window.MATRIX_INVALID_RUBRIC) {
                highlightRubric = "";
            }

            renderList(UI_THEME.owner, loadedOwners, highlightOwner, "owner", "owner", "owner", createBtn(UI_THEME.owner, "window.triggerAddRepo()", "Add Repository"));
            renderList(UI_THEME.repo, repoList, highlightRepo, "name", "name", "repo", createBtn(UI_THEME.repo, "window.triggerAddRepo()", "Add Repository"));
            renderList(UI_THEME.rubric, rubricList, highlightRubric, "id", "name", "rubric", createBtn(UI_THEME.rubric, "window.triggerOwnRubric()", "Own Rubric"));

            if (window.MATRIX_SYSTEM_EMPTY || window.MATRIX_INVALID_OWNER) {
                updLabel(UI_THEME.owner, UI_THEME.owner.title);
                updLabel(UI_THEME.repo, UI_THEME.repo.title);
                updLabel(UI_THEME.rubric, UI_THEME.rubric.title);
            } else if (window.MATRIX_INVALID_REPO || requestedRepoMissing) {
                updLabel(UI_THEME.owner, activeOwner || UI_THEME.owner.title);
                updLabel(UI_THEME.repo, UI_THEME.repo.title);
                updLabel(UI_THEME.rubric, UI_THEME.rubric.title);
            } else if (window.MATRIX_INVALID_RUBRIC) {
                updLabel(UI_THEME.owner, activeOwner || UI_THEME.owner.title);
                updLabel(UI_THEME.repo, activeRepoObj ? activeRepoObj.name : UI_THEME.repo.title);
                updLabel(UI_THEME.rubric, UI_THEME.rubric.title);
            } else {
                updLabel(UI_THEME.owner, activeOwner || UI_THEME.owner.title);
                updLabel(UI_THEME.repo, activeRepoObj ? activeRepoObj.name : UI_THEME.repo.title);
                const rObj = window.VALID_RUBRICS.find(r => String(r.id) === String(activeRubric));
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
