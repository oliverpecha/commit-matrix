import { TIER_DISTRIBUTIONS, TIER_DISTRIBUTION_MAP } from '../constants/tiers.js?v=0.1.436';
import { UI_STATE } from '../core/state.js?v=0.1.436';
import { processCommits, filterByDateBounds } from '../core/dataEngine.js?v=0.1.436';
import { renderTierChart, renderTrendChart, renderStackChart, renderConvergenceChart, renderTypesChart, renderFragChart, renderChurnChart, renderBlastChart, renderRiskCharts } from '../charts/chartCtrl.js?v=0.1.436';

const REVOLVE_ICON_SVG = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="display:inline-block; vertical-align:-1px; margin-right:6px;"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/></svg>`;
const PILL_ICON_SVG = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:inline-block; vertical-align:-1px; margin-right:2px;"><path d="M21.21 15.89A10 10 0 1 1 8 2.83"></path><path d="M22 12A10 10 0 0 0 12 2v10z"></path></svg>`;
const AVG_ICON_SVG = `<svg width="14" height="14" viewBox="0 0 32 32" fill="currentColor" style="display:inline-block; vertical-align:-2px; margin-right:4px;"><path d="M23,24c-3.5991,0-5.0293-4.1758-6.4126-8.2139C15.2764,11.9583,13.92,8,11,8a3.44,3.44,0,0,0-3.0532,2.3215L6.0513,9.6838C6.1016,9.5334,7.3218,6,11,6c4.3491,0,6.0122,4.8547,7.48,9.1379C19.6885,18.6667,20.83,22,23,22a3.44,3.44,0,0,0,3.0532-2.3215l1.8955.6377C27.8984,20.4666,26.6782,24,23,24Z"/><path d="M4,28V17H6V15H4V2H2V28a2,2,0,0,0,2,2H30V28Z"/><rect x="8" y="15" width="2" height="2"/><rect x="12" y="15" width="2" height="2"/><rect x="20" y="15" width="2" height="2"/><rect x="24" y="15" width="2" height="2"/><rect x="28" y="15" width="2" height="2"/></svg>`;

export const CHRON_MODES = [
    {
        id: 'timeline',
        isChron: true,
        name: 'Timeline',
        desc: 'Calendar date-spaced axis',
        formula: 't = commit.ts',
        sparkline: `<svg width="38" height="14" viewBox="0 0 38 14" fill="none"><line x1="2" y1="7" x2="36" y2="7" stroke="currentColor" stroke-width="1.2" opacity="0.4"/><circle cx="4" cy="7" r="1.3" fill="currentColor"/><circle cx="11" cy="7" r="1.9" fill="currentColor"/><circle cx="23" cy="7" r="1.3" fill="currentColor"/><circle cx="34" cy="7" r="2.1" fill="currentColor"/></svg>`
    },
    {
        id: 'index',
        isChron: false,
        name: 'Index',
        desc: 'Evenly spaced sequential commits',
        formula: 'i = commit.idx',
        sparkline: `<svg width="38" height="14" viewBox="0 0 38 14" fill="none"><rect x="3" y="3" width="3" height="8" rx="1" fill="currentColor" opacity="0.6"/><rect x="11" y="2" width="3" height="9" rx="1" fill="currentColor"/><rect x="19" y="5" width="3" height="6" rx="1" fill="currentColor" opacity="0.7"/><rect x="27" y="1" width="3" height="10" rx="1" fill="currentColor"/><rect x="34" y="4" width="2" height="7" rx="1" fill="currentColor" opacity="0.5"/></svg>`
    }
];

const TIMELINE_ICON_SVG = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="display:inline-block; vertical-align:-2px; margin-right:4px;"><circle cx="5" cy="12" r="4"/><path d="M5 9v3h1.5M9 12h1.5M13.5 12h1M17.5 12h3"/><circle cx="12" cy="12" r="1.5"/><circle cx="16" cy="12" r="1.5"/><circle cx="22" cy="12" r="1.5"/></svg>`;
const INDEX_ICON_SVG = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="display:inline-block; vertical-align:-2px; margin-right:4px;"><path d="M2 18h2M8 18h2M14 18h2M20 18h2"/><circle cx="6" cy="18" r="2"/><circle cx="12" cy="18" r="2"/><circle cx="18" cy="18" r="2"/><rect x="4" y="4" width="4" height="10" rx="2"/><rect x="10" y="4" width="4" height="10" rx="2"/><rect x="16" y="4" width="4" height="10" rx="2"/></svg>`;

