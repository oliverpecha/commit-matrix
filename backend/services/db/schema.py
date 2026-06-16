"""
CommitMatrix SQLite schema — boundary-anchored architecture persistence.

All metrics as columns (full relational, no JSON blobs).
Boundaries replace stored generation IDs.
Generation numbers computed at display time from boundary topo_id ordering.
"""

SCHEMA_VERSION = 1

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS taxonomy (
    tag TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    magnitude TEXT NOT NULL,
    family TEXT
);

CREATE TABLE IF NOT EXISTS architecture_runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_label TEXT NOT NULL,
    repo_display TEXT,
    generated_at TEXT NOT NULL,
    contract_version TEXT,
    computation_version INTEGER DEFAULT 1,
    last_recomputed_at TEXT,
    is_full_scan BOOLEAN DEFAULT TRUE,
    total_commits INTEGER,
    total_blueprints INTEGER,
    total_generations INTEGER,
    first_topo_id INTEGER,
    last_topo_id INTEGER
);

CREATE TABLE IF NOT EXISTS architecture_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES architecture_runs(run_id),
    boundary_commit_sig TEXT,
    snapshot_sig TEXT,
    snapshot_path TEXT,
    shape TEXT,
    shape_label TEXT,
    generator_version TEXT,
    generator_mode TEXT,
    generator_model TEXT,
    blueprint_grade TEXT DEFAULT 'programmatic',
    blueprint_hash TEXT,
    size_bytes INTEGER,
    selected_files INTEGER,
    total_files INTEGER,
    is_current BOOLEAN,
    is_dominant BOOLEAN,
    lifespan_class TEXT,
    total_commits INTEGER,
    run_count INTEGER,
    first_seen_topo_id INTEGER,
    last_seen_topo_id INTEGER,
    first_seen_date TEXT,
    last_seen_date TEXT,
    longest_streak INTEGER,
    successive_commit_count INTEGER,
    reappeared_commit_count INTEGER,
    operational_commit_count INTEGER,
    development_commit_count INTEGER,
    effective_commits INTEGER,
    share_of_generation REAL
);

CREATE TABLE IF NOT EXISTS architecture_commits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES architecture_runs(run_id),
    snapshot_sig TEXT,
    topo_id INTEGER,
    commit_sig TEXT,
    date TEXT,
    subject TEXT,
    role TEXT
);

CREATE TABLE IF NOT EXISTS architecture_boundaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES architecture_runs(run_id),
    boundary_commit_sig TEXT,
    boundary_commit_topo_id INTEGER,
    boundary_commit_date TEXT,
    boundary_commit_subject TEXT,
    cause_tag TEXT REFERENCES taxonomy(tag),
    magnitude TEXT,
    scope_dirs TEXT,
    scope_file_count INTEGER,
    snapshot_count INTEGER,
    structural_count INTEGER,
    incremental_count INTEGER,
    dominant_snapshot_sig TEXT,
    dominant_effective_commits INTEGER,
    dominant_share REAL,
    repeated_treesig_count INTEGER,
    distinct_commit_count INTEGER,
    displaced_snapshot_sig TEXT,
    displaced_lifespan_class TEXT,
    displaced_was_dominant BOOLEAN
);

CREATE INDEX IF NOT EXISTS idx_snapshots_run ON architecture_snapshots(run_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_sig ON architecture_snapshots(snapshot_sig);
CREATE INDEX IF NOT EXISTS idx_snapshots_boundary ON architecture_snapshots(run_id, boundary_commit_sig);
CREATE INDEX IF NOT EXISTS idx_snapshots_dominant ON architecture_snapshots(run_id, is_dominant);
CREATE INDEX IF NOT EXISTS idx_snapshots_lifespan ON architecture_snapshots(run_id, lifespan_class);
CREATE INDEX IF NOT EXISTS idx_commits_run ON architecture_commits(run_id);
CREATE INDEX IF NOT EXISTS idx_commits_sig ON architecture_commits(snapshot_sig);
CREATE INDEX IF NOT EXISTS idx_commits_topo ON architecture_commits(run_id, topo_id);
CREATE INDEX IF NOT EXISTS idx_commits_role ON architecture_commits(run_id, role);
CREATE INDEX IF NOT EXISTS idx_boundaries_run ON architecture_boundaries(run_id);
CREATE INDEX IF NOT EXISTS idx_boundaries_topo ON architecture_boundaries(run_id, boundary_commit_topo_id);
"""
