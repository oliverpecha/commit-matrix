class EventHub {
    constructor() {
        this.listeners = new Map();
        this.lastFired = new Map();
    }
    on(eventName, callback) {
        console.log(`[HUB] 🎧 Listener attached for: ${eventName}`);
        if (!this.listeners.has(eventName)) this.listeners.set(eventName, new Set());
        this.listeners.get(eventName).add(callback);
        return () => this.off(eventName, callback);
    }
    off(eventName, callback) {
        if (this.listeners.has(eventName)) {
            this.listeners.get(eventName).delete(callback);
        }
    }
    emit(eventName, payload = null) {
        // --- SELECTIVE DEBOUNCE LOGIC ---
        // ONLY debounce user ACTION events to prevent double-clicks.
        // NEVER debounce ENGINE streams, as they rely on high-frequency chunking.
        if (eventName.startsWith('ACTION:')) {
            const now = Date.now();
            if (this.lastFired.has(eventName) && (now - this.lastFired.get(eventName)) < 500) {
                console.warn(`[HUB] 🛡️ Debounced duplicate user action: ${eventName}`);
                return; // Block the ghost click
            }
            this.lastFired.set(eventName, now);
        }
        
        console.log(`[HUB] 📢 Broadcast triggered: ${eventName}`);
        let handled = false;
        
        if (this.listeners.has(eventName)) {
            this.listeners.get(eventName).forEach(cb => { cb(payload, eventName); handled = true; });
        }
        
        const parts = eventName.split(':');
        if (parts.length > 1) {
            const wildcard = `${parts[0]}:*`;
            if (this.listeners.has(wildcard)) {
                this.listeners.get(wildcard).forEach(cb => { cb(payload, eventName); handled = true; });
            }
        }
        
        if (!handled) console.warn(`[HUB] ⚠️ SIGNAL DROPPED: No modules are listening for ${eventName}`);
    }
}
export const hub = new EventHub();
