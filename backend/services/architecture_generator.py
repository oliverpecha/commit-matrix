"""
Architecture context generation and freshness gate for CommitMatrix.

Milestone 1 scope:
- compute repository tree signature
- manage architecture blueprint + metadata sidecar
- expose ensure_fresh_architecture_context(repo_path) as the main gate
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any

import os
import json
import hashlib
import subprocess
from datetime import datetime

from backend.services.parser_config import (
    HOST_REPO_NAME,
    MATRIX_ARCH_ENABLED,
    MATRIX_ARCH_GENERATOR_VERSION,
)


class ArchStatus(str, Enum):
    READY = "READY"
    STALE_APPROVED = "STALE_APPROVED"
    FAILED = "FAILED"


def _repo_id_from_path(repo_path: str) -> str:
    """Derive a repo identifier used for data/ namespacing."""
    base = os.path.basename(os.path.abspath(repo_path))
    if base == HOST_REPO_NAME:
        return HOST_REPO_NAME
    return base or HOST_REPO_NAME


def _architecture_paths(repo_path: str) -> tuple[Path, Path]:
    repo_id = _repo_id_from_path(repo_path)
    data_dir = Path("data") / repo_id
    data_dir.mkdir(parents=True, exist_ok=True)
    md_path = data_dir / f"{repo_id}_architecture.md"
    meta_path = data_dir / f"{repo_id}_architecture.meta.json"
    return md_path, meta_path


def _compute_tree_signature(repo_path: str) -> str:
    """Compute a deterministic signature of the current repo tree."""
    repo = Path(repo_path)
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "ls-tree", "-r", "--name-only", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        combined = (exc.stdout or "") + (exc.stderr or "")
        digest = hashlib.sha256(combined.encode("utf-8")).hexdigest()
        return f"git-error:{digest}"

    files = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    files.sort()
    joined = "\n".join(files)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _load_existing_blueprint(repo_path: str) -> tuple[Path, Path, Optional[dict]]:
    md_path, meta_path = _architecture_paths(repo_path)
    meta: Optional[dict] = None
    if meta_path.exists():
        try:
            raw = meta_path.read_text(encoding="utf-8")
            if raw.strip():
                meta = json.loads(raw)
        except Exception:
            meta = None
    return md_path, meta_path, meta


def _select_files_for_blueprint(repo_path: str) -> list[str]:
    """Heuristic file selection for architecture generation (Milestone 1)."""
    repo = Path(repo_path).resolve()
    candidates: list[Path] = []

    def is_ignored(p: Path) -> bool:
        parts = p.parts
        if any(part.startswith(".git") for part in parts):
            return True
        if any(part == "__pycache__" for part in parts):
            return True
        if len(parts) > 0 and parts[0].startswith("."):
            return True
        ext = p.suffix.lower()
        if ext in (".pyc", ".pyo", ".log", ".tmp"):
            return True
        return False

    def add_path(p: Path) -> None:
        if is_ignored(p):
            return
        if p.exists() and p.is_file() and p not in candidates:
            candidates.append(p)

    for name in ("README.md", "README", "readme.md", "CONTRIBUTING.md"):
        add_path(repo / name)

    docs_dir = repo / "docs"
    if docs_dir.is_dir():
        for p in sorted(docs_dir.glob("*.md"))[:3]:
            add_path(p)

    for name in (
        "docker-compose.yml",
        "compose.yml",
        "compose.yaml",
        "pyproject.toml",
        "package.json",
        "requirements.txt",
        "Pipfile",
        "setup.py",
        "Makefile",
        "Cargo.toml",
    ):
        add_path(repo / name)

    entry_patterns = (
        "main.py",
        "app.py",
        "server.py",
        "index.py",
        "main.*",
        "app.*",
        "server.*",
        "index.*",
    )
    for pattern in entry_patterns:
        for p in repo.rglob(pattern):
            add_path(p)

    size_list: list[tuple[int, Path]] = []
    for p in repo.rglob("*"):
        if not p.is_file():
            continue
        if is_ignored(p):
            continue
        try:
            size = p.stat().st_size
        except OSError:
            continue
        size_list.append((size, p))
    size_list.sort(reverse=True)
    for _, p in size_list[:20]:
        add_path(p)

    try:
        from backend.services.parser_config import MATRIX_ARCH_MAX_FILES  # type: ignore
    except Exception:
        max_files = 8
    else:
        max_files = max(1, int(MATRIX_ARCH_MAX_FILES))

    selected = candidates[:max_files]
    return [str(p.relative_to(repo)) for p in selected]


def _save_blueprint_and_meta(
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
) -> tuple[Path, Path, dict]:
    md_path, meta_path = _architecture_paths(repo_path)
    md_path.write_text(content, encoding="utf-8")

    meta: dict[str, Any] = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
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
    meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True), encoding="utf-8")

    try:
        sig = tree_signature
        if sig and not sig.startswith("git-error"):
            versions_dir = meta_path.parent / "architecture_versions"
            versions_dir.mkdir(exist_ok=True)
            sig_prefix = sig[:16]
            snapshot_path = versions_dir / f"arch-{sig_prefix}.md"
            snapshot_meta_path = versions_dir / f"arch-{sig_prefix}.meta.json"
            if not snapshot_path.exists():
                snapshot_path.write_text(content, encoding="utf-8")
            snapshot_meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True), encoding="utf-8")
    except Exception:
        pass

    return md_path, meta_path, meta


@dataclass
class ArchitectureResult:
    status: ArchStatus
    blueprint_path: Optional[Path] = None
    metadata: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None


def _build_architecture_prompt_context(
    repo_path: str,
    tree_sig: str,
    selected_files: list[str],
) -> dict:
    repo = Path(repo_path).resolve()
    top_level_dirs: list[str] = []
    for child in repo.iterdir():
        if child.is_dir() and not child.name.startswith("."):
            top_level_dirs.append(child.name)

    return {
        "repo_name": repo.name,
        "repo_path": str(repo),
        "tree_signature": tree_sig,
        "top_level_dirs": top_level_dirs,
        "selected_files": selected_files,
    }


def _infer_dir_role(name: str) -> str:
    dir_role_hints: dict[str, str] = {
        "backend": "server-side logic, API handlers, workers",
        "frontend": "client-side UI code",
        "static": "static assets (JS, CSS, images)",
        "templates": "HTML/template rendering layer",
        "workers": "background job processing",
        "services": "internal service modules",
        "controllers": "request routing and control flow",
        "utils": "shared utility functions",
        "lib": "shared library code",
        "core": "core domain logic",
        "api": "API definitions and routing",
        "models": "data models and schemas",
        "db": "database access and migrations",
        "config": "configuration management",
        "scripts": "operational and maintenance scripts",
        "tests": "test suite",
        "test": "test suite",
        "docs": "documentation",
        "calibration": "calibration fixtures and tooling",
        "data": "data storage and artifacts",
        "deploy": "deployment configuration",
        "infra": "infrastructure as code",
        "cli": "command-line interface",
    }
    lower = name.lower()
    for keyword, role in dir_role_hints.items():
        if keyword in lower:
            return role
    return "supporting module"


def _git_most_changed_files(repo_path: str, top_n: int = 10) -> list[tuple[int, str]]:
    """Return top N most-changed files by commit count."""
    try:
        result = subprocess.run(
            ["git", "-C", repo_path, "log", "--all", "--pretty=format:", "--name-only"],
            capture_output=True,
            text=True,
            check=True,
        )
        counts: dict[str, int] = {}
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            counts[line] = counts.get(line, 0) + 1

        def is_junk(path: str) -> bool:
            parts = path.split("/")
            if any(part.startswith(".git") for part in parts):
                return True
            if any(part == "__pycache__" for part in parts):
                return True
            if len(parts) > 0 and parts[0].startswith("."):
                return True
            ext = Path(path).suffix.lower()
            if ext in (".pyc", ".pyo", ".log", ".tmp"):
                return True
            return False

        filtered = {p: c for p, c in counts.items() if not is_junk(p)}
        code_exts = {
            ".py", ".js", ".ts", ".java", ".go", ".rs", ".rb", ".cs",
            ".php", ".c", ".cpp", ".h", ".sh", ".yml", ".yaml", ".json",
            ".toml", ".ini",
        }
        preferred = {p: c for p, c in filtered.items() if Path(p).suffix.lower() in code_exts}

        def top_n_items(d: dict[str, int]) -> list[tuple[int, str]]:
            return [(count, path) for path, count in sorted(d.items(), key=lambda x: x[1], reverse=True)[:top_n]]

        if preferred:
            return top_n_items(preferred)
        return top_n_items(filtered)
    except Exception:
        return []


def _call_model_with_retry_stub(context: dict) -> tuple[str, int]:
    """Programmatic architecture blueprint (no LLM)."""
    repo_name = context.get("repo_name", "unknown-repo")
    repo_path = context.get("repo_path", ".")
    top_level_dirs = context.get("top_level_dirs", [])
    selected_files = context.get("selected_files", [])
    repo = Path(repo_path)

    lines: list[str] = []
    lines.append(f"# Architecture — {repo_name}")
    lines.append("")
    lines.append("## Directory Map")
    if top_level_dirs:
        for d in sorted(top_level_dirs):
            role = _infer_dir_role(d)
            lines.append(f"- `{d}/` — {role}")
    else:
        lines.append("- no top-level directories detected")
    lines.append("")

    lines.append("## Key Files (heuristic selection)")
    if selected_files:
        for f in selected_files:
            lines.append(f"- `{f}`")
    else:
        lines.append("- no key files selected")
    lines.append("")

    ext_counts: dict[str, int] = {}
    try:
        for p in repo.rglob("*"):
            if p.is_file() and not any(part.startswith(".") for part in p.parts):
                ext = p.suffix.lower() or "no-ext"
                ext_counts[ext] = ext_counts.get(ext, 0) + 1
    except Exception:
        pass

    lines.append("## Language / File Type Breakdown")
    if ext_counts:
        for ext, count in sorted(ext_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
            lines.append(f"- `{ext}` — {count} files")
    else:
        lines.append("- no filetype data available")
    lines.append("")

    hotspots = _git_most_changed_files(repo_path, top_n=10)
    lines.append("## Most Changed Files (Git Hotspots)")
    if hotspots:
        for count, fpath in hotspots:
            lines.append(f"- `{fpath}` — {count} commits")
    else:
        lines.append("- git history unavailable")
    lines.append("")

    lines.append("## Notes")
    lines.append("")
    lines.append("This blueprint was generated programmatically (no LLM).")
    lines.append("It reflects repository structure and git history at generation time.")
    lines.append("Switch MATRIX_ARCH_MODE to `llm-single-pass` for richer semantic analysis.")
    lines.append("")

    return "\n".join(lines), 0


def _validate_architecture_markdown(content: str, repo_name: str) -> tuple[str, bool]:
    text = content.strip()
    if not text:
        return content, False
    lines = text.splitlines()
    if not lines or not lines[0].lstrip().startswith("#"):
        return content, False
    lowered = text.lower()
    if "architecture" not in lowered:
        return content, False
    if repo_name.lower() not in lowered:
        return content, False
    return content, True


def _classify_change_shape(meta_prev: dict | None, meta_curr: dict) -> str:
    """Classify structural difference between previous and current architecture meta."""
    if not meta_prev:
        return "major:first-generation"

    prev_cs = meta_prev.get("change_summary") or {}
    curr_cs = meta_curr.get("change_summary") or {}

    leaf_file_delta_max = 3
    multi_dir_delta_min = 2
    major_file_fraction = 0.20
    major_sel_delta = 8

    gen_prev = (meta_prev.get("generator_version") or "").strip()
    gen_curr = (meta_curr.get("generator_version") or "").strip()
    mode_prev = (prev_cs.get("mode") or "").strip()
    mode_curr = (curr_cs.get("mode") or "").strip()
    if gen_prev != gen_curr or mode_prev != mode_curr:
        return "major:generator-or-mode-change"

    dirs_prev = set(meta_prev.get("top_level_dirs") or [])
    dirs_curr = set(meta_curr.get("top_level_dirs") or [])
    dirs_added = dirs_curr - dirs_prev
    dirs_removed = dirs_prev - dirs_curr
    dir_delta = dirs_added | dirs_removed

    total_prev = int(prev_cs.get("total_files") or 0)
    total_curr = int(curr_cs.get("total_files") or 0)
    file_count_delta = abs(total_curr - total_prev)
    file_count_frac = file_count_delta / max(total_prev, 1)

    sel_prev = set(meta_prev.get("selected_files") or [])
    sel_curr = set(meta_curr.get("selected_files") or [])
    sel_added = sel_curr - sel_prev
    sel_removed = sel_prev - sel_curr
    sel_delta = len(sel_added | sel_removed)

    if len(dir_delta) >= multi_dir_delta_min:
        return "major:dirs"
    if file_count_frac >= major_file_fraction:
        return "major:file-count"
    if sel_delta >= major_sel_delta:
        return "major:selected-files"

    if len(dir_delta) == 1:
        return "multi-dir:dirs"
    if dirs_curr != dirs_prev and len(dirs_curr | dirs_prev) >= 3:
        return "multi-dir:coverage"

    if file_count_frac < major_file_fraction and sel_delta <= leaf_file_delta_max and len(dir_delta) == 0:
        return "leaf-only"

    return "multi-dir:default"


def build_arch_gen_trail(versions_dir: Path, current_gen: int | None, max_entries: int = 5) -> str:
    """Return a compact architecture generation trail string for prompt injection."""
    versions_dir = Path(versions_dir)
    if not versions_dir.exists():
        return ""

    snapshots = sorted(versions_dir.glob("arch-*.md"))
    if not snapshots:
        return ""

    lines: list[str] = []
    current_gen_n = 1
    entries: list[tuple[int, str, str, str, str]] = []

    for idx, snap in enumerate(snapshots):
        sidecar = snap.with_suffix(".meta.json")
        shape = "unknown"
        gen_ver = "—"
        mode = "—"
        gen_at = "—"
        if sidecar.exists():
            try:
                meta = json.loads(sidecar.read_text(encoding="utf-8"))
                shape = (meta.get("change_summary") or {}).get("change_shape", "unknown")
                gen_ver = meta.get("generator_version", "—")
                mode = (meta.get("change_summary") or {}).get("mode", "—")
                gen_at = (meta.get("generated_at") or "—")[:10]
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
        marker = " ◀ current" if gen_n == current_gen else ""
        lines.append(f"  Gen #{gen_n} [{shape}] — {gen_at}  {gen_ver}  {mode}{marker}")

    return "\n".join(lines)


def generate_architecture_blueprint(repo_path: str, tree_sig: str) -> ArchitectureResult:
    """Milestone 1 stub generator (no LLM)."""
    selected_files = _select_files_for_blueprint(repo_path)
    context = _build_architecture_prompt_context(repo_path, tree_sig, selected_files)
    repo = Path(repo_path)
    repo_name = context.get("repo_name", "unknown-repo")

    content, retry_count = _call_model_with_retry_stub(context)
    content, is_valid = _validate_architecture_markdown(content, repo_name)

    total_files = 0
    for p in repo.rglob("*"):
        if p.is_file():
            total_files += 1

    change_summary = {
        "selected_files_count": len(selected_files),
        "total_files": total_files,
        "mode": "stub-valid" if is_valid else "stub-invalid",
    }
    top_level_dirs = context.get("top_level_dirs", [])

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
    )

    try:
        shape = _classify_change_shape(meta_prev, meta)
        cs = meta.get("change_summary") or {}
        cs["change_shape"] = shape
        meta["change_summary"] = cs
        meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True), encoding="utf-8")

        sig_prefix = (meta.get("tree_signature") or "")[:16]
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


def ensure_fresh_architecture_context(repo_path: str) -> ArchitectureResult:
    """Milestone 1 gate (initial behavior, no LLM yet)."""
    if not MATRIX_ARCH_ENABLED:
        return ArchitectureResult(
            status=ArchStatus.READY,
            blueprint_path=None,
            metadata=None,
            reason="architecture gating disabled by MATRIX_ARCH_ENABLED",
        )

    tree_sig = _compute_tree_signature(repo_path)
    md_path, _, meta = _load_existing_blueprint(repo_path)

    if md_path.exists() and meta and meta.get("tree_signature") == tree_sig:
        return ArchitectureResult(
            status=ArchStatus.READY,
            blueprint_path=md_path,
            metadata=meta,
            reason="existing architecture blueprint is current",
        )

    return generate_architecture_blueprint(repo_path, tree_sig)
