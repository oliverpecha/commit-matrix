export const CM_EXPLANATIONS = {
    
    // ==========================================
    // KPI CARDS & CHARTS
    // ==========================================
    kpi_tot: "Total number of evaluated commits mapped to the codebase logic.\n\nWhy it matters: A baseline metric of mechanical output. Use alongside other metrics to gauge true velocity.",
    kpi_avg: "The rolling average Rubric score.\n\nWhy it matters: Establishes the typical weight of a developer's contribution. Low averages mean minor tweaks; high averages mean heavy lifting.",
    kpi_crit: "Commits scoring in the Pivotal/Critical tier.\n\nWhy it matters: Highlights heavy architectural shifts or major breakages. These are the needle-movers of your product.",
    kpi_sig: "Commits scoring in the Core/Significant tier.\n\nWhy it matters: Standard features and non-trivial refactors. The bread and butter of continuous delivery.",
    kpi_rout: "Commits scoring in the Minor/Routine tier.\n\nWhy it matters: Minor bug fixes, chores, and configuration edits. High volumes here often signify tech debt payment.",
    
    tierDist: "Proportion of commits divided into priority tiers.\n\nWhy it matters: Helps leadership verify that engineering resources are balanced between high-value feature delivery and minor maintenance.\n\nIdeal state: A healthy mix, typically avoiding >50% minor unless in a dedicated stabilization phase.",
    rubricAxis: "Visual breakdown of each commit's score across the active rubric's dimensions.\n\nWhy it matters: Exposes the specific nature of a commit. A commit scoring high on Risk but low on Impact requires different QA attention than one high on Scope but low on Risk.",
    commitTypes: "Distribution of Conventional Commits tags extracted from subjects.\n\nWhy it matters: Quickly shows the mechanical focus of the team. A spike in 'fix' indicates quality issues, while 'feat' indicates product velocity.",
    scoreTrend: "Chronological progression of total commit scores.\n\nWhy it matters: Visualizes team velocity and the scale of continuous delivery. Identifies sprint crunches or dead zones.\n\nIdeal state: Consistent grouping of high-value commits without massive gaps.",
    heatmap: "Sub-services touched by each commit over time.\n\nWhy it matters: Highlights architectural bottlenecks. If a single service is touched by every commit, it represents tight coupling and high risk.\n\nIdeal state: Distributed touches indicating decoupled architecture.",
    
    // ==========================================
    // TELEMETRY / HEURISTICS
    // ==========================================
    fragility: "Formula: (Complexity + Risk) / Documentation.\n\nWhy it matters: Isolates unmitigated danger. Identifies complex, high-risk code pushed without sufficient docs or tests to protect the system.\n\nIdeal state: Lower is better. Bright red spikes indicate dangerous technical debt.",
    churn: "Formula: Complexity / Impact.\n\nWhy it matters: Measures return on developer energy. High scores flag over-engineering, code churn, or convoluted solutions to simple problems.\n\nIdeal state: Lower is better. Bright purple spikes mean heavy effort with little systemic value.",
    blast: "Formula: Scope × Risk.\n\nWhy it matters: The QA Siren. Identifies commits with massive surface area and high danger.\n\nIdeal state: Lower is better. Bright orange spikes demand rigorous integration testing before deployment.",
    nexus: "Systemic Convergence Overlay.\n\nWhy it matters: Identifies the most dangerous codebase mutations by locating commits that simultaneously trigger the worst 25% of Fragility, Churn, AND Blast Radius.\n\nIdeal state: A flatline. Dots appear only when severe systemic risk is detected. Colors map to the Primary Scope.",
    avg: "Selects the algorithm used to calculate the moving average line. Different modes highlight different development patterns.",
    
    // ==========================================
    // TABLE HEADERS
    // ==========================================
    table_all: "Complete index of analyzed commits.",
    table_n: "Chronological ID assigned to the commit.",
    table_ts: "Authored: When the commit was originally authored.",
    table_p_type: "Type: Conventional commit type (e.g., feat, fix, chore).",
    table_p_scope: "Scope: The specific subsystem or domain affected by the commit.",
    table_p_desc: "Subject: The first line of the commit message.",
    table_tot: "Score: Total combined Rubric Score.",
    table_h: "Hash: The unique Git commit SHA identifier.",
    table_lines_added: "Lines Added: Total lines of code added in this commit.",
    table_lines_deleted: "Lines Deleted: Total lines of code deleted in this commit."
};
