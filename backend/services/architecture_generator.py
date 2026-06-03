#!/usr/bin/env python3
"""
Architecture context generation and freshness gate for CommitMatrix.

Facade module:
- exposes the stable public API used by parser/orchestrators
- delegates storage concerns to architecture_storage
- delegates tree analysis and stub generation to architecture_analysis
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any
import json

from backend.services.parser_config import (
    MATRIX_ARCH_ENABLED,
    MATRIX_ARCH_GENERATOR_VERSION,
)
from backend.services.architecture_storage import (
    load_existing_blueprint as _load_existing_blueprint,
    save_blueprint_and_meta as _save_blueprint_and_meta,
)
from backend.services.architecture_analysis import (
    build_architecture_prompt_context as _build_architecture_prompt_context,
    build_architecture_prompt_context_at_commit as _build_architecture_prompt_context_at_commit,
    call_model_with_retry_stub as _call_model_with_retry_stub,
    classify_change_shape as _classify_change_shape,
    compute_tree_signature as _compute_tree_signature,
    compute_tree_signature_for_commit as _compute_tree_signature_for_commit,
    select_files_for_blueprint as _select_files_for_blueprint,
    select_files_for_blueprint_at_commit as _select_files_for_blueprint_at_commit,
    validate_architecture_markdown as _validate_architecture_markdown,
)
from backend.utils.git_ops import list_tree_files_at_commit


class ArchStatus(str, Enum):
    READY = "READY"
    STALE_APPROVED = "STALE_APPROVED"
    FAILED = "FAILED"


@dataclass
class ArchitectureResult:
    status: ArchStatus
    blueprint_path: Optional[Path] = None
    metadata: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None


def generate_architecture_blueprint(repo_path: str, tree_sig: str, commit_sha: str | None = None) -> ArchitectureResult:
    repo = Path(repo_path)

    if commit_sha:
        selected_files = _select_files_for_blueprint_at_commit(repo_path, commit_sha)
        context = _build_architecture_prompt_context_at_commit(repo_path, commit_sha, tree_sig, selected_files)
        total_files = len(list_tree_files_at_commit(repo_path, commit_sha))
        top_level_dirs = context.get("top_level_dirs", [])
    else:
        selected_files = _select_files_for_blueprint(repo_path)
        context = _build_architecture_prompt_context(repo_path, tree_sig, selected_files)
        total_files = 0
        for p in repo.rglob("*"):
            if p.is_file():
                total_files += 1
        top_level_dirs = context.get("top_level_dirs", [])

    content, retry_count = _call_model_with_retry_stub(context)
    repo_name = context.get("repo_name", "unknown-repo")
    content, is_valid = _validate_architecture_markdown(content, repo_name)

    change_summary = {
        "selected_files_count": len(selected_files),
        "total_files": total_files,
        "mode": "stub-valid" if is_valid else "stub-invalid",
        "change_shape": "pending",
    }

    _, _, meta_prev = _load_existing_blueprint(repo_path)

    md_path, meta_path, meta = _save_blueprint_and_meta(
        repo_path=repo_path,
        content=content,
        tree_signature=tree_sig,
        model_name=MATRIX_ARCH_GENERATOR_VERSION,
        selected_files=selected_files,
        truncation_mode="stub",
        retry_count=retry_count,
        file_count=len(selected_files),
        top_level_dirs=top_level_dirs,
        change_summary=change_summary,
        commit_sha=commit_sha,
    )

    try:
        shape = _classify_change_shape(meta_prev, meta)
        meta.setdefault("change_summary", {})["change_shape"] = shape
        meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True), encoding="utf-8")

        sig_prefix = tree_sig[:16]
        if sig_prefix:
            versions_dir = meta_path.parent / "architecture_versions"
            snapshot_meta_path = versions_dir / f"arch-{sig_prefix}.meta.json"
            if snapshot_meta_path.exists():
                snapshot_meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True), encoding="utf-8")
    except Exception:
        pass

    return ArchitectureResult(
        status=ArchStatus.READY,
        blueprint_path=md_path,
        metadata=meta,
        reason="stub architecture blueprint generated (no LLM yet)",
    )


def build_arch_gen_trail(versions_dir: Path, current_gen: int | None, max_entries: int = 5) -> str:
    import json as j

    if not versions_dir.exists():
        return ""

    snapshots = sorted(versions_dir.glob("arch-*.md"), reverse=True)
    if not snapshots:
        return ""

    lines: list[str] = []
    current_gen_n = 1
    entries: list[tuple[int, str, str, str, str]] = []

    for idx, snap in enumerate(sorted(snapshots)):
        sidecar = snap.with_suffix(".meta.json")
        shape = "unknown"
        gen_ver = ""
        mode = ""
        gen_at = ""
        if sidecar.exists():
            try:
                m = j.loads(sidecar.read_text(encoding="utf-8"))
                shape = (m.get("change_summary") or {}).get("change_shape", "unknown")
                gen_ver = m.get("generator_version", "")
                mode = (m.get("change_summary") or {}).get("mode", "")
                gen_at = (m.get("generated_at") or "")[:10]
            except Exception:
                pass

        if idx > 0 and not shape.startswith("leaf-only"):
            current_gen_n += 1

        entries.append((current_gen_n, shape, gen_at, gen_ver, mode))

    entries_desc = list(reversed(entries))[:max_entries]
    if not entries_desc:
        return ""

    lines.append("Architecture Generation Trail (latest → oldest):")
    for gen_n, shape, gen_at, gen_ver, mode in entries_desc:
        marker = " [current]" if gen_n == current_gen else ""
        lines.append(f"- Gen #{gen_n}: {shape} · {gen_at} · {gen_ver} · mode={mode}{marker}")
    return "\n".join(lines)


def ensure_fresh_architecture_context(repo_path: str, commit_sha: str | None = None) -> ArchitectureResult:
    if not MATRIX_ARCH_ENABLED:
        return ArchitectureResult(
            status=ArchStatus.READY,
            blueprint_path=None,
            metadata=None,
            reason="architecture gating disabled by MATRIX_ARCH_ENABLED",
        )

    tree_sig = _compute_tree_signature_for_commit(repo_path, commit_sha) if commit_sha else _compute_tree_signature(repo_path)
    md_path, _, meta = _load_existing_blueprint(repo_path)

    if md_path.exists() and meta and meta.get("tree_signature") == tree_sig:
        if commit_sha:
            existing_commit = meta.get("commit_sha")
            if existing_commit == commit_sha:
                return ArchitectureResult(
                    status=ArchStatus.READY,
                    blueprint_path=md_path,
                    metadata=meta,
                    reason="existing architecture blueprint is current",
                )
        else:
            if not meta.get("commit_sha"):
                return ArchitectureResult(
                    status=ArchStatus.READY,
                    blueprint_path=md_path,
                    metadata=meta,
                    reason="existing architecture blueprint is current",
                )

    return generate_architecture_blueprint(repo_path, tree_sig, commit_sha=commit_sha)
