export const BEO_EXPLANATIONS = {
    kpi_tot: "Total number of evaluated commits mapped to the codebase logic.\n\nWhy it matters: A baseline metric of mechanical output. Use alongside other metrics to gauge true velocity.",
    kpi_avg: "The rolling average CIRSD score out of a max possible 15 points.\n\nWhy it matters: Establishes the typical weight of a developer's contribution. Low averages mean minor tweaks; high averages mean heavy lifting.",
    kpi_crit: "Commits scoring ≥ 13.\n\nWhy it matters: Highlights heavy architectural shifts or major breakages. These are the needle-movers of your product.",
    kpi_sig: "Commits scoring 9–12.\n\nWhy it matters: Standard features and non-trivial refactors. The bread and butter of continuous delivery.",
    kpi_rout: "Commits scoring 5–8.\n\nWhy it matters: Minor bug fixes, chores, and configuration edits. High volumes here often signify tech debt payment.",
    tierDist: "Proportion of commits divided into priority tiers.\n\nWhy it matters: Helps leadership verify that engineering resources are balanced between high-value feature delivery and routine maintenance.",
    cirsdAxis: "Visual breakdown of each commit's score across 5 impact dimensions.\n\nWhy it matters: Exposes the specific nature of a commit.",
    commitTypes: "Distribution of Conventional Commits tags extracted from subjects.",
    scoreTrend: "Chronological progression of total commit scores.",
    heatmap: "Sub-services touched by each commit over time.\n\nWhy it matters: Highlights architectural bottlenecks.",
    table_all: "Complete index of analyzed commits.",
    cirsd_C: "Complexity: Measures logical branching and cyclomatic depth.",
    cirsd_I: "Impact: Breadth of systemic functional effect.",
    cirsd_R: "Risk: Danger of regression or breakages.",
    cirsd_S: "Scope: Number of unique services and files touched.",
    cirsd_D: "Documentation: Delta between code changes and inline comments/tests."
};

export const CM_COLORS = {
    Critical: '#ff4b4b',
    Significant: '#ffb84d',
    Routine: '#fce83a'
};

export const SC_COLORS = {
    t_core: '#ff4b4b', t_proxy: '#00e676', t_scripts: '#ffeb3b', t_config: '#29b6f6',
    t_dashboard: '#ab47bc', t_docs: '#ffa726', t_tests: '#00bcd4', t_preflight: '#ec407a', t_metrics: '#69f0ae'
};

export const SC_CLASSES = {
    core: 'sc-core', proxy: 'sc-proxy', scripts: 'sc-scripts', config: 'sc-config',
    dashboard: 'sc-dashboard', docs: 'sc-docs', tests: 'sc-tests', preflight: 'sc-preflight', metrics: 'sc-metrics', global: 'sc-docs'
};

export const BP_AXC = ['#8ab4f0','#c99ef0','#ef8a8a','#8ed068','#f0b876'];
export const BP_AXC_BASE = ['rgba(138,180,240,0.3)','rgba(201,158,240,0.3)','rgba(239,138,138,0.3)','rgba(142,208,104,0.3)','rgba(240,184,118,0.3)'];
