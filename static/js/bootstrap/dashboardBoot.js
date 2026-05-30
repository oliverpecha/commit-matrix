import { toggleDashboardLayout } from "../ui/dashboardLayout.js";

document.addEventListener("DOMContentLoaded", () => {
    const setups = [
        { toggle: "cm-user-toggle", menu: "cm-user-menu" },
        { toggle: "cm-repo-toggle", menu: "cm-repo-menu" }
    ];

    const closeAllMenus = () => {
        setups.forEach(s => {
            const menuEl = document.getElementById(s.menu);
            const toggleEl = document.getElementById(s.toggle);
            if (menuEl) menuEl.style.display = "none";
            if (toggleEl) toggleEl.style.background = "rgba(138,180,240,0.05)";
        });
    };

    setups.forEach(s => {
        const toggleEl = document.getElementById(s.toggle);
        const menuEl = document.getElementById(s.menu);

        if (toggleEl && menuEl) {
            toggleEl.addEventListener("click", (e) => {
                e.stopPropagation();
                const wasHidden = menuEl.style.display === "none";
                closeAllMenus();

                if (wasHidden) {
                    menuEl.style.display = "flex";
                    toggleEl.style.background = "rgba(138,180,240,0.15)";
                }
            });
        }
    });

    document.addEventListener("click", (e) => {
        let clickedInside = false;
        setups.forEach(s => {
            const menuEl = document.getElementById(s.menu);
            if (menuEl && menuEl.contains(e.target)) clickedInside = true;
        });
        if (!clickedInside) closeAllMenus();
    });
});

window.toggleDashboardLayout = toggleDashboardLayout;
