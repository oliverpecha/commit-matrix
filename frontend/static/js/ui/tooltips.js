import { CM_EXPLANATIONS } from '../constants/explanations.js?v=0.1.234';

export function initGlobalTooltips() {
    const infoTtEl = document.getElementById('info-tt');
    if (!infoTtEl) return;

    document.addEventListener('mouseover', (e) => {
        const target = e.target.closest('.info-hover');
        if (target) {
            window._cmHoverTarget = target;
            const key = target.getAttribute('data-key');
            let explanation = (typeof CM_EXPLANATIONS !== 'undefined' && CM_EXPLANATIONS[key]) ? CM_EXPLANATIONS[key] : target.getAttribute('data-info');
            
            if (!explanation && key && key.startsWith('axis_')) {
                const payloadEl = document.getElementById('cm-page-payload');
                if (payloadEl) {
                    try {
                        const data = JSON.parse(payloadEl.textContent);
                        const rawRubric = new URLSearchParams(window.location.search).get("rubric") || data.default_rubric || "unknown";
                        const activeRubric = rawRubric.replace('_mock', '').toLowerCase();
                        const meta = data.rubrics_meta || {};
                        const matchedKey = Object.keys(meta).find(k => k.toLowerCase() === activeRubric);
                        const rMeta = matchedKey ? meta[matchedKey] : { overlays: {} };
                        const axisLetter = key.split('_')[1];
                        for (let ok in rMeta.overlays) {
                            if (ok.toLowerCase() === (axisLetter || '').toLowerCase()) explanation = rMeta.overlays[ok];
                        }
                    } catch(err) {}
                }
            }
            
            infoTtEl.innerHTML = (explanation || 'Explanation missing').replace(/\n/g, '<br>');
            
            const rect = target.getBoundingClientRect();
            infoTtEl.style.left = (rect.left + rect.width / 2) + 'px';
            
            let calculatedTop = rect.top - 8;
            if (rect.top < 50) { 
                calculatedTop = rect.bottom + window.scrollY + 16;
                infoTtEl.style.transform = 'translate(-50%, 0)'; 
            } else {
                infoTtEl.style.transform = 'translate(-50%, -100%)'; 
            }
            infoTtEl.style.top = calculatedTop + 'px';
            infoTtEl.classList.add('visible');
        }
    });

    document.addEventListener('mouseout', (e) => {
        if (e.target.closest('.info-hover')) {
            infoTtEl.classList.remove('visible');
            window._cmHoverTarget = null;
        }
    });

    if (!window._infoTtWatchdog) {
        window._infoTtWatchdog = true;
        setInterval(() => {
            const cmTt = document.getElementById('cm-tt');
            if (cmTt && cmTt.classList.contains('visible')) {
                // Bulletproof Chart.js Ghost Clear: If no canvas is physically hovered, kill the tooltip
                if (document.querySelector('canvas:hover') !== window._cmActiveChartCanvas) {
                    cmTt.classList.remove('visible');
                }
            }

            if (infoTtEl && infoTtEl.classList.contains('visible')) {
                // Bulletproof Ghost Clear: If the exact element that triggered the tooltip is removed from the DOM, kill it.
                if (!window._cmHoverTarget || !document.body.contains(window._cmHoverTarget)) {
                    infoTtEl.classList.remove('visible');
                    window._cmHoverTarget = null;
                }
            }
        }, 150);
    }
}
