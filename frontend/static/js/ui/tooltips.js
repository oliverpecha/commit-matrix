import { CM_EXPLANATIONS } from '../constants/explanations.js?v=0.1.188';

export function initGlobalTooltips() {
    const infoTtEl = document.getElementById('info-tt');
    if (!infoTtEl) return;

    document.body.addEventListener('mouseover', (e) => {
        const el = e.target.closest('.info-hover');
        if (!el) return;
        const key = el.getAttribute('data-key');
        infoTtEl.textContent = CM_EXPLANATIONS[key] || 'Explanation missing';
        
        const rect = el.getBoundingClientRect();
        infoTtEl.style.left = (rect.left + rect.width / 2) + 'px';
        infoTtEl.style.top = (rect.top - 8) + 'px';
        infoTtEl.classList.add('visible');
    });

    document.body.addEventListener('mouseout', (e) => {
        const el = e.target.closest('.info-hover');
        if (!el) return;
        infoTtEl.classList.remove('visible');
    });
}
