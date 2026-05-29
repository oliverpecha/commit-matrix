import { BEO_EXPLANATIONS } from '../core/constants.js';

export function initGlobalTooltips() {
    const infoTtEl = document.getElementById('info-tt');
    if (!infoTtEl) return;

    document.querySelectorAll('.info-hover').forEach(el => {
        el.addEventListener('mouseenter', () => {
            const key = el.getAttribute('data-key');
            infoTtEl.textContent = BEO_EXPLANATIONS[key] || 'Explanation missing';
            const rect = el.getBoundingClientRect();
            infoTtEl.style.left = (rect.left + rect.width / 2) + 'px';
            infoTtEl.style.top = (rect.top - 8) + 'px';
            infoTtEl.classList.add('visible');
        });
        el.addEventListener('mouseleave', () => infoTtEl.classList.remove('visible'));
    });
}
