from __future__ import annotations
from backend.services.architecture.metrics import human_shape_label

import json
import re
from dataclasses import asdict
from pathlib import Path

from backend.services.pipeline.pipeline_config import HOST_REPO_NAME

from backend.services.architecture.models import (
    BoundaryInfo,
    BoundaryScope,
    CurrentBlueprint,
    DisplacedSnapshot,
    GenerationSummaryMetrics,
    HistoryReport,
    SnapshotEntry,
    CommitRef,
)
from backend.services.architecture.taxonomy import (
    normalize_cause_tag,
    get_boundary_cause_label,
    get_boundary_magnitude,
)
from backend.cli.arch_history.arch_selectors import Selector, SelectorCategory, parse_selector, resolve_sig_category

from backend.services.architecture.metrics import (
    _compute_snapshot_lifespan_metrics,
    _compute_snapshot_composition_metrics,
    _compute_snapshot_dominance_metrics,
    _assign_dominant_flags,
    _compute_generation_summaries,
    validate_commit_snapshot_invariant,
)
# Legacy assembly routes removed
from backend.cli.arch_history.filters import (
    _find_entry_by_commit_sig_prefix,
    _find_snapshot_by_sig_prefix,
    _matches_selector_value,
    filter_history_report,
)
from backend.cli.arch_history.contract import serialize_history_report_to_contract






def history_report_to_dict(report: HistoryReport) -> dict:
    """DEPRECATED — use serialize_history_report_to_contract().

    Raw ``dataclasses.asdict()`` pass-through with no schema stability
    guarantees.  Scheduled for removal once all consumers migrate to C1.
    """
    import warnings
    # Suppress if [arch-graph] has written full commit coverage (unmapped count will be 0)
    warnings.warn(
        "history_report_to_dict() is deprecated; "
        "use serialize_history_report_to_contract()",
        DeprecationWarning,
        stacklevel=2,
    )
    return asdict(report)

# ─── C1 Contract Serialization ───────────────────────────────────────────────
#
# Design: canonical state (flags) + derived view (badges).
#   * flags  — authoritative typed booleans; agents/CI/policy use these.
#   * badges — read-only presentation tokens derived deterministically
#              from flags; UI renders these directly.  Never accepted as
#              input.  On conflict, flags wins.
#
# cause_tag / cause_label in generation summaries are routed through
# taxonomy.py boundary functions so internal classification changes
# never break the external contract.
#
# See: docs/architecture_history_metric_contract.md (ADR)
# ─────────────────────────────────────────────────────────────────────────────

CONTRACT_VERSION = "1.0"

_BOOLEAN_BADGE_RULES: list[tuple[str, str]] = [
    # (badge_token, flags_key)
    ("current",  "is_current"),
    ("dominant", "is_dominant"),
]

_LIFESPAN_BADGE_MAP: dict[str, str] = {
    "long":  "long_lived",
    "short": "short_lived",
}


def derive_badges(flags: dict) -> list[str]:
    """Deterministic derivation: flags dict -> badge token list.

    Handles boolean flags and the lifespan_class enum.
    Public so contract tests can assert:
        snapshot["badges"] == derive_badges(snapshot["flags"])
    """
    badges = [token for token, key in _BOOLEAN_BADGE_RULES if flags.get(key, False)]
    lc = flags.get("lifespan_class", "standard")
    if lc in _LIFESPAN_BADGE_MAP:
        badges.append(_LIFESPAN_BADGE_MAP[lc])
    return badges


def _build_snapshot_flags(entry: SnapshotEntry) -> dict:
    """Collapse scattered booleans into a single canonical flags dict.

    Internal model uses separate is_long_lived / is_short_lived booleans.
    External contract consolidates into a single lifespan_class enum:
      "long"     -- effective_commits >= 3 and longest_streak >= 3
      "short"    -- total_commits == 1
      "standard" -- everything else
    """
    dom = entry.dominance
    if dom:
        if dom.is_long_lived:
            lifespan_class = "long"
        elif dom.is_short_lived:
            lifespan_class = "short"
        else:
            lifespan_class = "standard"
    else:
        lifespan_class = "standard"

    return {
        "is_current":     entry.is_current,
        "is_dominant":    dom.is_dominant if dom else False,
        "lifespan_class": lifespan_class,
    }


