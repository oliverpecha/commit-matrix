// Tier Distributions Configuration
export const TIER_DISTRIBUTIONS = [
    {
        id: 'tight_floor',
        label: 'Tight Floor',
        desc: 'Minor < 7 · Core 7–13.9 · Pivotal ≥ 14',
        pivotal: 14.0,
        core: 7.0
    },
    {
        id: 'high_bar',
        label: 'High Bar',
        desc: 'Minor < 8 · Core 8–14.9 · Pivotal ≥ 15',
        pivotal: 15.0,
        core: 8.0
    },
    {
        id: 'asymmetric',
        label: 'Asymmetric',
        desc: 'Minor < 6.5 · Core 6.5–12.9 · Pivotal ≥ 13',
        pivotal: 13.0,
        core: 6.5
    }
];

export const TIER_DISTRIBUTION_MAP = Object.fromEntries(
    TIER_DISTRIBUTIONS.map(d => [d.id, d])
);

export function getTierFromTotal(tot, distId = 'tight_floor') {
    const dist = TIER_DISTRIBUTION_MAP[distId] || TIER_DISTRIBUTIONS[0];
    const val = Number(tot) || 0;
    if (val >= dist.pivotal) return 'Pivotal';
    if (val >= dist.core) return 'Core';
    return 'Minor';
}