export function getRevolvingChronCardHTML() {
    const isChron = (typeof UI_STATE !== 'undefined' && UI_STATE.globalChron !== undefined) ? !!UI_STATE.globalChron : true;
    const activeMode = CHRON_MODES.find(m => m.isChron === isChron) || CHRON_MODES[0];
    const nextMode = CHRON_MODES.find(m => m.isChron !== isChron) || CHRON_MODES[1];

    const ordered = [nextMode, activeMode];

    let h = `<div style="font-family:'Satoshi',sans-serif; min-width:260px;">`;
    h += `<div style="display:flex; align-items:center; margin-bottom:8px; padding-bottom:6px; border-bottom:1px solid rgba(255,255,255,0.08);">
            ${REVOLVE_ICON_SVG}
            <span style="font-size:11px; font-weight:700; color:#f0eee6; letter-spacing:0.3px;">Switch to</span>
          </div>`;

    h += `<div id="cm-chron-slots" style="display:flex; flex-direction:column; gap:5px;">`;

    ordered.forEach((r) => {
        const isActive = r.id === activeMode.id;
        const isNext = r.id === nextMode.id;

        const bgRow = isNext ? 'rgba(255,255,255,0.08)' : 'transparent';
        const borderRow = isNext ? 'rgba(255,255,255,0.22)' : 'transparent';
        const titleColor = isNext ? '#ffffff' : '#9c9a95';
        const sparklineColor = isNext ? '#ffffff' : (isActive ? '#36B8D8' : '#6F8197');

        h += `<div class="cm-chron-card-row" data-id="${r.id}" style="padding:5px 8px; border-radius:6px; background:${bgRow}; border:1px solid ${borderRow}; transition:transform 0.28s cubic-bezier(0.2, 0.8, 0.2, 1), background 0.2s ease, border-color 0.2s ease; will-change:transform;">`;
        h += `<div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:3px;">
                <div style="display:flex; align-items:center; gap:6px;">
                    <span style="font-size:11px; font-weight:${isNext ? 700 : 500}; color:${titleColor};">${r.name}</span>
                    ${isActive ? `<span style="font-size:9.5px; padding:1px 5px; border-radius:3px; background:#36B8D822; color:#36B8D8; font-family:monospace; font-weight:700;">ACTIVE</span>` : ''}
                </div>
                <div style="color:${sparklineColor}; display:flex; align-items:center;">
                    ${r.sparkline}
                </div>
              </div>`;

        h += `<div style="display:flex; justify-content:space-between; align-items:center; font-size:9.5px; color:#7a7874; font-family:monospace;">
                <span>${r.desc}</span>
                <span style="opacity:0.8; font-size:9px;">${r.formula}</span>
              </div>`;
        h += `</div>`;
    });

    h += `</div></div>`;
    return h;
}

