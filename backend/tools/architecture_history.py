#!/usr/bin/env python3
"""
Architecture Blueprint history utility.

Lists Architecture Blueprints, their Generations, ArchSig, change_shape tag,
and generator metadata for a given repo (defaults to HOST_REPO_NAME).

Usage (from repo root):
    PYTHONPATH=. python3 backend/tools/architecture_history.py
    PYTHONPATH=. python3 backend/tools/architecture_history.py my-repo
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.services.parser_config import HOST_REPO_NAME


def _load_snapshot_meta(snap: Path) -> dict:
    sidecar = snap.with_suffix(".meta.json")
    if sidecar.exists():
        try:
            return json.loads(sidecar.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _compute_generations(snapshots: list[Path]) -> list[tuple[int, Path, dict]]:
    """
    Return [(gen_number, snapshot_path, meta), ...] using change_shape-aware grouping.

    Rule:
      - First snapshot => Generation #1.
      - Each subsequent snapshot whose change_shape does NOT start with "leaf-only"
        bumps the Generation number by 1.
      - leaf-only snapshots stay in the same Generation as the previous snapshot.
    """
    result: list[tuple[int, Path, dict]] = []
    current_gen = 1
    for idx, snap in enumerate(snapshots):
        meta = _load_snapshot_meta(snap)
        shape = (meta.get("change_summary") or {}).get("change_shape", "unknown")
        if idx > 0 and not shape.startswith("leaf-only"):
            current_gen += 1
        result.append((current_gen, snap, meta))
    return result


def main(repo_label: str | None = None) -> None:
    repo_label = repo_label or HOST_REPO_NAME
    data_dir = Path("data") / repo_label
    meta_path = data_dir / f"{repo_label}_arch_blueprint.meta.json"
    versions_dir = data_dir / "architecture_versions"

    current_meta: dict = {}
    if meta_path.exists():
        try:
            raw = meta_path.read_text(encoding="utf-8").strip()
            if raw:
                current_meta = json.loads(raw)
        except Exception as e:
            print(f"  ⚠️  Failed to load current blueprint meta: {e}")

    curr_sig = current_meta.get("tree_signature", "")
    curr_generated_at = current_meta.get("generated_at", "—")
    curr_genver = current_meta.get("generator_version", "—")
    curr_cs = current_meta.get("change_summary") or {}
    curr_mode = curr_cs.get("mode", "—")
    curr_shape = curr_cs.get("change_shape", "—")
    curr_total = curr_cs.get("total_files", "—")
    curr_sel = curr_cs.get("selected_files_count", "—")

    print(f"\n📐 Architecture Blueprint History — [{repo_label}]")
    print("   (top section = latest current blueprint)")
    print(f"   {'ArchSig':<20} {curr_sig}")
    print(f"   {'Generated at':<20} {curr_generated_at}")
    print(f"   {'Generator':<20} {curr_genver}  (mode={curr_mode})")
    print(f"   {'change_shape':<20} {curr_shape}")
    print(f"   {'Files':<20} {curr_sel} selected / {curr_total} total")

    if not versions_dir.exists():
        print("\n  (no architecture_versions directory found)\n")
        return

    snapshots = sorted(p for p in versions_dir.glob("arch-*.md") if p.is_file())
    if not snapshots:
        print("\n  (no snapshot files found)\n")
        return

    generations = _compute_generations(snapshots)
    max_gen = generations[-1][0] if generations else 1

    print(f"\n   {'Snapshots':<20} {max_gen} Generation(s)  / {len(snapshots)} blueprints\n")

    generations_desc = list(reversed(generations))
    seen_gens: set[int] = set()

    for gen_num, snap, meta in generations_desc:
        sig = meta.get("tree_signature", snap.stem[len("arch-"):])
        shape = (meta.get("change_summary") or {}).get("change_shape", "—")
        genver = meta.get("generator_version", "—")
        mode = (meta.get("change_summary") or {}).get("mode", "—")
        generated_at = meta.get("generated_at", "—")[:19].replace("T", " ")
        size = snap.stat().st_size

        is_current = bool(
            curr_sig and (
                curr_sig == sig
                or curr_sig.startswith(sig[:16])
                or sig.startswith(curr_sig[:16])
            )
        )
        current_marker = "  ◀ current" if is_current else ""

        if gen_num not in seen_gens:
            print(f"  ┌─ 🕰️ Architecture Generation #{gen_num} " + "─" * 29 + "┐")
            seen_gens.add(gen_num)

        print(f"  │  🧬 {sig[:24]:<26} [{shape}]{current_marker}")
        print(f"  │     {generated_at}  ·  {genver}  ·  mode={mode}  ·  {size}B")

    print(f"  └{'─' * 50}┘\n")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
