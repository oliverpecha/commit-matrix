#!/usr/bin/env python3
from pathlib import Path
import json
import os
import shutil

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.services.architecture.arch_builder import ensure_fresh_architecture_context

REPO_PATH = "."
REPO_LABEL = os.path.basename(os.path.abspath(REPO_PATH)) or "repo"
DATA_DIR = Path("data") / REPO_LABEL
META_PATH = DATA_DIR / f"{REPO_LABEL}_arch_blueprint.meta.json"
VERSIONS_DIR = DATA_DIR / "architecture_versions"
LAST_SIG_PATH = DATA_DIR / "last_arch_sig"

def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise SystemExit(f"❌ test failure: {msg}")

print("=== reset architecture artifacts ===")
if META_PATH.exists():
    META_PATH.unlink()
if LAST_SIG_PATH.exists():
    LAST_SIG_PATH.unlink()
if VERSIONS_DIR.exists():
    shutil.rmtree(VERSIONS_DIR)

print("=== fresh generation ===")
res1 = ensure_fresh_architecture_context(REPO_PATH)
meta1 = res1.metadata or {}
sig1 = meta1.get("tree_signature", "")
shape1 = (meta1.get("change_summary") or {}).get("change_shape", "")

print("status-1:", res1.status)
print("reason-1:", res1.reason)
print("sig-1:", sig1)
print("shape-1:", shape1)

_assert(str(res1.status).endswith("READY"), "fresh run should return READY")
_assert(bool(sig1), "fresh run should produce a tree signature")
_assert(shape1 == "major:first-generation", "fresh run should classify as major:first-generation")

snapshots = sorted(VERSIONS_DIR.glob("arch-*.md"))
sidecars = sorted(VERSIONS_DIR.glob("arch-*.meta.json"))
print("snapshots-after-fresh:", [p.name for p in snapshots])
print("sidecars-after-fresh:", [p.name for p in sidecars])

_assert(len(snapshots) == 1, "fresh run should create exactly one snapshot")
_assert(len(sidecars) == 1, "fresh run should create exactly one snapshot sidecar")

side_meta = json.loads(sidecars[0].read_text(encoding="utf-8"))
_assert(side_meta.get("tree_signature") == sig1, "snapshot sidecar tree_signature should match current signature")

print("=== second run (reuse/current) ===")
res2 = ensure_fresh_architecture_context(REPO_PATH)
meta2 = res2.metadata or {}
sig2 = meta2.get("tree_signature", "")
print("status-2:", res2.status)
print("reason-2:", res2.reason)
print("sig-2:", sig2)

_assert(str(res2.status).endswith("READY"), "second run should return READY")
_assert(sig2 == sig1, "second run should keep the same tree signature")
_assert("current" in (res2.reason or ""), "second run should reuse current blueprint")

snapshots2 = sorted(VERSIONS_DIR.glob("arch-*.md"))
sidecars2 = sorted(VERSIONS_DIR.glob("arch-*.meta.json"))
_assert(len(snapshots2) == 1, "second run should not create a second snapshot")
_assert(len(sidecars2) == 1, "second run should not create a second sidecar")

print("✅ architecture generation flow smoke test passed")