export const AVG_MODES = [
    {
        id: 0,
        key: 'off',
        name: 'Off',
        desc: 'Raw scatter points only',
        formula: 'y = null',
        sparkline: `<svg width="38" height="14" viewBox="0 0 38 14" fill="none"><line x1="2" y1="7" x2="36" y2="7" stroke="currentColor" stroke-width="1.2" stroke-dasharray="2 3" opacity="0.4"/><circle cx="7" cy="4" r="1.3" fill="currentColor" opacity="0.6"/><circle cx="18" cy="10" r="1.3" fill="currentColor" opacity="0.6"/><circle cx="29" cy="5" r="1.3" fill="currentColor" opacity="0.6"/></svg>`
    },
    {
        id: 1,
        key: 'trailing',
        name: 'Trailing',
        desc: 'Simple moving window average',
        formula: 'avg(w=5)',
        sparkline: `<svg width="38" height="14" viewBox="0 0 38 14" fill="none"><path d="M2 11 C 10 11, 14 3, 20 6 C 26 9, 30 2, 36 3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>`
    },
    {
        id: 2,
        key: 'daily_peak',
        name: 'Daily Peak',
        desc: 'Max score per day',
        formula: 'max(scores[day])',
        sparkline: `<svg width="38" height="14" viewBox="0 0 38 14" fill="none"><path d="M2 12 L 8 12 L 12 2 L 18 9 L 24 2 L 29 10 L 33 4 L 36 10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`
    },
    {
        id: 3,
        key: 'daily_median',
        name: 'Daily Median',
        desc: '50th percentile per day',
        formula: 'p50(day)',
        sparkline: `<svg width="38" height="14" viewBox="0 0 38 14" fill="none"><path d="M2 8 Q 11 4 20 8 T 36 7" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>`
    },
    {
        id: 4,
        key: 'vol_weighted',
        name: 'Vol-Weighted',
        desc: 'Weighted by churn line volume',
        formula: 'Σ(s·v) / Σv',
        sparkline: `<svg width="38" height="14" viewBox="0 0 38 14" fill="none"><path d="M2 11 L 10 10 L 15 13 L 20 2 L 26 12 L 31 6 L 36 9" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>`
    },
    {
        id: 5,
        key: 'high_water',
        name: 'High-Water',
        desc: 'Non-decreasing ceiling mark',
        formula: 'max(peak[0..t])',
        sparkline: `<svg width="38" height="14" viewBox="0 0 38 14" fill="none"><path d="M2 12 L 10 12 L 10 8 L 22 8 L 22 4 L 30 4 L 30 2 L 36 2" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`
    }
];

export function getNextAvgMode(currentIdx) {
    return (currentIdx + 1) % AVG_MODES.length;
}

export function getActiveAvgMode(target = 'trend') {
    const avgKey = target === 'trend' ? 'avgTrend' : 'avg' + target.charAt(0).toUpperCase() + target.slice(1);
    const modeIdx = (typeof UI_STATE !== 'undefined' && UI_STATE[avgKey] !== undefined) ? UI_STATE[avgKey] : 2;
    return AVG_MODES[modeIdx] || AVG_MODES[2];
}

export function getRevolvingAvgCardHTML(target = 'trend') {
    const avgKey = target === 'trend' ? 'avgTrend' : 'avg' + target.charAt(0).toUpperCase() + target.slice(1);
    const activeIdx = (typeof UI_STATE !== 'undefined' && UI_STATE[avgKey] !== undefined) ? UI_STATE[avgKey] : 2;
    const nextIdx = getNextAvgMode(activeIdx);

    const middleModes = [];
    for (let step = 2; step < AVG_MODES.length; step++) {
        const midIdx = (activeIdx + step) % AVG_MODES.length;
        middleModes.push(AVG_MODES[midIdx]);
    }

    const orderedModes = [AVG_MODES[nextIdx], ...middleModes, AVG_MODES[activeIdx]].filter(Boolean);

    let h = `<div style="font-family:'Satoshi',sans-serif; min-width:280px;">`;
    h += `<div style="display:flex; align-items:center; margin-bottom:8px; padding-bottom:6px; border-bottom:1px solid rgba(255,255,255,0.08);">
            ${REVOLVE_ICON_SVG}
            <span style="font-size:11px; font-weight:700; color:#f0eee6; letter-spacing:0.3px;">Switch to</span>
          </div>`;

    h += `<div id="cm-avg-slots" style="display:flex; flex-direction:column; gap:5px;">`;

    orderedModes.forEach((r) => {
        const isActive = r.id === activeIdx;
        const isNext = r.id === nextIdx;

        const bgRow = isNext ? 'rgba(255,255,255,0.08)' : 'transparent';
        const borderRow = isNext ? 'rgba(255,255,255,0.22)' : 'transparent';
        const titleColor = isNext ? '#ffffff' : '#9c9a95';
        const sparklineColor = isNext ? '#ffffff' : (isActive ? '#36B8D8' : '#6F8197');

        h += `<div class="cm-avg-card-row" data-id="${r.id}" style="padding:5px 8px; border-radius:6px; background:${bgRow}; border:1px solid ${borderRow}; transition:transform 0.28s cubic-bezier(0.2, 0.8, 0.2, 1), background 0.2s ease, border-color 0.2s ease; will-change:transform;">`;
        h += `<div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:3px;">
                <div style="display:flex; align-items:center; gap:6px;">
                    <span style="font-size:11px; font-weight:${isNext ? 700 : 500}; color:${titleColor};">${r.name}</span>
                    ${isActive ? `<span style="font-size:9.5px; padding:1px 5px; border-radius:3px; background:#36B8D822; color:#36B8D8; font-family:monospace; font-weight:700;">ACTIVE</span>` : ''}
                </div>
                <div style="color:${sparklineColor}; display:flex; align-items:center;">
                    ${r.sparkline}
                </div>
              </div>`;

        h += `<div style="display:flex; justify-content:space-between; align-items:center; font-size:9.5px; color:#7a7874; font-family:monospace;">
                <span>${r.desc}</span>
                <span style="opacity:0.8; font-size:9px;">${r.formula}</span>
              </div>`;
        h += `</div>`;
    });

    h += `</div></div>`;
    return h;
}

