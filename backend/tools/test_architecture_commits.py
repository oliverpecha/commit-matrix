#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
from pathlib import Path

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.services.architecture_generator import ensure_fresh_architecture_context, build_arch_gen_trail

REPO_ROOT = Path(".").resolve()
REPO_LABEL = REPO_ROOT.name
DATA_DIR = Path("data") / REPO_LABEL
META_PATH = DATA_DIR / f"{REPO_LABEL}_arch_blueprint.meta.json"
VERSIONS_DIR = DATA_DIR / "architecture_versions"
LAST_SIG_PATH = DATA_DIR / "last_arch_sig"

TEST_BRANCH = "tmp/arch-gen-test"
LEAF_TARGET = Path("backend/services/parser_config.py")
STRUCT_DIR = Path("tmp_arch_gen_test_dir")
STRUCT_FILE = STRUCT_DIR / "placeholder.txt"


def run(cmd: list[str], *, check: bool = True, capture: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        check=check,
        text=True,
        capture_output=capture,
    )


def git(*args: str, check: bool = True, capture: bool = True) -> subprocess.CompletedProcess:
    return run(["git", *args], check=check, capture=capture)


def current_branch() -> str:
    return git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()


def reset_arch_outputs() -> None:
    if META_PATH.exists():
        META_PATH.unlink()
    if LAST_SIG_PATH.exists():
        LAST_SIG_PATH.unlink()
    if VERSIONS_DIR.exists():
        shutil.rmtree(VERSIONS_DIR)


def load_current_meta() -> dict:
    if not META_PATH.exists():
        return {}
    raw = META_PATH.read_text(encoding="utf-8").strip()
    return json.loads(raw) if raw else {}


def show_state(label: str) -> None:
    meta = load_current_meta()
    sig = meta.get("tree_signature", "")
    shape = (meta.get("change_summary") or {}).get("change_shape", "—")
    snapshots = sorted(p.name for p in VERSIONS_DIR.glob("arch-*.md")) if VERSIONS_DIR.exists() else []
    sidecars = sorted(p.name for p in VERSIONS_DIR.glob("arch-*.meta.json")) if VERSIONS_DIR.exists() else []
    trail = build_arch_gen_trail(VERSIONS_DIR, current_gen=None)
    print(f"=== {label} ===")
    print("sig:", sig)
    print("shape:", shape)
    print("snapshots:", snapshots)
    print("sidecars:", sidecars)
    print(trail if trail else "(no trail)")
    print()


def show_history(label: str) -> None:
    print(f"=== history: {label} ===")
    proc = subprocess.run(
        ["env", "PYTHONPATH=.", "python3", "backend/tools/architecture_history.py"],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    print(proc.stdout)


def ensure_clean_worktree() -> None:
    proc = git("status", "--porcelain")
    if proc.stdout.strip():
        raise SystemExit("❌ worktree is not clean; commit or stash changes before running test_architecture_commits.py")


def make_leaf_commit() -> None:
    original = LEAF_TARGET.read_text(encoding="utf-8")
    LEAF_TARGET.write_text(original + "\n# arch-gen commit-backed leaf-only marker\n", encoding="utf-8")
    git("add", str(LEAF_TARGET))
    git("commit", "-m", "test(arch): leaf-only generation mutation", capture=False)


def make_structural_commit() -> None:
    STRUCT_DIR.mkdir(parents=True, exist_ok=True)
    STRUCT_FILE.write_text("temporary structural mutation\n", encoding="utf-8")
    git("add", str(STRUCT_DIR))
    git("commit", "-m", "test(arch): structural generation mutation", capture=False)


def main() -> None:
    ensure_clean_worktree()
    original_branch = current_branch()
    print("original-branch:", original_branch)

    # Recreate disposable branch from current HEAD
    existing = git("branch", "--list", TEST_BRANCH).stdout.strip()
    if existing:
        git("branch", "-D", TEST_BRANCH, capture=False)
    git("checkout", "-b", TEST_BRANCH, capture=False)

    try:
        reset_arch_outputs()

        res = ensure_fresh_architecture_context(str(REPO_ROOT))
        print("baseline-status:", res.status)
        print("baseline-reason:", res.reason)
        show_state("baseline")
        show_history("baseline")

        make_leaf_commit()
        res = ensure_fresh_architecture_context(str(REPO_ROOT))
        print("leaf-status:", res.status)
        print("leaf-reason:", res.reason)
        show_state("leaf-only commit")
        show_history("leaf-only commit")

        make_structural_commit()
        res = ensure_fresh_architecture_context(str(REPO_ROOT))
        print("struct-status:", res.status)
        print("struct-reason:", res.reason)
        show_state("structural commit")
        show_history("structural commit")

    finally:
        git("checkout", original_branch, capture=False)
        git("branch", "-D", TEST_BRANCH, capture=False)
        if STRUCT_FILE.exists():
            STRUCT_FILE.unlink()
        if STRUCT_DIR.exists():
            try:
                STRUCT_DIR.rmdir()
            except OSError:
                pass

        # Hard reset tracked files back to original branch state
        git("reset", "--hard", "HEAD", capture=False)

    print("✅ commit-backed architecture test harness completed")


if __name__ == "__main__":
    main()
