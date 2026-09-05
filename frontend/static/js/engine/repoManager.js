console.log('📦 Module Boot: repoManager.js loaded and active.');
import { hub } from "../core/eventHub.js?v=0.1.24";

hub.on("ACTION:ADD_REPO_REQUESTED", () => {
    hub.emit("UI:SHOW_CLI_INSTRUCTIONS");
});