const PROFILES = [
    {
        id: 'tight_floor',
        name: 'Tight Floor',
        minor: '< 7',
        core: '7 – 13.9',
        pivotal: '≥ 14',
        pctMinor: 18.75, // 3/16
        pctCore: 43.75,  // 7/16
        pctPiv: 37.5     // 6/16
    },
    {
        id: 'high_bar',
        name: 'High Bar',
        minor: '< 8',
        core: '8 – 14.9',
        pivotal: '≥ 15',
        pctMinor: 25.0,  // 4/16
        pctCore: 43.75,  // 7/16
        pctPiv: 31.25    // 5/16
    },
    {
        id: 'asymmetric',
        name: 'Asymmetric',
        minor: '< 6.5',
        core: '6.5 – 12.9',
        pivotal: '≥ 13',
        pctMinor: 15.6,  // 2.5/16
        pctCore: 40.6,   // 6.5/16
        pctPiv: 43.8     // 7/16
    }
];

export function getNextDist(activeId) {
    const idx = TIER_DISTRIBUTIONS.findIndex(d => d.id === activeId);
    const nextIdx = (idx + 1) % TIER_DISTRIBUTIONS.length;
    return TIER_DISTRIBUTIONS[nextIdx];
}

export function getActiveDist() {
    const activeId = (typeof UI_STATE !== 'undefined' && UI_STATE.tierDistribution) ? UI_STATE.tierDistribution : 'tight_floor';
    return TIER_DISTRIBUTION_MAP[activeId] || TIER_DISTRIBUTIONS[0];
}

