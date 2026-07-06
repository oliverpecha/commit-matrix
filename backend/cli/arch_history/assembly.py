from __future__ import annotations

from typing import List

from backend.cli.arch_history.models import SnapshotEntry, CommitRef


def _reassign_generations(entries: List[SnapshotEntry]) -> List[SnapshotEntry]:
    ordered = sorted(
        entries,
        key=lambda e: (
            e.trigger.topo_id if e.trigger and e.trigger.topo_id is not None else 10_000_000
        ),
    )
    current_gen = 1
    gen_idx = 0
    for idx, entry in enumerate(ordered):
        if idx > 0 and not (entry.shape or "").startswith("leaf-only") and (entry.shape or "") != "major:head":
            current_gen += 1
            gen_idx = 0
        entry.generation = current_gen
        entry.generation_index = gen_idx
        gen_idx += 1
    return ordered


def _reanchor_reuse_by_signature(entries: List[SnapshotEntry]) -> List[SnapshotEntry]:
    ordered = sorted(
        entries,
        key=lambda e: (
            e.trigger.topo_id if e.trigger and e.trigger.topo_id is not None else 10_000_000
        ),
    )

    preserved_refs: list[tuple[str, CommitRef]] = []
    for entry in ordered:
        if entry.trigger:
            preserved_refs.append((entry.snapshot_sig, entry.trigger))
        for ref in entry.also_used_by:
            preserved_refs.append((entry.snapshot_sig, ref))

    for entry in ordered:
        entry.also_used_by = []

    anchors: dict[str, SnapshotEntry] = {}
    for entry in ordered:
        if entry.snapshot_sig:
            anchors[entry.snapshot_sig] = entry

    sig_to_trigger_topos: dict[str, set[int]] = {}
    for entry in ordered:
        if entry.snapshot_sig and entry.trigger and entry.trigger.topo_id is not None:
            sig_to_trigger_topos.setdefault(entry.snapshot_sig, set()).add(entry.trigger.topo_id)

    sig_to_rows: dict[str, list[CommitRef]] = {}
    for sig, ref in preserved_refs:
        sig_to_rows.setdefault(sig, []).append(ref)

    for sig, refs in sig_to_rows.items():
        anchor = anchors.get(sig)
        if anchor is None:
            continue

        trigger_topos = sig_to_trigger_topos.get(sig, set())
        seen: set[int] = set()
        reattached: list[CommitRef] = []

        for ref in sorted(
            refs,
            key=lambda r: (r.topo_id if r.topo_id is not None else 10_000_000, r.commit_sig),
        ):
            if ref.topo_id is None:
                continue
            if anchor.trigger and anchor.trigger.topo_id == ref.topo_id:
                continue
            if ref.topo_id in trigger_topos:
                continue
            if ref.topo_id in seen:
                continue
            seen.add(ref.topo_id)
            reattached.append(ref)

        anchor.also_used_by = reattached

    return ordered
