from backend.services.architecture.taxonomy import get_shape_metadata
from types import SimpleNamespace

class SafeNamespace(SimpleNamespace):
    def __getattr__(self, item):
        return ""

def compute_generation_summaries(entries: list, b_topo_map: dict, b_gen_map: dict) -> dict:
    generation_summaries = {}
    grouped_entries = {}
    for e in entries:
        grouped_entries.setdefault(e.generation, []).append(e)

    for gen_id, gen_entries in grouped_entries.items():
        matching_topo = next((t for t, b in b_topo_map.items() if b_gen_map.get(t) == gen_id), None)
        b_row = b_topo_map.get(matching_topo, {}) if matching_topo else {}
        
        raw_tag = str(b_row.get("cause_tag") or "default").strip()
        meta = get_shape_metadata(raw_tag)
        
        distinct_commits = sum(e.lifespan.total_commits for e in gen_entries)
        snap_count = len(gen_entries)
        struct_count = sum(1 for e in gen_entries if e.is_boundary or str(e.shape).startswith("major:") or str(e.shape).startswith("multi-dir:"))
        incr_count = snap_count - struct_count
        
        dominant_entry = max(gen_entries, key=lambda x: x.lifespan.total_commits) if gen_entries else None
        dom_eff = dominant_entry.lifespan.total_commits if dominant_entry else 1
        dom_sig = dominant_entry.snapshot_sig if dominant_entry else ""
        dom_share = (dom_eff / distinct_commits) if distinct_commits > 0 else 1.0

        generation_summaries[gen_id] = SafeNamespace(
            cause_tag=raw_tag,
            cause_label=meta.get("label", "Unknown Shift"),
            dominant_share_of_generation=dom_share,
            dominant_snapshot_sig=dom_sig,
            dominant_effective_commits=dom_eff,
            generation_distinct_commit_count=distinct_commits,
            snapshot_count=snap_count,
            repeated_treesig_count=int(b_row.get("repeated_treesig_count") or 0),
            incremental_count=incr_count,
            structural_count=struct_count,
        )

    return generation_summaries
