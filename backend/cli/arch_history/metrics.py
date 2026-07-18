from __future__ import annotations
from backend.services.architecture.models import GenerationSummaryMetrics
from backend.services.architecture.taxonomy import get_shape_metadata

def compute_generation_summaries(entries: list, db_boundaries: list[dict] = None) -> dict[int, GenerationSummaryMetrics]:
    """
    Computes precise generation summaries by pairing localized snapshot entries
    with authoritative era spans provided straight by the SQLite database layer.
    """
    from collections import defaultdict
    summaries: dict[int, GenerationSummaryMetrics] = {}
    
    # 1. Group our processed snapshots by their absolute generation era ID
    grouped_entries = defaultdict(list)
    for e in entries:
        if e.generation is not None:
            grouped_entries[e.generation].append(e)

    # 2. Map metrics using the authoritative database boundary array ordering
    if db_boundaries:
        sorted_bounds = sorted(db_boundaries, key=lambda b: b.get("boundary_commit_topo_id") or 0)
        
        for idx, bound in enumerate(sorted_bounds, start=1):
            gen_entries = grouped_entries[idx]
            if not gen_entries:
                continue
                
            # Dynamically accumulate the true commit span across the structural boundary era
            true_era_span = sum((e.lifespan.total_commits if e.lifespan else 0) for e in gen_entries)
            
            # Find the dominant snapshot entry inside this generation group
            dominant_entry = max(gen_entries, key=lambda x: x.lifespan.total_commits if x.lifespan else 0, default=gen_entries[0])
            dom_sig = dominant_entry.snapshot_sig
            dom_lifespan = dominant_entry.lifespan.total_commits if dominant_entry and dominant_entry.lifespan else 0
            
            # Absolute share: Dominant Snapshot Lifespan / Dynamically Computed Era Span
            dom_share = (dom_lifespan / true_era_span) if true_era_span > 0 else 1.0
            
            from backend.services.architecture.taxonomy import get_boundary_magnitude
            struct_count = sum(1 for e in gen_entries if get_boundary_magnitude(e.shape) == "structural" or str(e.shape).lower() in ("head", "major:head"))
            snap_count = len(gen_entries)
            
            tag = bound.get("cause_tag", "unknown")
            
            summaries[idx] = GenerationSummaryMetrics(
                generation=idx,
                cause_tag=tag,
                cause_label=get_shape_metadata(tag).get("label", "Implementation Refinement"),
                generation_distinct_commit_count=true_era_span,
                snapshot_count=snap_count,
                structural_count=struct_count,
                incremental_count=snap_count - struct_count,
                dominant_snapshot_sig=dom_sig,
                dominant_effective_commits=dom_lifespan,
                dominant_share_of_generation=dom_share,
                repeated_treesig_count=sum(1 for e in gen_entries if e.lifespan and e.lifespan.run_count > 1)
            )
    return summaries
