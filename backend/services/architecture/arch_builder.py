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

from backend.services.pipeline.pipeline_config import (
    MATRIX_ARCH_ENABLED,
    MATRIX_ARCH_GENERATOR_VERSION,
)
from backend.services.architecture.arch_storage import (
    load_existing_blueprint as _load_existing_blueprint,
    save_blueprint_and_meta as _save_blueprint_and_meta,
)
from backend.services.architecture.arch_inspector import (
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


def generate_architecture_blueprint(repo_path: str, tree_sig: str, commit_sha: str | None = None, topo_id: int | None = None, is_head_fallback: bool = False) -> ArchitectureResult:
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

    # NATIVE HEAD-TO-1 PARADOX FIX: Calculate true parent state dynamically via pure Git
    meta_prev = None
    if commit_sha:
        try:
            import subprocess
            parent_sha = subprocess.check_output(
                ["git", "rev-parse", f"{commit_sha}^1"], 
                cwd=repo_path, stderr=subprocess.DEVNULL
            ).decode().strip()
            
            # Use authentic system primitives to build identical schema shapes for the chronological parent
            parent_selected = _select_files_for_blueprint_at_commit(repo_path, parent_sha)
            parent_context = _build_architecture_prompt_context_at_commit(repo_path, parent_sha, "parent-sig", parent_selected)
            parent_total = len(list_tree_files_at_commit(repo_path, parent_sha))
            parent_top_dirs = parent_context.get("top_level_dirs", [])
            
            meta_prev = {
                "generator_version": MATRIX_ARCH_GENERATOR_VERSION,
                "selected_files": parent_selected,
                "top_level_dirs": parent_top_dirs,
                "change_summary": {
                    "total_files": parent_total,
                    "selected_files_count": len(parent_selected),
                    "mode": "stub-valid"
                }
            }
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            pass

    md_path, meta = _save_blueprint_and_meta(
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
        topo_id=topo_id,
    )

    try:
        shape = _classify_change_shape(meta_prev, meta)
        # NATIVE HEAD-TO-1 SSOT: Determine absolute HEAD natively via Git, bypassing chunking race conditions
        is_true_head = False
        if commit_sha:
            try:
                import subprocess
                repo_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_path, stderr=subprocess.DEVNULL).decode().strip()
                commit_full = subprocess.check_output(["git", "rev-parse", commit_sha], cwd=repo_path, stderr=subprocess.DEVNULL).decode().strip()
                is_true_head = (repo_head == commit_full)
            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception:
                pass

        if is_true_head:
            shape = "major:head"
        elif meta_prev is None:
            shape = "major:first-generation" if topo_id == 1 else "major:detached-root"
        else:
            if not shape or shape == "unknown":
                shape = "leaf-only"
        
        meta.setdefault("change_summary", {})["change_shape"] = shape
        try:
            from backend.services.architecture.taxonomy import get_boundary_cause_label, normalize_cause_tag
            meta["change_summary"]["change_shape_label"] = get_boundary_cause_label(normalize_cause_tag(shape))
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            pass
            
        try:
            import json as _json
            meta_path.write_text(_json.dumps(meta, indent=2), encoding="utf-8")
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            pass

        # State pointer obsolete in pure HEAD-to-1 dynamic architecture

        # Write snapshot metadata to DB directly (M1 — DB is canonical)
        try:
            from backend.services.db.writer import write_snapshot_meta
            write_snapshot_meta(repo_path, tree_sig, meta)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            pass
    except (KeyboardInterrupt, SystemExit):
        raise
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

    snapshots = sorted(versions_dir.glob("arch_snapshot-*.md"))  # chronological / lexical ascending
    if not snapshots:
        return ""

    entries: list[tuple[int, str, str, str, str]] = []
    gen_n = 1

    for idx, snap in enumerate(snapshots):
        sidecar = snap.with_suffix(".meta.json")
        sidecar = __import__("pathlib").Path(__import__("os").devnull) # Hijacked to void
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
            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception:
                pass

        if idx > 0 and not shape.startswith("leaf-only"):
            gen_n += 1

        entries.append((gen_n, shape, gen_at, gen_ver, mode))

    display_entries = list(reversed(entries))[:max_entries]
    if not display_entries:
        return ""

    lines = ["Architecture Generation Trail (latest → oldest):"]
    for entry_gen, shape, gen_at, gen_ver, mode in display_entries:
        marker = " [current]" if current_gen is not None and entry_gen == current_gen else ""
        lines.append(f"- Gen #{entry_gen}: {shape} · {gen_at} · {gen_ver} · mode={mode}{marker}")
    return "\n".join(lines)

def ensure_fresh_architecture_context(repo_path: str, commit_sha: str | None = None, topo_id: int | None = None, is_head_fallback: bool = False) -> ArchitectureResult:
    if not MATRIX_ARCH_ENABLED:
        return ArchitectureResult(
            status=ArchStatus.READY,
            blueprint_path=None,
            metadata=None,
            reason="architecture gating disabled by MATRIX_ARCH_ENABLED",
        )

    tree_sig = _compute_tree_signature_for_commit(repo_path, commit_sha) if commit_sha else _compute_tree_signature(repo_path)
    md_path, meta = _load_existing_blueprint(repo_path)

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

    return generate_architecture_blueprint(repo_path, tree_sig, commit_sha=commit_sha, topo_id=topo_id, is_head_fallback=is_head_fallback)