def _serialize_commit_ref(ref: CommitRef) -> dict:
    return {
        "commit_sig": ref.commit_sig,
        "topo_id":    ref.topo_id,
        "date":       ref.date,
        "subject":    ref.subject,
    }


def _serialize_snapshot_entry(entry: SnapshotEntry) -> dict:
    flags = _build_snapshot_flags(entry)

    return {
        "generation":        entry.generation,
        "generation_index":  entry.generation_index,
        "snapshot_sig":      entry.snapshot_sig,
        "shape":             entry.shape,
        "shape_label":       entry.shape_label,
        "generator_version": entry.generator_version,
        "mode":              entry.mode,
        "generated_at":      entry.generated_at,
        "size_bytes":        entry.size_bytes,
        "selected_files":    entry.selected_files,
        "total_files":       entry.total_files,

        # -- commit graph --
        "trigger":            _serialize_commit_ref(entry.trigger) if entry.trigger else None,
        "also_used_by":       [_serialize_commit_ref(r) for r in entry.also_used_by],
        "successive_used_by": [_serialize_commit_ref(r) for r in entry.successive_used_by],
        "reappeared_runs":    [
            [_serialize_commit_ref(r) for r in run]
            for run in entry.reappeared_runs
        ],

        # -- canonical state + derived view --
        "flags":  flags,
        "badges": derive_badges(flags),

        # -- metrics (numerical only; booleans live in flags) --
        "lifespan_metrics": {
            "total_commits":      entry.lifespan.total_commits,
            "run_count":          entry.lifespan.run_count,
            "first_seen_topo_id": entry.lifespan.first_seen_topo_id,
            "last_seen_topo_id":  entry.lifespan.last_seen_topo_id,
            "first_seen_date":    entry.lifespan.first_seen_date,
            "last_seen_date":     entry.lifespan.last_seen_date,
            "longest_streak":     entry.lifespan.longest_streak,
        } if entry.lifespan else None,

        "composition_metrics": {
            "successive_commit_count":  entry.composition.successive_commit_count,
            "reappeared_commit_count":  entry.composition.reappeared_commit_count,
            "operational_commit_count": entry.composition.operational_commit_count,
            "development_commit_count": entry.composition.development_commit_count,
        } if entry.composition else None,

        "dominance_metrics": {
            "effective_commits":   entry.dominance.effective_commits,
            "share_of_generation": entry.dominance.share_of_generation,
        } if entry.dominance else None,
    }


def _load_snapshot_sidecar(snapshot_sig: str) -> dict:
    """Load snapshot metadata from the SQLite database (legacy sidecar replacement)."""
    from backend.services.pipeline.pipeline_config import HOST_REPO_NAME
    from backend.services.db.reader import load_all_snapshot_meta
    
    try:
        all_meta = load_all_snapshot_meta(HOST_REPO_NAME)
        prefix = snapshot_sig[:16]
        return all_meta.get(prefix, {})
    except Exception:
        return {}


