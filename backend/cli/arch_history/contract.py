from __future__ import annotations

from typing import Dict, List, Optional

from backend.services.architecture.models import (
    BoundaryInfo,
    BoundaryScope,
    CurrentBlueprint,
    GenerationSummaryMetrics,
    HistoryReport,
    SnapshotEntry,
    CommitRef,
    DisplacedSnapshot,
)
from backend.services.architecture.taxonomy import (
    normalize_cause_tag,
    get_boundary_cause_label,
    get_boundary_magnitude,
)
from backend.services.architecture.metrics import _compute_generation_summaries
# Legacy import removed



CONTRACT_VERSION = "1.0"

BOOLEAN_BADGE_RULES: List[tuple[str, str]] = [
    ("is_current", "current"),
    ("is_dominant", "dominant"),
]

LIFESPAN_BADGE_MAP: Dict[str, str] = {
    "long": "long-lived",
    "short": "short-lived",
}


def _derive_badges(flags: Dict[str, object]) -> List[str]:
    badges: List[str] = []
    for token, key in BOOLEAN_BADGE_RULES:
        if flags.get(key, False):
            badges.append(token)
    lc = flags.get("lifespan_class", "standard")
    if lc in LIFESPAN_BADGE_MAP:
        badges.append(LIFESPAN_BADGE_MAP[lc])
    return badges


def _build_snapshot_flags(entry: SnapshotEntry) -> Dict[str, object]:
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
        "is_current": entry.is_current,
        "is_dominant": dom.is_dominant if dom else False,
        "lifespan_class": lifespan_class,
    }


def _serialize_commit_ref(ref: CommitRef) -> Dict[str, object]:
    return {
        "commit_sig": ref.commit_sig,
        "topo_id": ref.topo_id,
        "date": ref.date,
        "subject": ref.subject,
    }


def _serialize_snapshot_entry(entry: SnapshotEntry) -> Dict[str, object]:
    flags = _build_snapshot_flags(entry)
    return {
        "generation": entry.generation,
        "generation_index": entry.generation_index,
        "snapshot_sig": entry.snapshot_sig,
        "shape": entry.shape,
        "shape_label": entry.shape_label,
        "generator_version": entry.generator_version,
        "mode": entry.mode,
        "generated_at": entry.generated_at,
        "size_bytes": entry.size_bytes,
        "selected_files": entry.selected_files,
        "total_files": entry.total_files,
        "flags": flags,
        "badges": _derive_badges(flags),
    }


def _serialize_boundary(boundary: Optional[BoundaryInfo]) -> Optional[Dict[str, object]]:
    if boundary is None:
        return None

    displaced = boundary.displaced
    displaced_payload: Optional[Dict[str, object]]
    if displaced is not None:
        displaced_payload = {
            "snapshot_sig": displaced.snapshot_sig,
            "lifespan_class": displaced.lifespan_class,
            "was_dominant": displaced.was_dominant,
        }
    else:
        displaced_payload = None

    scope = boundary.scope
    return {
        "cause_tag": boundary.cause_tag,
        "cause_label": boundary.cause_label,
        "magnitude": boundary.magnitude,
        "commit": _serialize_commit_ref(boundary.commit) if boundary.commit else None,
        "scope": {
            "top_level_dirs": scope.top_level_dirs,
            "file_count": scope.file_count,
        }
        if scope
        else None,
        "displaced": displaced_payload,
    }


def _serialize_generation_summary(
    summary: GenerationSummaryMetrics, boundary: Optional[BoundaryInfo]
) -> Dict[str, object]:
    tag = normalize_cause_tag(summary.cause_tag)
    result: Dict[str, object] = {
        "generation": summary.generation,
        "cause_tag": tag,
        "cause_label": get_boundary_cause_label(tag),
        "generation_distinct_commit_count": summary.generation_distinct_commit_count,
        "snapshot_count": summary.snapshot_count,
        "structural_count": summary.structural_count,
        "incremental_count": summary.incremental_count,
        "dominant_snapshot_sig": summary.dominant_snapshot_sig,
        "dominant_effective_commits": summary.dominant_effective_commits,
        "dominant_share_of_generation": summary.dominant_share_of_generation,
        "repeated_tree_sig_count": summary.repeated_tree_sig_count,
    }
    serialized_boundary = _serialize_boundary(boundary)
    if serialized_boundary is not None:
        result["boundary"] = serialized_boundary
    return result


def _compute_generation_boundaries(
    entries: List[SnapshotEntry], generation_summaries: Dict[int, GenerationSummaryMetrics]
) -> Dict[int, BoundaryInfo]:
    # This is a simplified boundary computation placeholder adapted from orchestrator logic.
    boundaries: Dict[int, BoundaryInfo] = {}
    for gen, summary in generation_summaries.items():
        # Use the last entry of the generation as the boundary anchor.
        gen_entries = [e for e in entries if e.generation == gen]
        if not gen_entries:
            continue
        anchor_entry = gen_entries[-1]
        cause_tag = summary.cause_tag
        cause_label = get_boundary_cause_label(cause_tag)
        magnitude = get_boundary_magnitude(cause_tag)
        commit = anchor_entry.trigger
        sidecar = _load_snapshot_meta(anchor_entry.snapshot_sig)
        scope = None
        if sidecar:
            scope = BoundaryScope(
                top_level_dirs=sidecar.get("top_level_dirs") or [],
                file_count=sidecar.get("file_count")
                or (sidecar.get("changes_summary") or {}).get("total_files")
                or 0,
            )

        displaced: Optional[DisplacedSnapshot]
        if len(gen_entries) >= 2:
            prev = gen_entries[-2]
            lc = "standard"
            dom = prev.dominance
            if dom:
                if dom.is_long_lived:
                    lc = "long"
                elif dom.is_short_lived:
                    lc = "short"
            displaced = DisplacedSnapshot(
                snapshot_sig=prev.snapshot_sig,
                lifespan_class=lc,
                was_dominant=dom.is_dominant if dom else False,
            )
        else:
            displaced = None

        boundaries[gen] = BoundaryInfo(
            cause_tag=cause_tag,
            cause_label=cause_label,
            magnitude=magnitude,
            commit=commit,
            scope=scope,
            displaced=displaced,
        )
    return boundaries


def serialize_history_report_to_contract(report: HistoryReport) -> Dict[str, object]:
    generation_summaries = report.generation_summaries or _compute_generation_summaries(
        list(report.entries)
    )
    boundaries = _compute_generation_boundaries(list(report.entries), generation_summaries)

    current = report.current
    current_payload = {
        "snapshot_sig": current.snapshot_sig,
        "generated_at": current.generated_at,
        "generator_version": current.generator_version,
        "mode": current.mode,
        "shape": current.shape,
        "total_files": current.total_files,
        "selected_files": current.selected_files,
    }

    return {
        "contract_version": CONTRACT_VERSION,
        "repo_label": report.repo_label,
        "repo_display": report.repo_display,
        "total_commits": report.total_commits,
        "total_blueprints": report.total_blueprints,
        "total_generations": report.total_generations,
        "current": current_payload,
        "entries": [_serialize_snapshot_entry(e) for e in report.entries],
        "generation_summaries": [
            _serialize_generation_summary(g, boundaries.get(g.generation))
            for g in generation_summaries.values()
        ],
    }
