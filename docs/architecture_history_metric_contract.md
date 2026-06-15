# Architecture History — Serialization & Metric Contract

**Contract Version:** 1.0
**Last Updated:** 2026-06-15

---

## Contract Versioning

The JSON payload includes a top-level `contract_version` field.
Consumers should version-gate on this value.

| Version | Description |
|---------|-------------|
| 1.0     | Initial stable contract. flags/badges pattern, lifespan_class enum, taxonomy-routed cause tags. |

Bumping the version: change `CONTRACT_VERSION` in `orchestrator.py`.
Additive fields (new flags, new badges) do **not** require a version bump.
Removing or renaming an existing field **does**.

---

## Snapshot Flags & Badges (Canonical State + Derived View)

### `flags` — Authoritative Source

Typed state dictionary. Agents, CI, and policy logic must use this exclusively.

```json
{
  "is_current": false,
  "is_dominant": true,
  "lifespan_class": "long"
}

Key	Type	Values	Rule
is_current	bool	true/false	Snapshot matches the active blueprint
is_dominant	bool	true/false	Highest-ranked snapshot in its generation
lifespan_class	string	"long", "short", "standard"	See thresholds below

Lifespan thresholds:

    "long": effective_commits >= 3 AND longest_streak >= 3
    "short": total_commits == 1
    "standard": everything else

The internal model uses separate is_long_lived / is_short_lived booleans.
The serializer consolidates them into the single lifespan_class enum.
badges — Derived Presentation View

Read-only string token array generated server-side from flags.
UI renders directly via .map(renderChip). Never accepted as input.

JSON

"badges": ["dominant", "long_lived"]

Derivation rules (order is stable):

    Boolean flags: is_current -> "current", is_dominant -> "dominant"
    Lifespan: "long" -> "long_lived", "short" -> "short_lived", "standard" -> no badge

Invariant: snapshot.badges == derive_badges(snapshot.flags) must hold for every snapshot. Contract tests enforce this.

On conflict: flags always wins. badges is non-authoritative.
Snapshot Metrics
SnapshotLifespanMetrics (lifespan_metrics)
Field	Description
total_commits	Total mapped commits across trigger, successive, and all reappeared runs
run_count	Number of contiguous runs for the TreeSig
first_seen_topo_id	Earliest topo ID across all runs
last_seen_topo_id	Latest topo ID across all runs
first_seen_date	Date of first seen commit
last_seen_date	Date of last seen commit
longest_streak	Maximum contiguous run length

Edge cases:

    Single-commit snapshot: total_commits=1, run_count=1, longest_streak=1.
    Missing trigger: first seen falls back to earliest known run member.

SnapshotCompositionMetrics (composition_metrics)
Field	Description
successive_commit_count	Commits in the main run after the trigger
reappeared_commit_count	Total commits across all reappeared runs
operational_commit_count	Commits classified as stash/index/recovery/operational
development_commit_count	total_commits - operational_commit_count

Operational commits are preserved in the run model. They are never silently discarded.
SnapshotDominanceMetrics (dominance_metrics)

Locked rule: effective_commits = total_commits - operational_commit_count
Field	Description
effective_commits	Non-operational commit count
share_of_generation	Fraction of generation's effective commits
longest_streak	Maximum contiguous run length
reappearance_commit_count	Commits from reappeared runs

Note: is_dominant, is_long_lived, and is_short_lived are intentionally
excluded from dominance_metrics. They live in flags.

Ranking rule (for dominant assignment):

    effective_commits descending
    share_of_generation descending
    longest_streak descending
    reappearance_commit_count descending
    first_seen_topo_id ascending

Generation Summaries

JSON keys are string representations of integer generation IDs (JSON spec requires string keys). Sorted for deterministic output.
Fields
Field	Description
generation	Integer generation number
cause_tag	Normalized machine token (routed through taxonomy.py)
cause_label	Human-readable label (derived from cause_tag via taxonomy.py)
generation_distinct_commit_count	Distinct commits mapped to this generation
snapshot_count	Total snapshots in this generation
structural_count	Structurally distinct snapshots
incremental_count	Leaf-only / incremental snapshots
dominant_snapshot_sig	Signature of the dominant snapshot
dominant_effective_commits	Effective commits of the dominant snapshot
dominant_share_of_generation	Share held by the dominant snapshot
repeated_treesig_count	TreeSigs that appear in more than one run
Taxonomy Boundary Layer (taxonomy.py)

cause_tag and cause_label are never passed through raw from internal models.
They are routed through taxonomy.py boundary functions:

    normalize_cause_tag(raw) — maps volatile internal tokens (e.g. major:dirs) to stable API tokens (e.g. major_dirs)
    get_boundary_cause_label(normalized) — maps API tokens to human labels

Adding a new internal cause:

    Add raw token -> normalized key in BOUNDARY_CAUSE_TAG_MAP
    Add normalized key -> label in BOUNDARY_CAUSE_LABEL_MAP
    No serializer changes required

Unknown tags degrade gracefully: sanitized to underscored lowercase tokens,
labels title-cased from the token.
## Generation Boundary Rationale (`boundary`)

Each generation summary includes a `boundary` object that answers: why does this
generation exist, what triggered it, how significant was the change, and what did
it replace.

```json
"boundary": {
  "cause_tag": "major_file_count",
  "cause_label": "Significant File Count Threshold Breach",
  "magnitude": "moderate",
  "commit": {
    "commit_sig": "98c6051",
    "topo_id": 2,
    "date": "May 16, '26",
    "date_iso": "2026-05-16",
    "subject": "decouple UI into ES6 modules..."
  },
  "scope": {
    "top_level_dirs": ["backend", "data", "static", "templates"],
    "file_count": 18
  },
  "displaced": {
    "snapshot_sig": "60859c3eeca2e317...",
    "lifespan_class": "short",
    "was_dominant": true
  }
}