def _compute_generation_boundaries(
    entries: list[SnapshotEntry],
    generation_summaries: dict[int, GenerationSummaryMetrics],
) -> dict[int, BoundaryInfo]:
    """Compute boundary rationale for each generation.

    For each generation:
      - cause_tag/cause_label: from the generation summary (already normalized)
      - magnitude: derived from taxonomy family mapping
      - commit: trigger of the first structural snapshot in the generation
      - scope: top_level_dirs and file_count from the boundary snapshot's sidecar
      - displaced: last snapshot of the previous generation
    """
    if not entries:
        return {}

    # Group entries by generation
    by_gen: dict[int, list[SnapshotEntry]] = {}
    for e in entries:
        by_gen.setdefault(e.generation, []).append(e)

    # Sort each generation's entries by topo_id
    for gen_entries in by_gen.values():
        gen_entries.sort(
            key=lambda e: e.trigger.topo_id if e.trigger and e.trigger.topo_id is not None else 10_000_000
        )

    sorted_gens = sorted(by_gen.keys())
    boundaries: dict[int, BoundaryInfo] = {}

    for idx, gen_id in enumerate(sorted_gens):
        summary = generation_summaries.get(gen_id)
        if summary is None:
            continue

        tag = normalize_cause_tag(summary.cause_tag)
        label = get_boundary_cause_label(tag)
        magnitude = get_boundary_magnitude(tag)

        gen_entries = by_gen[gen_id]

        # Boundary commit: trigger of the structural anchor (newest) in this generation
        boundary_commit = gen_entries[-1].trigger if gen_entries else None

        # Scope: from the structural anchor's meta sidecar
        scope = None
        if gen_entries:
            sidecar = _load_snapshot_sidecar(gen_entries[-1].snapshot_sig)
            if sidecar:
                scope = BoundaryScope(
                    top_level_dirs=sidecar.get("top_level_dirs", []),
                    file_count=sidecar.get("file_count") or (sidecar.get("change_summary") or {}).get("total_files"),
                )

        # Displaced: last snapshot of the previous generation
        displaced = None
        if idx > 0:
            prev_gen = sorted_gens[idx - 1]
            prev_entries = by_gen.get(prev_gen, [])
            if prev_entries:
                prev_last = prev_entries[-1]
                prev_dom = prev_last.dominance

                if prev_dom:
                    if prev_dom.is_long_lived:
                        lc = "long"
                    elif prev_dom.is_short_lived:
                        lc = "short"
                    else:
                        lc = "standard"
                else:
                    lc = "standard"

                displaced = DisplacedSnapshot(
                    snapshot_sig=prev_last.snapshot_sig,
                    lifespan_class=lc,
                    was_dominant=prev_dom.is_dominant if prev_dom else False,
                )

        boundaries[gen_id] = BoundaryInfo(
            cause_tag=tag,
            cause_label=label,
            magnitude=magnitude,
            commit=boundary_commit,
            scope=scope,
            displaced=displaced,
        )

    return boundaries


def _serialize_boundary(boundary: BoundaryInfo | None) -> dict | None:
    if boundary is None:
        return None
    return {
        "cause_tag":   boundary.cause_tag,
        "cause_label": boundary.cause_label,
        "magnitude":   boundary.magnitude,
        "commit":      _serialize_commit_ref(boundary.commit) if boundary.commit else None,
        "scope": {
            "top_level_dirs": boundary.scope.top_level_dirs,
            "file_count":     boundary.scope.file_count,
        } if boundary.scope else None,
        "displaced": {
            "snapshot_sig":   boundary.displaced.snapshot_sig,
            "lifespan_class": boundary.displaced.lifespan_class,
            "was_dominant":   boundary.displaced.was_dominant,
        } if boundary.displaced else None,
    }


def _serialize_generation_summary(
    summary: GenerationSummaryMetrics,
    boundary: BoundaryInfo | None = None,
) -> dict:
    tag = normalize_cause_tag(summary.cause_tag)
    result = {
        "generation":                       summary.generation,
        "cause_tag":                        tag,
        "cause_label":                      get_boundary_cause_label(tag),
        "generation_distinct_commit_count": summary.generation_distinct_commit_count,
        "snapshot_count":                   summary.snapshot_count,
        "structural_count":                 summary.structural_count,
        "incremental_count":                summary.incremental_count,
        "dominant_snapshot_sig":             summary.dominant_snapshot_sig,
        "dominant_effective_commits":        summary.dominant_effective_commits,
        "dominant_share_of_generation":      summary.dominant_share_of_generation,
        "repeated_treesig_count":           summary.repeated_treesig_count,
    }
    serialized_boundary = _serialize_boundary(boundary)
    if serialized_boundary is not None:
        result["boundary"] = serialized_boundary
    return result


