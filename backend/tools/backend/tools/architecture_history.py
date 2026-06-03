#!/usr/bin/env python3
"""
Architecture history utility.

Lists architecture snapshots, their ArchSig prefixes, and generator metadata
for a given repo (defaults to HOST_REPO_NAME).
"""

import json
from pathlib import Path

from backend.services.parser_config import HOST_REPO_NAME

def main(repo_label: str | None = None) -> None:
    repo_label = repo_label or HOST_REPO_NAME
    data_dir = Path("data") / repo_label
    meta_path = data_dir / f"{repo_label}_arch_blueprint.meta.json"
    versions_dir = data_dir / "architecture_versions"

    print(f"📚 Architecture history for [{repo_label}]")
    if not versions_dir.exists():
        print("  (no architecture_versions directory found)")
        return

    try:
        meta = {}
        if meta_path.exists():
            raw = meta_path.read_text(encoding="utf-8").strip()
            if raw:
                meta = json.loads(raw)
    except Exception as e:
        print(f"  ⚠️ Failed to load metadata: {e}")
        meta = {}

    tree_sig = meta.get("tree_signature", "")
    generated_at = meta.get("generated_at", "")
    gen_version = meta.get("generator_version", "")
    mode = (meta.get("change_summary") or {}).get("mode", "unknown")

    print(f"  Current ArchSig: {tree_sig}")
    print(f"  Generated at:   {generated_at}")
    print(f"  Generator:      {gen_version} (mode={mode})")
    print()

    snapshots = sorted(p for p in versions_dir.glob("arch-*.md") if p.is_file())
    if not snapshots:
        print("  (no snapshot files found)")
        return

    print("  Snapshots:")
    for idx, snap in enumerate(snapshots, start=1):
        name = snap.name  # arch-<prefix>.md
        prefix = name[len("arch-"):-len(".md")]
        size = snap.stat().st_size
        marker = ""
        if tree_sig.startswith(prefix):
            marker = "  <-- current"
        print(f"    Gen #{idx:02d}: {name} ({size} bytes){marker}")

if __name__ == "__main__":
    main()
