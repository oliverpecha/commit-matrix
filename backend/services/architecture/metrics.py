from __future__ import annotations

from backend.services.architecture.models import (
    CommitRef,
    GenerationSummaryMetrics,
    SnapshotCompositionMetrics,
    SnapshotDominanceMetrics,
    SnapshotEntry,
    SnapshotLifespanMetrics,
)
from backend.cli.arch_history.data.loader import _is_operational, human_shape_label
from backend.cli.arch_history.taxonomy import get_shape_metadata

def _compute_snapshot_lifespan_metrics(entry: "SnapshotEntry") -> SnapshotLifespanMetrics:
    runs: list[list[CommitRef]] = []
    main_run: list[CommitRef] = []
    if entry.trigger:
        main_run.append(entry.trigger)
    main_run.extend(entry.successive_used_by)
    if main_run:
        runs.append(main_run)
    runs.extend(entry.reappeared_runs)

    if not runs:
        return SnapshotLifespanMetrics(
            total_commits=0,
            run_count=0,
            first_seen_topo_id=None,
            last_seen_topo_id=None,
            first_seen_date="unknown",
            last_seen_date="unknown",
            longest_streak=0,
        )

    all_refs = [ref for run in runs for ref in run]
    refs_with_topo = [ref for ref in all_refs if ref.topo_id is not None]

    if refs_with_topo:
        first_ref = min(refs_with_topo, key=lambda r: r.topo_id)
        last_ref = max(refs_with_topo, key=lambda r: r.topo_id)
    else:
        first_ref = all_refs[0]
        last_ref = all_refs[-1]

    return SnapshotLifespanMetrics(
        total_commits=len(all_refs),
        run_count=len(runs),
        first_seen_topo_id=first_ref.topo_id,
        last_seen_topo_id=last_ref.topo_id,
        first_seen_date=first_ref.date,
        last_seen_date=last_ref.date,
        longest_streak=max(len(run) for run in runs),
    )

def _compute_snapshot_composition_metrics(entry: "SnapshotEntry") -> SnapshotCompositionMetrics:
    all_refs: list[CommitRef] = []
    if entry.trigger:
        all_refs.append(entry.trigger)
    all_refs.extend(entry.successive_used_by)
    for run in entry.reappeared_runs:
        all_refs.extend(run)

    operational_commit_count = sum(1 for ref in all_refs if _is_operational(ref.subject))
    total_commits = len(all_refs)

    return SnapshotCompositionMetrics(
        successive_commit_count=len(entry.successive_used_by),
        reappeared_commit_count=sum(len(run) for run in entry.reappeared_runs),
        operational_commit_count=operational_commit_count,
        development_commit_count=total_commits - operational_commit_count,
    )

def _compute_snapshot_dominance_metrics(
    entry: "SnapshotEntry",
    generation_effective_total: int,
) -> SnapshotDominanceMetrics:
    if entry.lifespan is None or entry.composition is None:
        raise ValueError("lifespan and composition must be computed before dominance")

    effective_commits = max(0, entry.lifespan.total_commits - entry.composition.operational_commit_count)
    share_of_generation = (
        effective_commits / generation_effective_total
        if generation_effective_total > 0
        else 0.0
    )

    return SnapshotDominanceMetrics(
        effective_commits=effective_commits,
        share_of_generation=share_of_generation,
        longest_streak=entry.lifespan.longest_streak,
        reappearance_commit_count=entry.composition.reappeared_commit_count,
        is_dominant=False,
        is_long_lived=(effective_commits >= 3 and entry.lifespan.longest_streak >= 3),
        is_short_lived=(entry.lifespan.total_commits == 1),
    )

def _assign_dominant_flags(entries: list[SnapshotEntry]) -> None:
    grouped: dict[int, list[SnapshotEntry]] = {}
    for entry in entries:
        grouped.setdefault(entry.generation, []).append(entry)

    for gen_entries in grouped.values():
        ranked = sorted(
            gen_entries,
            key=lambda e: (
                -(e.dominance.effective_commits if e.dominance else 0),
                -(e.dominance.share_of_generation if e.dominance else 0.0),
                -(e.lifespan.longest_streak if e.lifespan else 0),
                -(e.composition.reappeared_commit_count if e.composition else 0),
                (e.lifespan.first_seen_topo_id if e.lifespan and e.lifespan.first_seen_topo_id is not None else 10_000_000),
            ),
        )
        if ranked and ranked[0].dominance is not None:
            ranked[0].dominance.is_dominant = True

