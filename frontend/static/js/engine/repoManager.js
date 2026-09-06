console.log('📦 Module Boot: repoManager.js loaded and active.');
<<<<<<< Updated upstream
import { hub } from "../core/eventHub.js?v=0.1.59";
=======
import { hub } from "../core/eventHub.js?v=0.1.59";
>>>>>>> Stashed changes

hub.on("ACTION:ADD_REPO_REQUESTED", () => {
    hub.emit("UI:SHOW_CLI_INSTRUCTIONS");
});
