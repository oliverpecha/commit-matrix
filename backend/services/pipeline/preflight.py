from __future__ import annotations

from backend.services.pipeline.work_item import CommitWorkItem


def extract_commit_sha(commit_parts: tuple) -> str:
    hash_full = commit_parts[0]
    return str(hash_full).strip()


def prepare_commit_work_item(
    topo_id: int,
    commit_parts: tuple,
    total_unscanned: int,
    processed_count: int,
    ordinal_in_window: int,
    model_name: str,
    rubric_path: str,
    tracker,
):
    commit_sha = extract_commit_sha(commit_parts)
    arch_state, arch_meta = tracker.resolve_for_commit(commit_sha, topo_id=topo_id)

    arch_context = (
        arch_meta.get("architecture_context")
        or arch_meta.get("context")
        or ""
    )

    work_item = CommitWorkItem(
        topo_id=topo_id,
        commit_parts=commit_parts,
        total_unscanned=total_unscanned,
        processed_count=processed_count,
        ordinal_in_window=ordinal_in_window,
        model_name=model_name,
        rubric_path=rubric_path,
        arch_context=arch_context,
        arch_tree_signature=arch_state.signature,
        arch_gen=arch_state.gen,
        arch_meta=arch_meta or {},
    )
    return work_item, arch_state
