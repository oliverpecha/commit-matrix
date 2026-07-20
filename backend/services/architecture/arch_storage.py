from __future__ import annotations

from pathlib import Path
from typing import Optional
import datetime
import json
import os

from backend.services.pipeline.pipeline_config import (
    HOST_REPO_NAME,
    MATRIX_ARCH_GENERATOR_VERSION,
)


def repo_id_from_path(repo_path: str) -> str:
    if HOST_REPO_NAME:
        return HOST_REPO_NAME

    base = os.path.basename(os.path.abspath(repo_path))
    return base or "target_repo"


def architecture_paths(repo_path: str) -> Path:
    repo_id = repo_id_from_path(repo_path)
    data_dir = Path("data") / repo_id
    data_dir.absolute().mkdir(parents=True, exist_ok=True)
    md_path = data_dir / f"{repo_id}_current_arch_blueprint.md"
    return md_path


def load_existing_blueprint(repo_path: str) -> tuple[Path, Optional[dict]]:
    md_path = architecture_paths(repo_path)
    return md_path, None


def save_blueprint_and_meta(
    repo_path: str,
    content: str,
    tree_signature: str,
    model_name: str,
    selected_files: list[str],
    truncation_mode: str,
    retry_count: int,
    file_count: int,
    top_level_dirs: list[str],
    change_summary: dict | None = None,
    commit_sha: str | None = None,
    topo_id: int | None = None,
) -> tuple[Path, dict]:
    md_path = architecture_paths(repo_path)
    # In retrospective mode, only write current blueprint for the first commit (HEAD)
    # In chronological mode, overwrite each time (last commit = current)
    import os as _os
    _queue_order = _os.environ.get("MATRIX_QUEUE_ORDER", "retrospective").strip().lower()
    if _queue_order == "retrospective":
        if not md_path.exists():
            md_path.write_text(content, encoding="utf-8")
    else:
        md_path.write_text(content, encoding="utf-8")

    meta = {
        "generated_at": datetime.datetime.now(datetime.UTC).isoformat() + "Z",
        "tree_signature": tree_signature,
        "generator_version": MATRIX_ARCH_GENERATOR_VERSION,
        "model": model_name,
        "prompt_contract": MATRIX_ARCH_GENERATOR_VERSION,
        "selected_files": selected_files,
        "truncation_mode": truncation_mode,
        "retry_count": retry_count,
        "file_count": file_count,
        "top_level_dirs": top_level_dirs,
        "change_summary": change_summary or {},
    }
    if commit_sha:
        meta["commit_sha"] = commit_sha
    if topo_id is not None:
        meta["topo_id"] = topo_id
        meta["commit_index"] = topo_id

    try:
        sig_prefix = tree_signature[:16]
        if sig_prefix and not tree_signature.startswith("git-error"):
            versions_dir = meta_path.parent / "past_blueprints"
            versions_dir.mkdir(exist_ok=True)
            snapshot_path = versions_dir / f"arch_snapshot-{sig_prefix}.md"
            if not snapshot_path.exists():
                snapshot_path.write_text(content, encoding="utf-8")
    except Exception:
        pass

    return md_path, meta