export function getRevolvingTierCardHTML() {
    const activeId = (typeof UI_STATE !== 'undefined' && UI_STATE.tierDistribution) ? UI_STATE.tierDistribution : 'tight_floor';
    const nextDist = getNextDist(activeId);

    // Dynamic slot ordering:
    // Slot 1 (Top): Upcoming tier (nextDist)
    // Slot 2 (Middle): Other tiers
    // Slot 3 (Bottom): Active tier
    const topProfile = PROFILES.find(p => p.id === nextDist.id);
    const bottomProfile = PROFILES.find(p => p.id === activeId);
    const middleProfiles = PROFILES.filter(p => p.id !== nextDist.id && p.id !== activeId);

    const orderedProfiles = [topProfile, ...middleProfiles, bottomProfile].filter(Boolean);

    let h = `<div style="font-family:'Satoshi',sans-serif; min-width:260px;">`;
    h += `<div style="display:flex; align-items:center; margin-bottom:8px; padding-bottom:6px; border-bottom:1px solid rgba(255,255,255,0.08);">
            ${REVOLVE_ICON_SVG}
            <span style="font-size:11px; font-weight:700; color:#f0eee6; letter-spacing:0.3px;">Switch to</span>
          </div>`;

    h += `<div id="cm-tier-slots" style="display:flex; flex-direction:column; gap:6px;">`;

    orderedProfiles.forEach((r, idx) => {
        const isActive = r.id === activeId;
        const isNext = r.id === nextDist.id;

        const bgRow = isNext ? 'rgba(255,255,255,0.08)' : 'transparent';
        const borderRow = isNext ? 'rgba(255,255,255,0.22)' : 'transparent';
        const titleColor = isNext ? '#ffffff' : '#9c9a95';

        h += `<div class="cm-tier-card-row" data-id="${r.id}" style="padding:5px 8px; border-radius:6px; background:${bgRow}; border:1px solid ${borderRow}; transition:transform 0.25s cubic-bezier(0.2, 0.8, 0.2, 1), background 0.2s ease, border-color 0.2s ease; will-change:transform;">`;
        h += `<div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:4px;">
                <span style="font-size:11px; font-weight:${isNext ? 700 : 500}; color:${titleColor};">${r.name}</span>
                ${isActive ? `<span style="font-size:9.5px; padding:1px 5px; border-radius:3px; background:#36B8D822; color:#36B8D8; font-family:monospace; font-weight:700;">ACTIVE</span>` : ''}
              </div>`;

        // Segmented Range Bar
        h += `<div style="height:6px; border-radius:3px; overflow:hidden; display:flex; gap:1.5px; background:rgba(255,255,255,0.03); margin-bottom:3px;">
                <div style="width:${r.pctMinor}%; background:#6F8197; border-radius:2px 0 0 2px;" title="Minor: ${r.minor}"></div>
                <div style="width:${r.pctCore}%; background:#36B8D8;" title="Core: ${r.core}"></div>
                <div style="width:${r.pctPiv}%; background:#D43BC6; border-radius:0 2px 2px 0;" title="Pivotal: ${r.pivotal}"></div>
              </div>`;

        // Range Legend
        h += `<div style="display:flex; justify-content:space-between; font-size:9px; color:#7a7874; font-family:monospace;">
                <span style="color:#8c9ba8;">Min ${r.minor}</span>
                <span style="color:#56cbe8;">Core ${r.core}</span>
                <span style="color:#e85fda;">Piv ${r.pivotal}</span>
              </div>`;
        h += `</div>`;
    });

    h += `</div></div>`;
    return h;
}

function positionRevolvingCard(btn, infoTtEl) {
    // Exactly matches the standardized anchor positioning from the baseline button
    infoTtEl.style.pointerEvents = 'none';
    infoTtEl.style.transform = 'translate(0px, 0px)';

    const rect = btn.getBoundingClientRect();
    const cursorOffsetY = 8;

    // Align card flush with the left margin of the anchor pill button
    infoTtEl.style.left = rect.left + 'px';
    infoTtEl.style.top = (rect.bottom + cursorOffsetY) + 'px';
    infoTtEl.classList.add('visible');

    // Horizontal viewport clamping only - never push vertically over the button
    requestAnimationFrame(() => {
        const ttRect = infoTtEl.getBoundingClientRect();
        let shiftX = 0;
        if (ttRect.left < 10) {
            shiftX = 10 - ttRect.left;
        } else if (ttRect.right > window.innerWidth - 10) {
            shiftX = window.innerWidth - 10 - ttRect.right;
        }
        if (shiftX !== 0) {
            infoTtEl.style.transform = `translate(${shiftX}px, 0px)`;
        }
    });
}

