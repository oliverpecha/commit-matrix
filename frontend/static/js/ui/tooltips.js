import { CM_EXPLANATIONS } from '../constants/explanations.js';

export function initGlobalTooltips() {
    const infoTtEl = document.getElementById('info-tt');
    if (!infoTtEl) return console.error("❌ [Tooltips] No #info-tt element found.");

    // Prevent double-binding if called by both auto-init and app.js
    if (window._cmTtBound) return;
    window._cmTtBound = true;

    console.log("✅ [Tooltips] System initialized and listening on document.");

    // Bind to document instead of document.body to ensure we catch everything
    document.addEventListener('mouseover', (e) => {
        const el = e.target.closest('.info-hover');
        if (!el) return; // Silent return for non-tooltip elements
        
        const key = el.getAttribute('data-key');
        if (!key) {
            const tempTt = el.getAttribute('data-tt-temp');
            if (tempTt) {
                // Safely replace newlines in the tooltip text
                infoTtEl.innerHTML = tempTt.replace(/\n/g, '<br>');
                const rect = el.getBoundingClientRect();
                infoTtEl.style.left = (rect.left + rect.width / 2) + 'px';
                
        let calculatedTop = rect.top - 8;
        if (rect.top < 50) { 
            // If too close to top of viewport, render below the element instead
            calculatedTop = rect.bottom + window.scrollY + 16;
            infoTtEl.style.transform = 'translate(-50%, 0)'; // Remove upward translation
        } else {
            infoTtEl.style.transform = 'translate(-50%, -100%)'; // Standard upward translation
        }
        infoTtEl.style.top = calculatedTop + 'px';

                infoTtEl.classList.add('visible');
            }
            return;
        }

        let explanation = CM_EXPLANATIONS[key];
        
        // Dynamic Resolution for Axis acronyms
        if (!explanation && key.startsWith('axis_')) {
            const payloadEl = document.getElementById('cm-page-payload');
            if (payloadEl) {
                try {
                    const data = JSON.parse(payloadEl.textContent);
                    const rawRubric = new URLSearchParams(window.location.search).get("rubric") || data.default_rubric || "unknown";
                    const activeRubric = rawRubric.replace('_mock', '').toLowerCase();
                    const meta = data.rubrics_meta || {};
                    
                    // Fuzzy match rubric key
                    const matchedKey = Object.keys(meta).find(k => k.toLowerCase() === activeRubric);
                    const rMeta = meta[matchedKey] || { overlays: {} };
                    
                    const axisLetter = key.split('_')[1];
                    let overlay = null;
                    for (let ok in rMeta.overlays) {
                        if (ok.toLowerCase() === (axisLetter || '').toLowerCase()) overlay = rMeta.overlays[ok];
                    }
                    explanation = overlay || `Explanation missing for ${axisLetter}`;
                } catch (err) {
                    console.error("❌ [Tooltips] JSON parse error on payload", err);
                }
            }
        }
        
        if (!explanation) {
            console.warn(`⚠️ [Tooltips] Dictionary miss for key: ${key}`);
            explanation = `[DEV] Missing dictionary definition for: ${key}`;
        }
        
        infoTtEl.innerHTML = explanation.replace(/\n/g, '<br>');
        
        const rect = el.getBoundingClientRect();
        infoTtEl.style.left = (rect.left + rect.width / 2) + 'px';
        
        let calculatedTop = rect.top - 8;
        if (rect.top < 50) { 
            // If too close to top of viewport, render below the element instead
            calculatedTop = rect.bottom + window.scrollY + 16;
            infoTtEl.style.transform = 'translate(-50%, 0)'; // Remove upward translation
        } else {
            infoTtEl.style.transform = 'translate(-50%, -100%)'; // Standard upward translation
        }
        infoTtEl.style.top = calculatedTop + 'px';

        infoTtEl.classList.add('visible');
    });

    document.addEventListener('mouseout', (e) => {
        if (!e.target.closest('.info-hover')) return;
        infoTtEl.classList.remove('visible');
    });
}

// Ensure execution if imported independently
if (!window._cmTooltipsAutoInit) {
    window._cmTooltipsAutoInit = true;
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initGlobalTooltips);
    } else {
        initGlobalTooltips();
    }
}