Boundary Fields
Field	Type	Source	Description
cause_tag	string	taxonomy.py	Normalized boundary cause token
cause_label	string	taxonomy.py	Human-readable label
magnitude	string	taxonomy.py	Bucket: "major", "moderate", "minor" — derived from taxonomy mapping
commit	object/null	First snapshot trigger	The commit that crossed the generation boundary
scope.top_level_dirs	string[]	Meta sidecar	Top-level directories at the boundary snapshot
scope.file_count	int/null	Meta sidecar	Total tracked files at the boundary snapshot
displaced.snapshot_sig	string/null	Previous gen	Signature of the snapshot this generation replaced
displaced.lifespan_class	string/null	Previous entry	"long", "short", or "standard"
displaced.was_dominant	bool/null	Previous entry	Whether the displaced snapshot was its generation's dominant
Magnitude Mapping

Magnitude is derived directly from the normalized cause tag, not from numeric thresholds:
Tags	Magnitude
genesis, major_dirs, major_selected_files, multi_dir_dirs, multi_dir_coverage, multi_dir_default	major
major_file_count	moderate
leaf_only	minor
Unknown tags	moderate (safe default)
Boundary Rules

    boundary is present on every generation summary.
    Generation 1 has displaced: null (nothing preceded it).
    scope may be null if the meta sidecar is missing or malformed.
    commit uses the same shape as snapshot triggers.
    cause_tag inside boundary matches the top-level cause_tag on the generation summary.

Reserved Future Fields

    boundary.scope.file_count_delta — difference from previous generation's file count
    [cross-gen] badge — for snapshots whose runs span multiple generations

These are intentionally not required for the current contract version.
Output Surfaces
CLI (--json)

Full contract payload with contract_version, entries, generation_summaries, and applied filters.
CLI (text renderer)

Snapshot view: header with shape label and badge chips, compact lifespan line,
trigger block, successive/reappeared sections, operational annotations.

Generation view: summary panel using generation summary metrics.
Downstream Consumers (API / DB / LLM)

These metrics are typed contract objects. Consumers must treat flags as
authoritative and may render badges directly without recomputing.
Visibility Modes

Default: show operational commits inline with annotations.

Compact / hidden operational: collapse operational rows into summary lines.
Never silently drop them from metric inputs.
Contract Evolution Rules

    flags is the single source of truth. badges is derived, read-only.
    Adding new flags or badges is additive and non-breaking.
    Clients must ignore unknown badge tokens.
    Removing or renaming a flag requires a contract version bump.
    Changing derive_badges logic requires review and test updates.
    taxonomy.py governs all external cause tags and labels.
    Internal model changes that don't affect serialized output require no contract action.
    