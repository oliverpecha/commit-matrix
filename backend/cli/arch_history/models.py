from __future__ import annotations

from dataclasses import asdict, dataclass, field

@dataclass
class CommitRef:
    commit_sig: str        # currently the Git commit hash (Git commit hash today)
    subject: str
    topo_id: int | None = None
    date: str | None = None  # ISO format, e.g. "2026-05-16"

@dataclass
class SnapshotLifespanMetrics:
    """How long and across how many runs a snapshot was active."""
    total_commits: int
    run_count: int
    first_seen_topo_id: int | None
    last_seen_topo_id: int | None
    first_seen_date: str
    last_seen_date: str
    longest_streak: int

@dataclass
class SnapshotCompositionMetrics:
    """How the snapshot's commits break down by role."""
    successive_commit_count: int
    reappeared_commit_count: int
    operational_commit_count: int
    development_commit_count: int

@dataclass
class SnapshotDominanceMetrics:
    """How dominant a snapshot is within its generation."""
    effective_commits: int
    share_of_generation: float
    longest_streak: int
    reappearance_commit_count: int
    is_dominant: bool
    is_long_lived: bool
    is_short_lived: bool

@dataclass
class BoundaryScope:
    """What directories and file counts characterize the boundary snapshot."""
    top_level_dirs: list[str]
    file_count: int | None = None


@dataclass
class DisplacedSnapshot:
    """What snapshot the new generation replaced."""
    snapshot_sig: str | None = None
    lifespan_class: str | None = None
    was_dominant: bool | None = None


@dataclass
class BoundaryInfo:
    """Full rationale for why a generation boundary exists."""
    cause_tag: str
    cause_label: str
    magnitude: str
    commit: CommitRef | None = None
    scope: BoundaryScope | None = None
    displaced: DisplacedSnapshot | None = None


@dataclass
class GenerationSummaryMetrics:
    """Generation-level summary used by the history printer."""
    generation: int
    cause_tag: str
    cause_label: str
    generation_distinct_commit_count: int
    snapshot_count: int
    structural_count: int
    incremental_count: int
    dominant_snapshot_sig: str
    dominant_effective_commits: int
    dominant_share_of_generation: float
    repeated_treesig_count: int

@dataclass
class SnapshotEntry:
    generation: int
    generation_index: int
    snapshot_sig: str
    shape: str
    generator_version: str
    mode: str
    generated_at: str
    size_bytes: int
    selected_files: str | int
    total_files: str | int
    trigger: CommitRef | None = None
    also_used_by: list[CommitRef] = field(default_factory=list)
    successive_used_by: list[CommitRef] = field(default_factory=list)
    reappeared_runs: list[list[CommitRef]] = field(default_factory=list)
    is_current: bool = False
    shape_label: str | None = None
    lifespan: SnapshotLifespanMetrics | None = None
    composition: SnapshotCompositionMetrics | None = None
    dominance: SnapshotDominanceMetrics | None = None

@dataclass
class CurrentBlueprint:
    snapshot_sig: str
    generated_at: str
    generator_version: str
    mode: str
    shape: str
    total_files: str | int
    selected_files: str | int

@dataclass
class HistoryReport:
    repo_label: str
    repo_display: str
    total_commits: int
    total_blueprints: int
    total_generations: int
    current: CurrentBlueprint
    entries: list[SnapshotEntry]
    generation_summaries: dict[int, GenerationSummaryMetrics] | None = None