def serialize_history_report_to_contract(report: HistoryReport) -> dict:
    """C1 contract serializer -- hand-rolled, stable external schema.

    Replaces the legacy ``history_report_to_dict()`` (raw asdict).

    Key differences from the legacy serializer:
      * ``contract_version`` field for consumer version-gating.
      * Snapshot booleans consolidated into ``flags`` (authoritative).
      * ``badges`` derived deterministically from ``flags`` (readOnly view).
      * Metrics namespaced: ``lifespan_metrics``, ``composition_metrics``,
        ``dominance_metrics`` -- dominance booleans excluded from metrics.
      * cause_tag / cause_label routed through taxonomy.py boundary layer.
      * Internal dataclass field names decoupled from external contract keys.
    """
    return {
        "contract_version": CONTRACT_VERSION,
        "repo_label":        report.repo_label,
        "repo_display":      report.repo_display,
        "total_commits":     report.total_commits,
        "total_blueprints":  report.total_blueprints,
        "total_generations": report.total_generations,
        "current": {
            "snapshot_sig":      report.current.snapshot_sig,
            "generated_at":      report.current.generated_at,
            "generator_version": report.current.generator_version,
            "mode":              report.current.mode,
            "shape":             report.current.shape,
            "total_files":       report.current.total_files,
            "selected_files":    report.current.selected_files,
        },
        "entries": [_serialize_snapshot_entry(e) for e in report.entries],
        # Compute boundary rationale for each generation
        "generation_summaries": (lambda: {
            str(gen_id): _serialize_generation_summary(
                summary,
                boundary=_compute_generation_boundaries(
                    report.entries,
                    report.generation_summaries or {},
                ).get(gen_id),
            )
            for gen_id, summary in sorted(
                (report.generation_summaries or {}).items()
            )
        })(),
    }



