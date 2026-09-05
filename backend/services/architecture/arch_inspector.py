from __future__ import annotations
from pathlib import Path
import hashlib
import subprocess
from backend.utils.git_ops import (
    list_tree_files_at_commit,
    list_top_level_dirs_at_commit,
)
DIR_ROLE_HINTS: dict[str, str] = {
    "backend": "server-side logic, API handlers, and workers",
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
_LEAF_FILE_DELTA_MAX = 3
_MULTI_DIR_DELTA_MIN = 2
_MAJOR_FILE_FRACTION = 0.20
_MAJOR_SEL_DELTA = 8
def compute_tree_signature(repo_path: str) -> str:
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
        return f"git-error-{digest}"
    files = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    files.sort()
    joined = "\n".join(files)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()
def compute_tree_signature_for_commit(repo_path: str, commit_sha: str) -> str:
    files = list_tree_files_at_commit(repo_path, commit_sha)
    files.sort()
    joined = "\n".join(files)
    if not joined:
        return f"empty-{commit_sha[:12]}"
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()
def select_files_for_blueprint(repo_path: str) -> list[str]:
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
    entry_patterns = ("main.py", "app.py", "server.py", "index.py", "main.*", "app.*", "server.*", "index.*")
    for pattern in entry_patterns:
        for p in repo.rglob(pattern):
            add_path(p)
    size_list = []
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
        from backend.services.pipeline.pipeline_config import MATRIX_ARCH_MAX_FILES  # type: ignore
        max_files = max(1, int(MATRIX_ARCH_MAX_FILES))
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        max_files = 8
    selected = candidates[:max_files]
    return [str(p.relative_to(repo)) for p in selected]
def select_files_for_blueprint_at_commit(repo_path: str, commit_sha: str) -> list[str]:
    files = list_tree_files_at_commit(repo_path, commit_sha)
    def allowed(path: str) -> bool:
        parts = Path(path).parts
        if any(part.startswith(".git") for part in parts):
            return False
        if any(part == "__pycache__" for part in parts):
            return False
        ext = Path(path).suffix.lower()
        if ext in (".pyc", ".pyo", ".log", ".tmp"):
            return False
        return True
    preferred_exact = {
        "README.md", "README", "readme.md", "CONTRIBUTING.md",
        "docker-compose.yml", "compose.yml", "compose.yaml",
        "pyproject.toml", "package.json", "requirements.txt",
        "Pipfile", "setup.py", "Makefile", "Cargo.toml",
    }
    selected: list[str] = []
    seen: set[str] = set()
    def add(rel_path: str) -> None:
        if rel_path in seen:
            return
        if not allowed(rel_path):
            return
        seen.add(rel_path)
        selected.append(rel_path)
    for f in files:
        if f in preferred_exact:
            add(f)
    docs_added = 0
    for f in files:
        parts = Path(f).parts
        if len(parts) >= 2 and parts[0] == "docs" and f.endswith(".md"):
            add(f)
            docs_added += 1
            if docs_added >= 3:
                break
    entry_names = {"main.py", "app.py", "server.py", "index.py"}
    for f in files:
        name = Path(f).name
        if name in entry_names or name.startswith(("main.", "app.", "server.", "index.")):
            add(f)
    code_exts = {
        ".py", ".js", ".ts", ".java", ".go", ".rs", ".rb", ".cs", ".php",
        ".c", ".cpp", ".h", ".sh", ".json", ".toml", ".yml", ".yaml",
        ".md", ".html", ".css",
    }
    for f in files:
        if Path(f).suffix.lower() in code_exts:
            add(f)
    try:
        from backend.services.pipeline.pipeline_config import MATRIX_ARCH_MAX_FILES  # type: ignore
        max_files = max(1, int(MATRIX_ARCH_MAX_FILES))
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        max_files = 8
    return selected[:max_files]
def build_architecture_prompt_context(repo_path: str, tree_sig: str, selected_files: list[str]) -> dict:
    repo = Path(repo_path).resolve()
    top_level_dirs: list[str] = []
    for child in repo.iterdir():
        if child.is_dir() and not child.name.startswith("."):
            top_level_dirs.append(child.name)
    return {
        "repo_name": repo.name,
        "repo_path": str(repo),
        "tree_signature": tree_sig,
        "top_level_dirs": sorted(top_level_dirs),
        "selected_files": selected_files,
    }
def build_architecture_prompt_context_at_commit(repo_path: str, commit_sha: str, tree_sig: str, selected_files: list[str]) -> dict:
    repo = Path(repo_path).resolve()
    top_level_dirs = list_top_level_dirs_at_commit(repo_path, commit_sha)
    return {
        "repo_name": repo.name,
        "repo_path": str(repo),
        "commit_sha": commit_sha,
        "tree_signature": tree_sig,
        "top_level_dirs": sorted(top_level_dirs),
        "selected_files": selected_files,
    }
def infer_dir_role(name: str) -> str:
    lower = name.lower()
    for keyword, role in DIR_ROLE_HINTS.items():
        if keyword in lower:
            return role
    return "supporting module"
def git_most_changed_files(repo_path: str, top_n: int = 10) -> list[tuple[int, str]]:
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
            parts = Path(path).parts
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
            ".py", ".js", ".ts", ".java", ".go", ".rs", ".rb", ".cs", ".php",
            ".c", ".cpp", ".h", ".sh", ".yml", ".yaml", ".json", ".toml", ".ini",
        }
        preferred = {p: c for p, c in filtered.items() if Path(p).suffix.lower() in code_exts}
        source = preferred if preferred else filtered
        return [(count, path) for path, count in sorted(source.items(), key=lambda x: x[1], reverse=True)[:top_n]]
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        return []
def call_model_with_retry_stub(context: dict) -> tuple[str, int]:
    repo_name = context.get("repo_name", "unknown-repo")
    repo_path = context.get("repo_path", ".")
    top_level_dirs = context.get("top_level_dirs", [])
    selected_files = context.get("selected_files", [])
    tree_sig = context.get("tree_signature", "unknown")
    commit_sha = context.get("commit_sha")
    repo = Path(repo_path)
    sig_prefix = tree_sig[:16] if tree_sig else "unknown"
    lines: list[str] = []
    lines.append(f"# Architecture Snapshot: {repo_name} [Sig: {sig_prefix}]")
    lines.append(f"Tree Signature: `{tree_sig}`")
    lines.append("")
    lines.append("## Directory Map")
    if top_level_dirs:
        for d in sorted(top_level_dirs):
            lines.append(f"- `{d}/` — {infer_dir_role(d)}")
    else:
        lines.append("- no top-level directories detected")
    lines.append("")
    lines.append("## Key Files")
    if selected_files:
        for f in selected_files:
            lines.append(f"- `{f}`")
    else:
        lines.append("- no key files selected")
    lines.append("")
    ext_counts: dict[str, int] = {}
    if commit_sha:
        for rel in list_tree_files_at_commit(repo_path, commit_sha):
            ext = Path(rel).suffix.lower() or "[no ext]"
            ext_counts[ext] = ext_counts.get(ext, 0) + 1
    else:
        try:
            for p in repo.rglob("*"):
                if p.is_file() and not any(part.startswith(".") for part in p.parts):
                    ext = p.suffix.lower() or "[no ext]"
                    ext_counts[ext] = ext_counts.get(ext, 0) + 1
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            pass
    lines.append("## Language / File Type Breakdown")
    if ext_counts:
        for ext, count in sorted(ext_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
            lines.append(f"- `{ext}`: {count} files")
    else:
        lines.append("- no file type data available")
    lines.append("")
    hotspots = git_most_changed_files(repo_path, top_n=10)
    lines.append("## Most Changed Files (Git Hotspots)")
    if hotspots:
        for count, fpath in hotspots:
            lines.append(f"- `{fpath}` — {count} commits")
    else:
        lines.append("- git history unavailable")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- This blueprint was generated programmatically based on canonical architectural state.")
    lines.append(f"- Snapshot Signature: `{tree_sig}`.")
    lines.append("")
    return "\n".join(lines), 0
def validate_architecture_markdown(content: str, repo_name: str) -> tuple[str, bool]:
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
def classify_change_shape(meta_prev: dict | None, meta_curr: dict) -> str:
    if not meta_prev:
        return "major:first-generation"
    prev_cs = meta_prev.get("change_summary") or {}
    curr_cs = meta_curr.get("change_summary") or {}
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
    if len(dir_delta) >= _MULTI_DIR_DELTA_MIN:
        return "major:dirs"
    if file_count_frac >= _MAJOR_FILE_FRACTION:
        return "major:file-count"
    if sel_delta >= _MAJOR_SEL_DELTA:
        return "major:selected-files"
    if len(dir_delta) == 1:
        return "multi-dir:dirs"
    if dirs_curr != dirs_prev and len(dirs_curr | dirs_prev) >= 3:
        return "multi-dir:coverage"
    if file_count_frac < _MAJOR_FILE_FRACTION and sel_delta <= _LEAF_FILE_DELTA_MAX and len(dir_delta) == 0:
        return "leaf-only"
    return "multi-dir:default"