export function initTierDistributionRevolving() {
    const btn = document.getElementById('cm-tier-cycle-btn');
    const infoTtEl = document.getElementById('info-tt');
    if (!btn || btn.__cmBound) return;
    btn.__cmBound = true;

    function renderLabel(text) {
        const lbl = btn.querySelector('#cm-tier-cycle-label');
        if (lbl) {
            lbl.textContent = text;
        } else {
            btn.innerHTML = `${PILL_ICON_SVG} <span id="cm-tier-cycle-label">${text}</span>`;
        }
    }

    function isCursorOverButton(e) {
        if (!e || e.clientX === undefined) return btn.matches(':hover');
        const rect = btn.getBoundingClientRect();
        return (
            e.clientX >= rect.left &&
            e.clientX <= rect.right &&
            e.clientY >= rect.top &&
            e.clientY <= rect.bottom
        );
    }

    function showCard() {
        if (!infoTtEl) return;
        window._cmHoverTarget = btn;
        btn.dataset.isHovered = 'true';
        infoTtEl.innerHTML = getRevolvingTierCardHTML();
        positionRevolvingCard(btn, infoTtEl);
    }

    function syncHoverPreview() {
        // Pill displays the ACTIVE tier string when hovered
        renderLabel(getActiveDist().label);
        showCard();
    }

    function syncActiveDisplay() {
        btn.dataset.isHovered = 'false';
        renderLabel(getActiveDist().label);
        if (infoTtEl && window._cmHoverTarget === btn) {
            infoTtEl.classList.remove('visible');
            window._cmHoverTarget = null;
        }
    }

    btn.addEventListener('mouseenter', () => {
        syncHoverPreview();
    });

    btn.addEventListener('mouseleave', (e) => {
        if (isCursorOverButton(e)) return;
        syncActiveDisplay();
    });

    btn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();

        // 1. Capture previous positions of rows for FLIP animation
        const prevRects = new Map();
        if (infoTtEl && infoTtEl.classList.contains('visible')) {
            infoTtEl.querySelectorAll('.cm-tier-card-row').forEach(row => {
                const id = row.getAttribute('data-id');
                if (id) prevRects.set(id, row.getBoundingClientRect().top);
            });
        }

        // 2. Advance tier
        const nextDist = getNextDist(UI_STATE.tierDistribution || 'tight_floor');
        UI_STATE.tierDistribution = nextDist.id;

        // 3. Update pill string to the newly active tier and update card
        syncHoverPreview();

        // 4. Apply smooth FLIP transition on card rows
        if (prevRects.size > 0 && infoTtEl) {
            infoTtEl.querySelectorAll('.cm-tier-card-row').forEach(row => {
                const id = row.getAttribute('data-id');
                const oldTop = prevRects.get(id);
                if (oldTop !== undefined) {
                    const newTop = row.getBoundingClientRect().top;
                    const deltaY = oldTop - newTop;
                    if (deltaY !== 0) {
                        row.style.transition = 'none';
                        row.style.transform = `translateY(${deltaY}px)`;
                        requestAnimationFrame(() => {
                            row.style.transition = 'transform 0.28s cubic-bezier(0.2, 0.8, 0.2, 1), background 0.2s ease, border-color 0.2s ease';
                            row.style.transform = 'translateY(0px)';
                        });
                    }
                }
            });
        }

        // 5. Invalidate raw payloads & recompute tier assignments for tooltips
        const sourceData = window.MATRIX_PAYLOAD_RAW || window.MATRIX_CHART_PAYLOAD || window.MATRIX_PAYLOAD || [];
        let p = [];
        try {
            p = processCommits(sourceData);
        } catch (err) {}

        const df = UI_STATE.dateFilter || { start: null, end: null, label: 'All history', mode: 'preset' };
        let filteredP = (df.mode === 'incoming' && UI_STATE.incomingBaselineIds)
            ? p.filter(c => !UI_STATE.incomingBaselineIds.has(c.h || c.hash))
            : filterByDateBounds(p, df.start, df.end);

        window.CM_CURRENT_FILTERED_PAYLOAD = filteredP;

        // 6. Update KPIs (counters and color badges)
        if (typeof window.paintKPIs === 'function' && typeof window.computeKPIs === 'function') {
            window.paintKPIs(window.computeKPIs(filteredP));
        }

        // 7. Selectively redraw ONLY the 2 charts that visually represent tier distribution
        renderTierChart(filteredP);
        renderTrendChart(filteredP);
    });

    syncActiveDisplay();
}