def load_history_report_from_db(repo_path: str, db_path: str | None = None):
    """Load architecture history report from SQLite for arch-history CLI.

    This is the DB-first replacement for build_history_report() in the Option A
    design. It uses architecture_runs, architecture_boundaries, architecture_snapshots,
    and architecture_commits as the primary source of truth.

    For now, it returns a simple dict; later it can be upgraded to structured
    dataclasses used by the renderer.
    """
    import sqlite3
    from backend.services.architecture.arch_storage import repo_id_from_path

    if db_path is not None:
        db = Path(db_path)
        inferred_label = repo_id_from_path(repo_path) if repo_path else None
    else:
        project_root = Path(__file__).resolve().parents[3]
        # If a wrapper script cd'd into the project root, OLDPWD holds your actual terminal directory
        import os
        if Path.cwd() == project_root and "OLDPWD" in os.environ:
            actual_user_dir = Path(os.environ["OLDPWD"])
        else:
            actual_user_dir = Path.cwd()
            
        inferred_label = repo_path if repo_path else actual_user_dir.name
        db = project_root / "data" / inferred_label / "db" / f"{repo_label}.db"
        if not db.exists():
            fallback = Path("data") / inferred_label / "db" / f"{repo_label}.db"
            if fallback.exists():
                db = fallback

    import sys
    print(f"[*] DB context: {db}", file=sys.stderr)
    
    if not db.exists():
        raise RuntimeError(f"No {repo_label}.db found at {db}")

    with sqlite3.connect(str(db)) as conn:
        conn.row_factory = sqlite3.Row

        # Blindly fetch the latest run from this DB without enforcing repo_label
        run_row = conn.execute(
            "SELECT run_id, repo_label, repo_display, generated_at, total_commits, total_blueprints, total_generations "
            "FROM architecture_runs ORDER BY run_id DESC LIMIT 1"
        ).fetchone()

        if not run_row:
            raise RuntimeError(f"No architecture_runs row found in DB: {db}")
        
        run_row_dict = dict(run_row)
        
        # Override the label to match the folder name to hide pipeline env-var leaks
        if not db_path and not repo_path:
            run_row_dict["repo_label"] = inferred_label
            run_row_dict["repo_display"] = inferred_label
            
        repo_label = run_row_dict["repo_label"]

        run_id = run_row["run_id"]

        boundaries = conn.execute(
            "SELECT boundary_commit_topo_id, boundary_commit_sig, cause_tag, magnitude, "
            "       snapshot_count, structural_count, incremental_count, distinct_commit_count, "
            "       dominant_snapshot_sig "
            "FROM architecture_boundaries "
            "WHERE run_id = ? "
            "ORDER BY boundary_commit_topo_id",
            (run_id,),
        ).fetchall()

        snapshots = conn.execute(
            "SELECT snapshot_sig, boundary_commit_sig, shape, shape_label, "
            "       is_current, is_dominant, lifespan_class, "
            "       total_commits, run_count, first_seen_topo_id, last_seen_topo_id, "
            "       first_seen_date, last_seen_date, longest_streak, "
            "       successive_commit_count, reappeared_commit_count, "
            "       operational_commit_count, development_commit_count, "
            "       effective_commits, share_of_generation, "
            "       selected_files, total_files, generator_version, generator_mode, size_bytes "
            "FROM architecture_snapshots "
            "WHERE run_id = ?",
            (run_id,),
        ).fetchall()

        commits = conn.execute(
            "SELECT snapshot_sig, topo_id, commit_sig, date, subject, role "
            "FROM architecture_commits "
            "WHERE run_id = ? "
            "ORDER BY topo_id",
            (run_id,),
        ).fetchall()

    snapshot_metas = {}
    for row in snapshots:
        sig = row["snapshot_sig"]
        # Prefer explicit file-count columns if present; fall back to lifespans when missing.
        selected_files = row["selected_files"] if "selected_files" in row.keys() else row.get("run_count", 0)
        total_files = row["total_files"] if "total_files" in row.keys() else row.get("total_commits", 0)

        # Dynamically calculate sizes for zero-state or cached lookups
        _size = row["size_bytes"] if ("size_bytes" in row.keys() and row["size_bytes"]) else 0
        if _size == 0 and sig:
            try:
                import glob
                import pathlib as _pl
                _matches = glob.glob(f"data/*/blueprints/*{sig[:7]}*.json")
                if _matches:
                    _size = _pl.Path(_matches[0]).stat().st_size
            except Exception:
                pass

        _mode_val = row["generator_mode"] if "generator_mode" in row.keys() else "programmatic"
        if not _mode_val and "blueprint_grade" in row.keys():
            _mode_val = row["blueprint_grade"]

        snapshot_metas[sig] = {
            "shape": row["shape"],
            "shape_label": human_shape_label(row["shape"]),
            "is_current": bool(row["is_current"]),
            "generated_at": run_row_dict.get("generated_at", ""),
            "mode": _mode_val or "programmatic",
            "generator_version": row["generator_version"] if "generator_version" in row.keys() else "archgen-v1",
            "size_bytes": int(_size or 0),
            "selected_files": int(selected_files or 0),
            "total_files": int(total_files or 0),
        }

    commit_rows_by_snapshot = {}
    
    for row in commits:
        sig = row["snapshot_sig"]
        role = row["role"] or "unmapped"
        run_idx = row["run_index"] if "run_index" in row.keys() else None

        normalized = {
            "sha": row["commit_sig"] or "",
            "subject": row["subject"] or "",
            "topo_id": row["topo_id"],
            "date": row["date"],
            "role": role,
            "run_index": run_idx
        }
        commit_rows_by_snapshot.setdefault(sig, []).append(normalized)

    from backend.services.architecture.models import CurrentBlueprint
    
    current_meta = None
    for row in snapshots:
        if row["is_current"]:
            current_meta = row
            break
    if current_meta is None and snapshots:
        current_meta = snapshots[-1]

    if current_meta is not None:
        current_meta_dict = dict(current_meta)

        selected_files = current_meta_dict.get("selected_files")
        if selected_files is None:
            selected_files = current_meta_dict.get("run_count")

        total_files = current_meta_dict.get("total_files")
        if total_files is None:
            total_files = current_meta_dict.get("total_commits")

        current = CurrentBlueprint(
            snapshot_sig=current_meta_dict["snapshot_sig"],
            generated_at=run_row_dict.get("generated_at", ""),
            generator_version="",
            mode="arch",
            shape=current_meta_dict["shape"],
            total_files=int(total_files or 0),
            selected_files=int(selected_files or 0),
        )
    else:
        current = CurrentBlueprint(
            snapshot_sig="",
            generated_at=str(run_row_dict.get("generated_at") or ""),
            generator_version="",
            mode="arch",
            shape="unknown",
            total_files=0,
            selected_files=0,
        )

    # Convert sqlite3.Row boundaries to dicts to pass down
    db_bounds_list = [dict(b) for b in boundaries]
    
    report = assemble_history_report(
        repo_label=run_row_dict["repo_label"],
        repo_display=run_row_dict["repo_display"],
        current=current,
        snapshot_metas=snapshot_metas,
        commit_rows_by_snapshot=commit_rows_by_snapshot,
        runs_by_sig={},  # DB rows natively have run_index, so grouping is implicit
        real_commit_count=run_row_dict["total_commits"],
        db_boundaries=db_bounds_list,
    )

    return report


