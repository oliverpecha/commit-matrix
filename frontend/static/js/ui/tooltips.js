
import { getRevolvingTierCardHTML } from './revolvingButton.js?v=0.1.427';

import { CM_EXPLANATIONS } from '../constants/explanations.js?v=0.1.427';

export function initGlobalTooltips() {
    const infoTtEl = document.getElementById('info-tt');
    if (!infoTtEl) return;

    document.addEventListener('mouseover', (e) => {
        const target = e.target.closest('.info-hover');
        if (target) {
            if (target.id === 'cm-tier-cycle-btn' || target.id === 'cm-global-chron-btn' || target.matches('button[data-action="cycleAvg"]') || target.matches('button[data-action="toggleGlobalChron"]')) return;
            window._cmHoverTarget = target;
            const key = target.getAttribute('data-key');
            let explanation = '';
            if (key === 'tierDistCycle') {
                explanation = getRevolvingTierCardHTML();
            } else if (typeof CM_EXPLANATIONS !== 'undefined' && CM_EXPLANATIONS[key]) {
                explanation = CM_EXPLANATIONS[key];
            } else {
                explanation = target.getAttribute('data-info');
            }
            
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
            
            if (explanation && explanation.startsWith('<div')) {
                infoTtEl.innerHTML = explanation;
            } else {
                infoTtEl.innerHTML = (explanation || 'Explanation missing').replace(/\n/g, '<br>');
            }
            
                        const rect = target.getBoundingClientRect();
            const isPillBtn = target.classList.contains('cm-pill-btn') || target.closest('.cm-card-hd');

            // Default offset below and to the right
            const cursorOffsetX = 12;
            const cursorOffsetY = 12;

            infoTtEl.style.transform = `translate(0px, 0px)`;
            infoTtEl.style.pointerEvents = 'none';

            if (isPillBtn) {
                // Pin directly below the button, clearing its bottom edge completely
                infoTtEl.style.left = (rect.left + cursorOffsetX) + 'px';
                infoTtEl.style.top = (rect.bottom + cursorOffsetY) + 'px';
            } else {
                // Follow cursor for text/kpi hovers
                infoTtEl.style.left = (e.clientX + cursorOffsetX) + 'px';
                infoTtEl.style.top = (e.clientY + cursorOffsetY) + 'px';
            }

            infoTtEl.classList.add('visible');

            // Exact Dual-Axis Viewport Clamping matching chart tooltip in plugins.js
            requestAnimationFrame(() => {
                const ttRect = infoTtEl.getBoundingClientRect();
                let shiftX = 0;
                let shiftY = 0;

                if (ttRect.left < 10) {
                    shiftX = 10 - ttRect.left;
                } else if (ttRect.right > window.innerWidth - 10) {
                    shiftX = window.innerWidth - 10 - ttRect.right;
                }

                if (ttRect.top < 10) {
                    shiftY = 10 - ttRect.top;
                } else if (ttRect.bottom > window.innerHeight - 10) {
                    shiftY = window.innerHeight - 10 - ttRect.bottom;
                }

                if (shiftX !== 0 || shiftY !== 0) {
                    infoTtEl.style.transform = `translate(${shiftX}px, ${shiftY}px)`;
                }
            });
        }
    });

    document.addEventListener('mouseout', (e) => {
        const target = e.target.closest('.info-hover');
        if (target) {
            if (target.id === 'cm-tier-cycle-btn' || target.id === 'cm-global-chron-btn' || target.matches('button[data-action="cycleAvg"]') || target.matches('button[data-action="toggleGlobalChron"]')) return;
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
                if (window._cmHoverTarget && (window._cmHoverTarget.id === 'cm-tier-cycle-btn' || window._cmHoverTarget.id === 'cm-global-chron-btn' || window._cmHoverTarget.matches('button[data-action="cycleAvg"]') || window._cmHoverTarget.matches('button[data-action="toggleGlobalChron"]'))) {
                    // Handled exclusively by revolvingButton.js
                } else if (!window._cmHoverTarget || !document.body.contains(window._cmHoverTarget)) {
                    infoTtEl.classList.remove('visible');
                    window._cmHoverTarget = null;
                }
            }
        }, 150);
    }
}