export function initAvgSmoothingRevolving() {
    const buttons = document.querySelectorAll('button[data-action="cycleAvg"]');
    const infoTtEl = document.getElementById('info-tt');
    if (!buttons.length) return;

    buttons.forEach(btn => {
        if (btn.__cmAvgBound) return;
        btn.__cmAvgBound = true;

        const target = btn.getAttribute('data-target') || 'trend';
        const avgKey = target === 'trend' ? 'avgTrend' : 'avg' + target.charAt(0).toUpperCase() + target.slice(1);

        function renderLabel(text) {
            const lbl = btn.querySelector('.cm-avg-label');
            if (lbl) {
                lbl.textContent = text;
            } else {
                btn.innerHTML = `${AVG_ICON_SVG} <span class="cm-avg-label">${text}</span>`;
            }
            const activeMode = getActiveAvgMode(target);
            btn.classList.toggle('active', activeMode.id !== 0);
        }

        function isCursorOverButton(e) {
            if (!e || e.clientX === undefined) return btn.matches(':hover');
            const rect = btn.getBoundingClientRect();
            return (
                e.clientX >= rect.left &&
                e.clientX <= rect.right &&
                e.clientY >= rect.top &&
                e.clientY <= rect.bottom
            );
        }

        function showCard() {
            if (!infoTtEl) return;
            window._cmHoverTarget = btn;
            btn.dataset.isHovered = 'true';
            infoTtEl.innerHTML = getRevolvingAvgCardHTML(target);
            positionRevolvingCard(btn, infoTtEl);
        }

        function syncHoverPreview() {
            renderLabel(getActiveAvgMode(target).name);
            showCard();
        }

        function syncActiveDisplay() {
            btn.dataset.isHovered = 'false';
            renderLabel(getActiveAvgMode(target).name);
            if (infoTtEl && window._cmHoverTarget === btn) {
                infoTtEl.classList.remove('visible');
                window._cmHoverTarget = null;
            }
        }

        btn.addEventListener('mouseenter', () => syncHoverPreview());
        btn.addEventListener('mouseleave', (e) => {
            if (isCursorOverButton(e)) return;
            syncActiveDisplay();
        });

        btn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();

            const prevRects = new Map();
            if (infoTtEl && infoTtEl.classList.contains('visible')) {
                infoTtEl.querySelectorAll('.cm-avg-card-row').forEach(row => {
                    const id = row.getAttribute('data-id');
                    if (id !== null) prevRects.set(id, row.getBoundingClientRect().top);
                });
            }

            const currentIdx = (typeof UI_STATE !== 'undefined' && UI_STATE[avgKey] !== undefined) ? UI_STATE[avgKey] : 2;
            const nextIdx = getNextAvgMode(currentIdx);
            UI_STATE[avgKey] = nextIdx;

            syncHoverPreview();

            if (prevRects.size > 0 && infoTtEl) {
                infoTtEl.querySelectorAll('.cm-avg-card-row').forEach(row => {
                    const id = row.getAttribute('data-id');
                    const oldTop = prevRects.get(id);
                    if (oldTop !== undefined) {
                        const newTop = row.getBoundingClientRect().top;
                        const deltaY = oldTop - newTop;
                        if (deltaY !== 0) {
                            row.style.transition = 'none';
                            row.style.transform = `translateY(${deltaY}px)`;
                            requestAnimationFrame(() => {
                                row.style.transition = 'transform 0.28s cubic-bezier(0.2, 0.8, 0.2, 1), background 0.2s ease, border-color 0.2s ease';
                                row.style.transform = 'translateY(0px)';
                            });
                        }
                    }
                });
            }

            const payload = window.CM_CURRENT_FILTERED_PAYLOAD || window.MATRIX_CHART_PAYLOAD || window.MATRIX_PAYLOAD || [];
            if (target === 'trend') renderTrendChart(payload);
            else if (target === 'frag') renderFragChart(payload);
            else if (target === 'churn') renderChurnChart(payload);
            else if (target === 'blast') renderBlastChart(payload);
            else renderRiskCharts(payload);
        });

        syncActiveDisplay();
    });
}