def assemble_history_report(
    repo_label: str,
    repo_display: str,
    current: "CurrentBlueprint",
    snapshot_metas: dict[str, dict],
    commit_rows_by_snapshot: dict[str, list[dict]],
    runs_by_sig: dict,
    real_commit_count: int,
    db_boundaries: list[dict] = None,
) -> "HistoryReport":
    from backend.services.architecture.models import HistoryReport
    from backend.services.architecture.metrics import (
        _compute_snapshot_lifespan_metrics,
        _compute_snapshot_composition_metrics,
        _compute_snapshot_dominance_metrics,
        _assign_dominant_flags,
    )
    from backend.cli.arch_history.metrics import compute_generation_summaries
    
    entries_out = assemble_snapshot_entries(snapshot_metas, commit_rows_by_snapshot, runs_by_sig)
    
    # 1. Map generation IDs strictly based on chronological DB boundaries (Oldest First = Gen 1)
    if db_boundaries:
        sorted_bounds = sorted(db_boundaries, key=lambda b: b.get("boundary_commit_topo_id") or 0)
        for entry in entries_out:
            topo = entry.trigger.topo_id if entry.trigger and entry.trigger.topo_id is not None else 0
            assigned_gen = len(sorted_bounds)
            for idx, bound in enumerate(sorted_bounds, start=1):
                if (bound.get("boundary_commit_topo_id") or 0) >= topo:
                    assigned_gen = idx
                    break
            entry.generation = assigned_gen

        # 2. Assign relative intra-era generation_index to prevent UI compaction hallucinations
        from collections import defaultdict
        gen_groups = defaultdict(list)
        for e in entries_out:
            gen_groups[e.generation].append(e)
        for gen_id, gen_entries in gen_groups.items():
            gen_entries.sort(key=lambda e: e.trigger.topo_id if e.trigger and e.trigger.topo_id is not None else 0)
            for i, e in enumerate(gen_entries, start=0):
                e.generation_index = i

    # 3. Sort entries Chronologically (Oldest to Newest) because the UI's render loop 
    # internally applies `reversed(entries)` to execute a top-down Head -> 1 stream layout!
    entries_out.sort(key=lambda e: e.trigger.topo_id if e.trigger and e.trigger.topo_id is not None else 0, reverse=False)

    # 4. Compute accurate lifespan and metrics natively
    for entry in entries_out:
        entry.lifespan = _compute_snapshot_lifespan_metrics(entry)
        entry.composition = _compute_snapshot_composition_metrics(entry)

    generation_effective_totals = {}
    for entry in entries_out:
        effective = max(0, entry.lifespan.total_commits - entry.composition.operational_commit_count)
        generation_effective_totals[entry.generation] = generation_effective_totals.get(entry.generation, 0) + effective

    for entry in entries_out:
        entry.dominance = _compute_snapshot_dominance_metrics(
            entry, generation_effective_total=generation_effective_totals.get(entry.generation, 0)
        )

    _assign_dominant_flags(entries_out)
    
    # 5. Delegate Summary Calculations directly to our corrected metrics layer
    generation_summaries = compute_generation_summaries(entries_out, db_boundaries=db_boundaries)
    
    # 6. Synchronize Database Taxonomy Overwrite strings cleanly without side-effect metric mutations
    if db_boundaries:
        from backend.services.architecture.taxonomy import get_boundary_cause_label, normalize_cause_tag
        sorted_bounds = sorted(db_boundaries, key=lambda b: b.get("boundary_commit_topo_id") or 0)
        for idx, bound in enumerate(sorted_bounds, start=1):
            if idx in generation_summaries:
                tag = bound.get("cause_tag", "unknown")
                generation_summaries[idx].cause_tag = tag
                generation_summaries[idx].cause_label = get_boundary_cause_label(normalize_cause_tag(tag))
                
                bound_topo = bound.get("boundary_commit_topo_id")
                for e in entries_out:
                    if e.generation == idx and e.trigger and e.trigger.topo_id == bound_topo:
                        e.shape = tag
                        e.shape_label = generation_summaries[idx].cause_label

    return HistoryReport(
        repo_label=repo_label,
        repo_display=repo_display,
        total_commits=real_commit_count,
        total_blueprints=len(entries_out),
        total_generations=len(db_boundaries) if db_boundaries else 0,
        current=current,
        entries=entries_out,
        generation_summaries=generation_summaries,
    )

