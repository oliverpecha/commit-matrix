from __future__ import annotations
from typing import Tuple
from backend.services.pipeline.work_item import CommitWorkItem
from backend.utils.commit_heuristics import extract_heuristics
from backend.services.db.reader import get_commit_arch_context

def extract_commit_sha(commit_parts: tuple) -> str:
    return str(commit_parts[0]).strip()

def prepare_commit_work_item(topo_id: int, commit_parts: tuple, total_unscanned: int, processed_count: int, ordinal_in_window: int, model_name: str, rubric_path: str, repo_label: str, db_path: str) -> Tuple[CommitWorkItem, dict]:
    commit_sha = extract_commit_sha(commit_parts)
    subject = str(commit_parts[3]) if len(commit_parts) > 3 else ""
    diff = str(commit_parts[4]) if len(commit_parts) > 4 else ""

    heuristics = extract_heuristics(subject, diff)

    arch_context, cause_tag, generation, snapshot_sig, role = get_commit_arch_context(repo_label=repo_label, topo_id=topo_id, db_path=db_path)

    arch_meta = {
        "cause_tag": cause_tag, "generation": generation, "architecture_context": arch_context or "",
        "commit_sha": commit_sha, "topo_id": topo_id, "snapshot_sig": snapshot_sig, "role": role,
        "heuristics": heuristics
    }

    work_item = CommitWorkItem(
        topo_id=topo_id, commit_parts=commit_parts, total_unscanned=total_unscanned,
        processed_count=processed_count, ordinal_in_window=ordinal_in_window, model_name=model_name,
        rubric_path=rubric_path, arch_context=arch_context or "", arch_tree_signature=snapshot_sig,
        arch_gen=generation, arch_meta=arch_meta,
    )
    return work_item, arch_meta