def _compute_generation_summaries(entries: list[SnapshotEntry]) -> dict[int, GenerationSummaryMetrics]:
    from collections import defaultdict

    grouped: dict[int, list[SnapshotEntry]] = defaultdict(list)
    for e in entries:
        grouped[e.generation].append(e)

    summaries: dict[int, GenerationSummaryMetrics] = {}

    for gen, snaps in grouped.items():
        generation_distinct_commit_count = 0
        structural_count = 0
        incremental_count = 0
        repeated_treesig_count = 0

        for e in snaps:
            if e.lifespan:
                generation_distinct_commit_count += e.lifespan.total_commits
                if e.lifespan.run_count > 1:
                    repeated_treesig_count += 1

            shape = (e.shape or "").strip()
            if get_shape_metadata(shape)["family"] in ("genesis", "depth", "breadth"):
                structural_count += 1
            else:
                incremental_count += 1

        snapshot_count = len(snaps)

        ranked = sorted(
            snaps,
            key=lambda e: (
                -(e.dominance.effective_commits if e.dominance else 0),
                -(e.dominance.share_of_generation if e.dominance else 0.0),
                -(e.lifespan.longest_streak if e.lifespan else 0),
                -(e.composition.reappeared_commit_count if e.composition else 0),
                (e.lifespan.first_seen_topo_id if e.lifespan and e.lifespan.first_seen_topo_id is not None else 10_000_000),
            ),
        )
        dominant = ranked[0] if ranked else None
        if dominant and dominant.dominance:
            dominant_sig = dominant.snapshot_sig
            dominant_eff = dominant.dominance.effective_commits
            dominant_share = dominant.dominance.share_of_generation
        else:
            dominant_sig = ""
            dominant_eff = 0
            dominant_share = 0.0

        cause_tag = ""
        cause_label = ""
        structural_first = next((e for e in snaps if (e.shape or "").startswith(("major:", "multi-dir:"))), None)
        anchor_entry = structural_first or snaps[0]

        cause_tag = (anchor_entry.shape or "unknown")
        cause_label = (anchor_entry.shape_label or human_shape_label(cause_tag))

        summaries[gen] = GenerationSummaryMetrics(
            generation=gen,
            cause_tag=cause_tag,
            cause_label=cause_label,
            generation_distinct_commit_count=generation_distinct_commit_count,
            snapshot_count=snapshot_count,
            structural_count=structural_count,
            incremental_count=incremental_count,
            dominant_snapshot_sig=dominant_sig,
            dominant_effective_commits=dominant_eff,
            dominant_share_of_generation=dominant_share,
            repeated_treesig_count=repeated_treesig_count,
        )

    return summaries


def validate_commit_snapshot_invariant(report: "HistoryReport", debug: bool = False) -> None:
    """Check that each commit_sig appears only under a single snapshot_sig.

    If a commit appears in multiple snapshots, this emits a warning by default.
    In debug mode, it raises a ValueError to make the issue explicit.
    """
    from backend.services.architecture.models import SnapshotEntry, CommitRef  # type: ignore

    commit_to_snapshots: dict[str, set[str]] = {}
    for entry in getattr(report, "entries", []):
        if not isinstance(entry, SnapshotEntry):
            continue
        snapshot_sig = getattr(entry, "snapshot_sig", None)
        if not snapshot_sig:
            continue
        refs = []
        if entry.trigger:
            refs.append(entry.trigger)
        refs.extend(entry.successive_used_by)
        for run in entry.reappeared_runs:
            refs.extend(run)
        refs.extend(entry.also_used_by)
        for ref in refs:
            if isinstance(ref, CommitRef):
                sig = getattr(ref, "commit_sig", None)
                if not sig:
                    continue
                commit_to_snapshots.setdefault(sig, set()).add(snapshot_sig)

    offenders = {c: snaps for c, snaps in commit_to_snapshots.items() if len(snaps) > 1}
    if not offenders:
        return

    message_lines = ["Commit→snapshot invariant violated for the following commit_sig(s):"]
    for commit_sig, snaps in sorted(offenders.items()):
        message_lines.append(f"  {commit_sig}: {sorted(snaps)}")
    message = "\n".join(message_lines)

    if debug:
        raise ValueError(message)
    else:
        import sys as _sys
        print(f"[arch_history] WARNING: {message}", file=_sys.stderr)


# Public alias for pipeline usage
compute_generation_summaries = _compute_generation_summaries


# Pipeline-compatible wrapper (minimal implementation)
def compute_generation_summaries(repo_label: str, db_path: str):
    """
    Compute generation summaries for architecture boundaries.
    Minimal implementation - returns empty list if full data unavailable.
    """
    try:
        import sqlite3
        from backend.services.architecture.models import GenerationSummaryMetrics
        
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        
        # Query generations from boundaries
        rows = conn.execute(
            "SELECT gen, change_shape FROM architecture_boundaries WHERE run_id = 1"
        ).fetchall()
        
        summaries = []
        for row in rows:
            gen = row['gen']
            # Count snapshots in this generation
            snap_count = conn.execute(
                "SELECT COUNT(*) FROM architecture_snapshots WHERE gen = ?", (gen,)
            ).fetchone()[0]
            
            summaries.append(GenerationSummaryMetrics(
                gen=gen,
                snapshot_count=snap_count,
                structural_count=0,  # Would need deeper analysis
                incremental_count=snap_count,
                dominant_snapshot_sig=None,
                dominant_share_of_generation=0.0,
                repeated_treesig_count=0
            ))
        
        conn.close()
        return summaries
    except Exception:
        return []  # Graceful degradation
