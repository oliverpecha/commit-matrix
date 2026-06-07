#!/usr/bin/env python3

from __future__ import annotations

import re

from backend.cli.architecture_history_data import HistoryReport, SnapshotEntry, shape_icon


SUBJECT_LIMIT = len("sync live stream sorting contract between backend timestamps and frontend UI mode")


def truncate_subject(subject: str, limit: int = SUBJECT_LIMIT) -> str:
    subject = (subject or "").strip()
    if not subject:
        return "no subject"
    if len(subject) <= limit:
        return subject
    return subject[: max(0, limit - 3)].rstrip() + "..."


def fmt_subject(raw: str) -> str:
    s = (raw or "").strip()
    s = re.sub(r"^(?:[a-z]+\([^)]*\):\s*|[a-z]+:\s*)", "", s, count=1)
    return truncate_subject(s) if s else "no subject"


def render_summary(report: HistoryReport) -> None:
    print(f"\n🏗️  Architecture Blueprint History — [{report.repo_display}]")
    print()
    print("   Snapshot Summary")
    print(f"   {'─' * 83}")
    print(f"   💾 commits      {report.total_commits:<3}  (raw history)")
    print(f"   📐 blueprints   {report.total_blueprints:<3}  (architecture snapshots)")
    print(f"   🕰️  Generations {report.total_generations:<3}  (grouped by change_shape)")
    print()


def _render_trigger(entry: SnapshotEntry, trunk: str) -> None:
    print(f" {trunk}   ├- Trigger:")
    if entry.trigger and entry.trigger.sha:
        topo_label = f"ID #{entry.trigger.topo_id}" if entry.trigger.topo_id is not None else "ID #?"
        print(f" {trunk}   │      {topo_label} · {entry.trigger.date} · {entry.trigger.sha}")
        print(f" {trunk}   │      {fmt_subject(entry.trigger.subject)}")
    else:
        print(f" {trunk}   │      unavailable")


def _render_commit_block(rows: list, trunk: str) -> None:
    for row in rows:
        rid_label = f"ID #{row.topo_id}" if row.topo_id is not None else row.sha
        print(f" {trunk}   │      {rid_label} · {row.date} · {row.sha}")
        print(f" {trunk}   │      {fmt_subject(row.subject)}")


def _render_also_used(entry: SnapshotEntry, trunk: str) -> None:
    if entry.successive_used_by:
        count = len(entry.successive_used_by)
        label = "commit" if count == 1 else "commits"
        print(f" {trunk}   ├- Also used by {count} other successive {label}:")
        _render_commit_block(entry.successive_used_by, trunk)

    for run in entry.reappeared_runs:
        count = len(run)
        label = "commit" if count == 1 else "commits"
        print(f" {trunk}   ├- Reappeared in {count} later {label}:")
        _render_commit_block(run, trunk)


def render_entry(entry: SnapshotEntry, next_generation: int | None, opened_gen: int | None) -> int:
    branch = "└" if next_generation != entry.generation else "├"
    trunk = " " if next_generation != entry.generation else "│"

    if opened_gen != entry.generation:
        if opened_gen is not None:
            print()
        print(f" 🕰️  Architecture Generation #{entry.generation}")
        opened_gen = entry.generation

    validation = (
        "valid" if entry.mode.endswith("-valid")
        else "invalid" if entry.mode.endswith("-invalid")
        else "unknown"
    )

    current_tag = "  ← current" if entry.is_current else ""
    print(f" {branch} {shape_icon(entry.shape)} {entry.sig[:24]:<26} [{entry.shape}]{current_tag}")
    _render_trigger(entry, trunk)
    _render_also_used(entry, trunk)
    print(
        f" {trunk}   ├- Details: {entry.generator_version} · {entry.mode} · "
        f"sampled {entry.selected_files} of {entry.total_files} files"
    )
    print(
        f" {trunk}   └ Debug: generated {entry.generated_at} · "
        f"validation={validation} · {entry.size_bytes}B"
    )
    return opened_gen


def render_history_report(report: HistoryReport, reverse: bool = False) -> None:
    if report.total_blueprints == 0:
        print("\n  (no snapshot files found)\n")
        return

    render_summary(report)

    entries = list(report.entries) if not reverse else list(reversed(report.entries))

    opened_gen = None
    for idx, entry in enumerate(entries):
        next_generation = entries[idx + 1].generation if idx + 1 < len(entries) else None
        opened_gen = render_entry(entry, next_generation, opened_gen)

    print()