export function initGlobalChronRevolving() {
    const btn = document.getElementById('cm-global-chron-btn');
    const infoTtEl = document.getElementById('info-tt');
    if (!btn || btn.__cmChronBound) return;
    btn.__cmChronBound = true;

    function renderLabel() {
        const isChron = UI_STATE.globalChron;
        btn.innerHTML = (isChron ? TIMELINE_ICON_SVG : INDEX_ICON_SVG) + ` <span class="cm-chron-label">${isChron ? 'Timeline' : 'Index'}</span>`;
        btn.classList.toggle('active', isChron);
    }

    function isCursorOverButton(e) {
        if (!e || e.clientX === undefined) return btn.matches(':hover');
        const rect = btn.getBoundingClientRect();
        return (
            e.clientX >= rect.left && e.clientX <= rect.right &&
            e.clientY >= rect.top && e.clientY <= rect.bottom
        );
    }

    function showCard() {
        if (!infoTtEl) return;
        window._cmHoverTarget = btn;
        btn.dataset.isHovered = 'true';
        infoTtEl.innerHTML = getRevolvingChronCardHTML();
        positionRevolvingCard(btn, infoTtEl);
    }

    function syncHoverPreview() {
        renderLabel();
        showCard();
    }

    function syncActiveDisplay() {
        btn.dataset.isHovered = 'false';
        renderLabel();
        if (infoTtEl && window._cmHoverTarget === btn) {
            infoTtEl.classList.remove('visible');
            window._cmHoverTarget = null;
        }
    }

    btn.addEventListener('mouseenter', () => syncHoverPreview());
    btn.addEventListener('mouseleave', (e) => {
        if (isCursorOverButton(e)) return;
        syncActiveDisplay();
    });

    btn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();

        const prevRects = new Map();
        if (infoTtEl && infoTtEl.classList.contains('visible')) {
            infoTtEl.querySelectorAll('.cm-chron-card-row').forEach(row => {
                const id = row.getAttribute('data-id');
                if (id) prevRects.set(id, row.getBoundingClientRect().top);
            });
        }

        UI_STATE.globalChron = !UI_STATE.globalChron;
        const isChron = UI_STATE.globalChron;

        const CHRONO_CAPABLE = ['stack', 'trend', 'conv', 'frag', 'churn', 'blast', 'heat', 'types', 'tier'];
        CHRONO_CAPABLE.forEach(t => {
            UI_STATE[t] = isChron;
            if (['trend', 'frag', 'churn', 'blast'].includes(t)) {
                const avgKey = t === 'trend' ? 'avgTrend' : 'avg' + t.charAt(0).toUpperCase() + t.slice(1);
                UI_STATE[avgKey] = isChron ? 2 : 0;
                const ab = document.querySelector(`button[data-action="cycleAvg"][data-target="${t}"]`);
                if (ab) {
                    const mode = AVG_MODES[UI_STATE[avgKey]] || AVG_MODES[2];
                    const lbl = ab.querySelector('.cm-avg-label');
                    if (lbl) lbl.textContent = mode.name;
                    ab.classList.toggle('active', UI_STATE[avgKey] !== 0);
                }
            }
        });

        syncHoverPreview();

        if (prevRects.size > 0 && infoTtEl) {
            infoTtEl.querySelectorAll('.cm-chron-card-row').forEach(row => {
                const id = row.getAttribute('data-id');
                const oldTop = prevRects.get(id);
                if (oldTop !== undefined) {
                    const newTop = row.getBoundingClientRect().top;
                    const deltaY = oldTop - newTop;
                    if (deltaY !== 0) {
                        row.style.transition = 'none';
                        row.style.transform = `translateY(${deltaY}px)`;
                        requestAnimationFrame(() => {
                            row.style.transition = 'transform 0.28s cubic-bezier(0.2, 0.8, 0.2, 1), background 0.2s ease, border-color 0.2s ease';
                            row.style.transform = 'translateY(0px)';
                        });
                    }
                }
            });
        }

        const payload = window.CM_CURRENT_FILTERED_PAYLOAD || window.MATRIX_CHART_PAYLOAD || window.MATRIX_PAYLOAD || [];
        renderStackChart(payload);
        renderTrendChart(payload);
        renderConvergenceChart(payload);
        renderFragChart(payload);
        renderChurnChart(payload);
        renderBlastChart(payload);
        renderTierChart(payload);
        renderTypesChart(payload);

        let ver = "0.1.412";
        try { ver = window.location.href.match(/v=([0-9\.]+)/)[1]; } catch(err){}
        import(`../ui/heatmap.js?v=${ver}`).then(m => {
            if (m.renderHeatmap) m.renderHeatmap(payload);
        }).catch(() => {});
    });

    syncActiveDisplay();
}
