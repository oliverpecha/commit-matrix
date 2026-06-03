#!/usr/bin/env python3
import os
import json
import shutil
from pathlib import Path

from backend.services.architecture.arch_builder import ensure_fresh_architecture_context, build_arch_gen_trail

REPO_ROOT = Path(".").resolve()
REPO_LABEL = REPO_ROOT.name
DATA_DIR = Path("data") / REPO_LABEL
META_PATH = DATA_DIR / f"{REPO_LABEL}_arch_blueprint.meta.json"
VERSIONS_DIR = DATA_DIR / "architecture_versions"
LAST_SIG_PATH = DATA_DIR / "last_arch_sig"

LEAF_TARGET = Path("backend/services/parser_config.py")
STRUCT_DIR = Path("tmp_arch_gen_test_dir")
STRUCT_FILE = STRUCT_DIR / "placeholder.txt"


def _reset_arch_outputs() -> None:
    if META_PATH.exists():
        META_PATH.unlink()
    if LAST_SIG_PATH.exists():
        LAST_SIG_PATH.unlink()
    if VERSIONS_DIR.exists():
        shutil.rmtree(VERSIONS_DIR)


def _load_current_meta() -> dict:
    if not META_PATH.exists():
        return {}
    raw = META_PATH.read_text(encoding="utf-8").strip()
    return json.loads(raw) if raw else {}


def _show_state(label: str) -> None:
    meta = _load_current_meta()
    sig = meta.get("tree_signature", "")
    shape = (meta.get("change_summary") or {}).get("change_shape", "—")
    versions_dir = DATA_DIR / "architecture_versions"
    snapshots = sorted(p.name for p in versions_dir.glob("arch-*.md")) if versions_dir.exists() else []
    sidecars = sorted(p.name for p in versions_dir.glob("arch-*.meta.json")) if versions_dir.exists() else []
    trail = build_arch_gen_trail(versions_dir, current_gen=None)
    print(f"=== {label} ===")
    print("sig:", sig)
    print("shape:", shape)
    print("snapshots:", snapshots)
    print("sidecars:", sidecars)
    print(trail if trail else "(no trail)")
    print()


def baseline() -> None:
    _reset_arch_outputs()
    res = ensure_fresh_architecture_context(str(REPO_ROOT))
    print("baseline-status:", res.status)
    print("baseline-reason:", res.reason)
    _show_state("baseline")


def leaf_only() -> None:
    original = LEAF_TARGET.read_text(encoding="utf-8")
    try:
        patched = original + "\n# arch-gen leaf-only test marker\n"
        LEAF_TARGET.write_text(patched, encoding="utf-8")
        res = ensure_fresh_architecture_context(str(REPO_ROOT))
        print("leaf-status:", res.status)
        print("leaf-reason:", res.reason)
        _show_state("leaf-only mutation")
    finally:
        LEAF_TARGET.write_text(original, encoding="utf-8")


def structural() -> None:
    created_dir = False
    created_file = False
    try:
        if not STRUCT_DIR.exists():
            STRUCT_DIR.mkdir(parents=True)
            created_dir = True
        if not STRUCT_FILE.exists():
            STRUCT_FILE.write_text("temporary structural mutation\n", encoding="utf-8")
            created_file = True
        res = ensure_fresh_architecture_context(str(REPO_ROOT))
        print("struct-status:", res.status)
        print("struct-reason:", res.reason)
        _show_state("structural mutation")
    finally:
        if created_file and STRUCT_FILE.exists():
            STRUCT_FILE.unlink()
        if created_dir and STRUCT_DIR.exists():
            STRUCT_DIR.rmdir()


if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "baseline":
        baseline()
    elif mode == "leaf":
        leaf_only()
    elif mode == "struct":
        structural()
    else:
        raise SystemExit("usage: PYTHONPATH=. python3 backend/tools/test_architecture_mutations.py [baseline|leaf|struct]")