def assemble_snapshot_entries(snapshot_metas: dict, commit_rows_by_snapshot: dict, runs_by_sig: dict) -> list:
    from backend.services.architecture.models import SnapshotEntry, CommitRef
    entries = []
    
    for idx, (sig, meta) in enumerate(snapshot_metas.items(), start=1):
        commit_rows = commit_rows_by_snapshot.get(sig, [])
        trigger_row = next((r for r in commit_rows if r.get("role") == "trigger"), None)
        
        if not trigger_row and commit_rows:
            trigger_row = max([r for r in commit_rows if r.get("topo_id") is not None], key=lambda r: r.get("topo_id", 0), default=commit_rows[0])
            
        trigger_ref = None
        if trigger_row:
            trigger_ref = CommitRef(
                commit_sig=trigger_row.get("sha", ""),
                subject=trigger_row.get("subject", ""),
                topo_id=trigger_row.get("topo_id"),
                date=(trigger_row.get("date") or meta.get("generated_at", "")[:10])
            )
            
        successive_refs = [
            CommitRef(
                commit_sig=r.get("sha", ""),
                subject=r.get("subject", ""),
                topo_id=r.get("topo_id"),
                date=(r.get("date") or meta.get("generated_at", "")[:10])
            ) for r in commit_rows if r.get("role") == "successive"
        ]
        
        reappeared_refs = [
            CommitRef(
                commit_sig=r.get("sha", ""),
                subject=r.get("subject", ""),
                topo_id=r.get("topo_id"),
                date=(r.get("date") or meta.get("generated_at", "")[:10])
            ) for r in commit_rows if r.get("role") == "reappeared"
        ]
        
        reappeared_runs = {}
        for r, orig_row in zip(reappeared_refs, [row for row in commit_rows if row.get("role") == "reappeared"]):
            r_idx = orig_row.get("run_index", 0)
            reappeared_runs.setdefault(r_idx, []).append(r)
        
        entry = SnapshotEntry(
            generation=1,
            generation_index=idx,
            snapshot_sig=sig,
            shape=meta.get("shape", "leaf-only"),
            generator_version=meta.get("generator_version", "archgen-v1"),
            mode=meta.get("mode", "programmatic"),
            generated_at=meta.get("generated_at", ""),
            size_bytes=meta.get("size_bytes", 0),
            selected_files=meta.get("selected_files", 0),
            total_files=meta.get("total_files", 0),
            trigger=trigger_ref,
            successive_used_by=successive_refs,
            reappeared_runs=list(reappeared_runs.values()),
            is_current=meta.get("is_current", False),
            shape_label=meta.get("shape_label")
        )
        entries.append(entry)
    return entries
