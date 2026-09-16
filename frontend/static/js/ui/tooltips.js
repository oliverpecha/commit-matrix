import { CM_EXPLANATIONS } from '../constants/explanations.js?v=0.1.324';

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
            const isGraph = target.tagName.toLowerCase() === 'rect' || target.closest('svg');
            
            let transX = '-50%';
            let transY = '-100%';
            
            if (isGraph) {
                // Mimic Chart.js behavior (bottom-right offset from cursor)
                const cursorOffsetX = 12;
                const cursorOffsetY = 12;
                infoTtEl.style.left = (e.clientX + cursorOffsetX) + 'px';
                infoTtEl.style.top = (e.clientY + cursorOffsetY) + 'px';
                transX = '0px';
                transY = '0px';
            } else {
                // UI Elements: Anchor to element bounds
                infoTtEl.style.left = (rect.left + rect.width / 2) + 'px';
                let calculatedTop = rect.top - 8;
                if (rect.top < 50) { 
                    calculatedTop = rect.bottom + 16; // Removed buggy scrollY math on fixed element
                    transY = '0px'; 
                }
                infoTtEl.style.top = calculatedTop + 'px';
            }

            infoTtEl.style.transform = `translate(${transX}, ${transY})`;
            infoTtEl.classList.add('visible');

            // Apply dual-axis viewport clamping
            requestAnimationFrame(() => {
                const ttRect = infoTtEl.getBoundingClientRect();
                let shiftX = 0;
                let shiftY = 0;

                if (ttRect.left < 10) shiftX = 10 - ttRect.left;
                else if (ttRect.right > window.innerWidth - 10) shiftX = window.innerWidth - 10 - ttRect.right;

                if (ttRect.top < 10) shiftY = 10 - ttRect.top;
                else if (ttRect.bottom > window.innerHeight - 10) shiftY = window.innerHeight - 10 - ttRect.bottom;

                if (shiftX !== 0 || shiftY !== 0) {
                    infoTtEl.style.transform = `translate(calc(${transX} + ${shiftX}px), calc(${transY} + ${shiftY}px))`;
                }
            });
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
