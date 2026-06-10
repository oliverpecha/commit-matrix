#!/usr/bin/env python3

from __future__ import annotations

import re
from pathlib import Path

from backend.cli.architecture_history_data import (
    HistoryReport,
    SnapshotEntry,
    GenerationSummaryMetrics,
    shape_icon,
)


SUBJECT_LIMIT = len("sync live stream sorting contract between backend timestamps and frontend UI mode")
COMPACT_SUBJECT_LIMIT = SUBJECT_LIMIT
COMPACT_OMISSION_LIMIT = 56


def truncate_subject(subject: str, limit: int = SUBJECT_LIMIT) -> str:
    subject = (subject or "").strip()
    if not subject:
        return "no subject"
    if len(subject) <= limit:
        return subject
    return subject[: max(0, limit - 3)].rstrip() + "..."


def fmt_subject(raw: str, limit: int = SUBJECT_LIMIT) -> str:
    s = (raw or "").strip()
    s = re.sub(r"^(?:[a-z]+\([^)]*\):\s*|[a-z]+:\s*)", "", s, count=1)
    return truncate_subject(s, limit=limit) if s else "no subject"


def _format_lifespan_date_span(first_date: str, last_date: str) -> str:
    first_date = (first_date or "").strip()
    last_date = (last_date or "").strip()
    if not first_date:
        return last_date or "unknown"
    if not last_date or last_date == first_date:
        return first_date
    return f"{first_date}–{last_date}"


def render_summary(report: HistoryReport) -> None:
    print(f"\n🏗️  Architecture Blueprint History — [{report.repo_display}]")
    print()

    print("   Snapshot Summary")
    print(f"   {'─' * 83}")
    print(f"   💾 Commits      {report.total_commits:<3}  (raw history)")
    print(f"   📐 Snapshots    {report.total_blueprints:<3}  (architecture artifacts)")
    print(f"   🕰️  Generations  {report.total_generations:<3}  (grouped by change_shape)")
    print()


def _render_filtered_header(
    report: HistoryReport,
    entries: list[SnapshotEntry],
    reverse: bool = False,
    since: str | None = None,
    until: str | None = None,
    generation: int | None = None,
    sig_prefix: str | None = None,
    only_reappeared: bool = False,
    compact: bool = False,
) -> None:
    topo_ids = [e.trigger.topo_id for e in entries if e.trigger and e.trigger.topo_id is not None]
    generations = sorted({e.generation for e in entries})
    generation_label = (
        f"{generations[0]}"
        if len(generations) == 1
        else f"{generations[0]}..{generations[-1]}"
    ) if generations else "?"

    if topo_ids:
        range_label = f"topo IDs {min(topo_ids)}..{max(topo_ids)}"
    else:
        range_label = "selected history window"

    filters: list[str] = []
    if since:
        filters.append(f"since={since}")
    if until:
        filters.append(f"until={until}")
    if generation is not None:
        filters.append(f"generation={generation}")
    if sig_prefix:
        filters.append(f"sig_prefix={sig_prefix}")
    if only_reappeared:
        filters.append("only_reappeared")
    filter_label = ", ".join(filters) if filters else "derived subset"

    order_bits = ["newest → oldest" if reverse else "oldest → newest"]
    if compact:
        order_bits.append("compact")
    order_label = ", ".join(order_bits)

    print(f"\n🔎 Architecture Blueprint Slice — [{report.repo_display}]")
    print(f"   Filters: {filter_label}")
    print(f"   Range: {range_label}")
    print(f"   Generations: {generation_label}")
    print(f"   Order: {order_label}")
    print("   Note: snapshot lifespan and reappearance metadata may extend beyond the selected range.")
    print()


def _shape_icon_fallback(shape: str) -> str:
    s = (shape or "").strip()
    if s.startswith("leaf-only"):
        return "🍃"
    if s.startswith("major:") or s.startswith("multi-dir:") or s.startswith("multi-dir"):
        return "🌳"
    return "•"


def _render_generation_panel(
    report: HistoryReport,
    generation: int,
    compact: bool = False,
    filtered: bool = False,
) -> None:
    summaries = report.generation_summaries or {}
    summary: GenerationSummaryMetrics | None = summaries.get(generation)
    if summary is None:
        print(f" 🕰️  Architecture Generation #{generation}")
        return

    panel_width = 56

    def row(label: str, value: str) -> None:
        inner = f" {label:<16} {value}"
        print(f" │  │{inner:<{panel_width}}│")

    def structural_mix_value() -> str:
        parts: list[str] = []
        if summary.incremental_count:
            parts.append(f"{summary.incremental_count} incremental")
        if summary.structural_count:
            parts.append(f"{summary.structural_count} structural")
        return " / ".join(parts) if parts else "0"

    dom_sig = summary.dominant_snapshot_sig[:24] if summary.dominant_snapshot_sig else "n/a"
    generation_share_pct = int(round(summary.dominant_share_of_generation * 100)) if summary.dominant_share_of_generation > 0 else 0
    repo_share_pct = int(round((summary.mapped_commits / report.total_commits) * 100)) if report.total_commits > 0 else 0

    print(f" 🕰️  Architecture Generation #{generation}")
    print(" │")
    title = "Summary (filtered view)" if filtered else "Summary"
    print(f" │  ┌ {title:<24}───────────────────────────────────────┐")
    row("Boundary cause", summary.cause_label)
    treesig_label = "TreeSig" if summary.repeated_treesig_count == 1 else "TreeSigs"
    snapshots_value = str(summary.snapshot_count)
    if summary.repeated_treesig_count:
        snapshots_value += f" · {summary.repeated_treesig_count} {treesig_label}"
    row("Snapshots", snapshots_value)
    row("Generation span", f"{summary.mapped_commits} commits")
    row("Repo share", f"{repo_share_pct}%")
    row("Structural mix", structural_mix_value())
    print(" │  │-- Dominant snapshot -----------------------------------│")
    print(f" │  │ {dom_sig:<55}│")
    row("Lifespan", f"{summary.dominant_effective_commits} commits")
    row("Generation share", f"{generation_share_pct}%")
    if summary.repeated_treesig_count:
        row("Repeated TreeSigs", str(summary.repeated_treesig_count))
    print(" │  └────────────────────────────────────────────────────────┘")
    print(" │")


def _render_lifespan_and_badges(entry: SnapshotEntry, branch: str, trunk: str) -> None:
    """Render snapshot header with shape label and badges plus Lifespan line."""
    icon = shape_icon(entry.shape) or _shape_icon_fallback(entry.shape)
    if icon == "•":
        icon = _shape_icon_fallback(entry.shape)
    shape_label = entry.shape_label or entry.shape or "unknown"
    dominance = entry.dominance
    lifespan = entry.lifespan

    badges: list[str] = []
    if dominance:
        if dominance.is_dominant:
            badges.append("[dominant]")
        if dominance.is_long_lived:
            badges.append("[long-lived]")
        if dominance.is_short_lived:
            badges.append("[short-lived]")
    # repeat badge: more than one run
    if lifespan and lifespan.run_count > 1:
        badges.append("[repeat]")

    if entry.is_current:
        badges.append("            ← [CURRENT]")
    badge_str = (" · " + " · ".join(badges)) if badges else ""
    print(f" {branch} {icon} {entry.sig[:24]:<26} [{shape_label}]{badge_str}")

    if lifespan:
        if lifespan.run_count <= 1:
            date_part = _format_lifespan_date_span(
                lifespan.first_seen_date,
                lifespan.last_seen_date,
            )
            print(f" {trunk}   ├- Lifespan: {lifespan.total_commits} commit{'s' if lifespan.total_commits != 1 else ''} · {date_part}")
        else:
            first_date = lifespan.first_seen_date
            last_date = lifespan.last_seen_date
            print(
                f" {trunk}   ├- Lifespan: {lifespan.total_commits} commits across {lifespan.run_count} runs · first {first_date} · last {last_date}"
            )

def _operational_kind(subject: str) -> str:
    s = (subject or "").strip()
    if s.startswith("index on "):
        return "stash/index"
    if s.startswith("WIP on "):
        return "stash/wip"
    if "RECOVERY BASELINE" in s:
        return "recovery"
    if s.startswith("On ") and ": " in s:
        return "operational"
    return ""


def _is_operational_ref(ref) -> bool:
    s = (ref.subject or "").strip()
    return bool(
        s.startswith("index on ")
        or s.startswith("WIP on ")
        or ("RECOVERY BASELINE" in s)
        or (s.startswith("On ") and ": " in s)
    )


def _render_commit_line(ref, trunk: str, annotate_operational: bool = False) -> None:
    rid_label = f"ID #{ref.topo_id}" if ref.topo_id is not None else ref.sha
    kind = _operational_kind(ref.subject) if annotate_operational and _is_operational_ref(ref) else ""
    extra = f" · [operational: {kind}]" if kind else ""
    print(f" {trunk}   │      {rid_label} · {ref.date} · {ref.sha}{extra}")
    print(f" {trunk}   │      {fmt_subject(ref.subject)}")


def _render_commit_block(
    rows: list,
    trunk: str,
    show_operational: bool = True,
    compact: bool = False,
) -> None:
    visible_rows = []
    hidden_operational = []

    for row in rows:
        if _is_operational_ref(row):
            if show_operational:
                visible_rows.append(row)
            else:
                hidden_operational.append(row)
        else:
            visible_rows.append(row)

    for row in visible_rows:
        _render_commit_line(row, trunk, annotate_operational=show_operational)

    if hidden_operational:
        kinds = sorted(set(filter(None, (_operational_kind(r.subject) for r in hidden_operational))))
        kinds_label = "/".join(kinds) if kinds else "operational"
        kinds_label = truncate_subject(kinds_label, limit=COMPACT_OMISSION_LIMIT)
        print(
            f" {trunk}   │      · {len(hidden_operational)} operational omitted ({kinds_label}); use --show-operational"
        )


def _render_trigger(entry: SnapshotEntry, trunk: str) -> None:
    print(f" {trunk}   ├- Trigger:")
    if entry.trigger and entry.trigger.sha:
        topo_label = f"ID #{entry.trigger.topo_id}" if entry.trigger.topo_id is not None else "ID #?"
        print(f" {trunk}   │      {topo_label} · {entry.trigger.date} · {entry.trigger.sha}")
        print(f" {trunk}   │      {fmt_subject(entry.trigger.subject)}")
    else:
        print(f" {trunk}   │      unavailable")




def _render_also_used(
    entry: SnapshotEntry,
    trunk: str,
    show_operational: bool = True,
    compact: bool = False,
) -> None:
    if entry.successive_used_by:
        count = len(entry.successive_used_by)
        label = "commit" if count == 1 else "commits"
        print(f" {trunk}   ├- Also used by {count} other successive {label}:")
        _render_commit_block(
            entry.successive_used_by,
            trunk,
            show_operational=show_operational,
            compact=compact,
        )

    for run in entry.reappeared_runs:
        count = len(run)
        label = "commit" if count == 1 else "commits"
        print(f" {trunk}   ├- Reappeared in {count} later {label}:")
        _render_commit_block(
            run,
            trunk,
            show_operational=show_operational,
            compact=compact,
        )


def _generation_clip_counts(
    report: HistoryReport,
    entries: list[SnapshotEntry],
    generation: int,
) -> tuple[int, int]:
    all_generation_entries = [e for e in report.entries if e.generation == generation]
    visible_generation_entries = [e for e in entries if e.generation == generation]
    if not all_generation_entries or not visible_generation_entries:
        return 0, 0

    all_sigs = [e.sig for e in all_generation_entries]
    visible_sigs = [e.sig for e in visible_generation_entries]
    first_visible = visible_sigs[0]
    last_visible = visible_sigs[-1]

    earlier = 0
    for sig in all_sigs:
        if sig == first_visible:
            break
        earlier += 1

    later = 0
    for sig in reversed(all_sigs):
        if sig == last_visible:
            break
        later += 1

    return earlier, later


def _render_generation_omission_hint(
    report: HistoryReport,
    entries: list[SnapshotEntry],
    index: int,
    opened_gen: int | None,
    reverse: bool = False,
) -> None:
    entry = entries[index]
    generation = entry.generation
    if opened_gen == generation:
        return

    visible_generation_entries = [e for e in entries if e.generation == generation]
    all_generation_entries = [e for e in report.entries if e.generation == generation]
    if not all_generation_entries or len(visible_generation_entries) >= len(all_generation_entries):
        return

    earlier, later = _generation_clip_counts(report, entries, generation)
    if reverse:
        earlier, later = later, earlier

    trunk = " │"
    if earlier > 0 and later > 0:
        print(f"{trunk}  … {earlier} earlier snapshots omitted outside selected range; {later} later snapshots omitted")
    elif earlier > 0:
        print(f"{trunk}  … {earlier} earlier snapshots omitted outside selected range")
    elif later > 0:
        print(f"{trunk}  … {later} later snapshots omitted outside selected range")


def render_entry(
    report: HistoryReport,
    entry: SnapshotEntry,
    next_generation: int | None,
    opened_gen: int | None,
    compact: bool = False,
    show_operational: bool = True,
    filtered_generation: bool = False,
    show_generation_summary: bool = True,
) -> int:
    branch = "└" if next_generation != entry.generation else "├"
    trunk = " " if next_generation != entry.generation else "│"

    if opened_gen != entry.generation:
        if opened_gen is not None:
            print()
        if show_generation_summary:
            _render_generation_panel(
                report,
                entry.generation,
                compact=compact,
                filtered=filtered_generation,
            )
        else:
            print(f" 🕰️  Architecture Generation #{entry.generation}")
            print(" │")
        opened_gen = entry.generation

    validation = (
        "valid" if entry.mode.endswith("-valid")
        else "invalid" if entry.mode.endswith("-invalid")
        else "unknown"
    )

    _render_lifespan_and_badges(entry, branch, trunk)
    _render_trigger(entry, trunk)
    _render_also_used(
        entry,
        trunk,
        show_operational=show_operational,
        compact=compact,
    )
    if compact:
        print(
            f" {trunk}   └ Details: {entry.generator_version} · {entry.mode} · "
            f"{entry.selected_files}/{entry.total_files} files · {entry.size_bytes}B"
        )
    else:
        print(
            f" {trunk}   ├- Details: {entry.generator_version} · {entry.mode} · "
            f"sampled {entry.selected_files} of {entry.total_files} files"
        )
        debug_parts = [f"generated {entry.generated_at}"]
        if validation != "unknown":
            debug_parts.append(f"validation={validation}")
        debug_parts.append(f"{entry.size_bytes}B")
        print(f" {trunk}   └- Debug: " + " · ".join(debug_parts))
    return opened_gen


def render_history_report(
    report: HistoryReport,
    reverse: bool = False,
    compact: bool = False,
    show_operational: bool = True,
    since: str | None = None,
    until: str | None = None,
    generation: int | None = None,
    sig_prefix: str | None = None,
    only_reappeared: bool = False,
) -> None:
    # True empty-repo case: no snapshots and no mapped commits at all.
    if report.total_blueprints == 0 and report.total_commits == 0:
        print("\n  (no snapshot files found)\n")
        return

    entries = list(report.entries) if not reverse else list(reversed(report.entries))
    if compact:
        entries = [e for e in entries if e.dominance and e.dominance.is_dominant]

    if not entries:
        print("\n  (no snapshots matched the current filters)\n")
        return

    visible_generations = len({e.generation for e in entries})
    is_filtered_view = (
        len(entries) != report.total_blueprints
        or visible_generations != report.total_generations
    )

    if not is_filtered_view:
        render_summary(report)
    else:
        _render_filtered_header(
            report,
            entries,
            reverse=reverse,
            since=since,
            until=until,
            generation=generation,
            sig_prefix=sig_prefix,
            only_reappeared=only_reappeared,
            compact=compact,
        )

    opened_gen = None
    for idx, entry in enumerate(entries):
        _render_generation_omission_hint(report, entries, idx, opened_gen, reverse=reverse)
        next_generation = entries[idx + 1].generation if idx + 1 < len(entries) else None
        all_generation_entries = [e for e in report.entries if e.generation == entry.generation]
        visible_generation_entries = [e for e in entries if e.generation == entry.generation]
        filtered_generation = len(visible_generation_entries) < len(all_generation_entries)
        opened_gen = render_entry(
            report,
            entry,
            next_generation,
            opened_gen,
            compact=compact,
            show_operational=show_operational,
            filtered_generation=filtered_generation,
            show_generation_summary=not is_filtered_view,
        )

    # In compact mode we intentionally suppress the trailing current-blueprint footer.
    if compact:
        print()
        return

    latest = entries[-1] if entries else None
    if latest is not None and not is_filtered_view:
        print()
        filename = f"arch-G{latest.generation}-{latest.sig[:16]}.md"
        print(f"   Current Blueprint  {filename}")
        blueprint_path = None
        for candidate in (
            Path(filename),
            Path(".architecture") / filename,
            Path("blueprints") / filename,
            Path("backend") / filename,
        ):
            if candidate.exists():
                blueprint_path = candidate
                break

        if blueprint_path is not None:
            try:
                print(blueprint_path.read_text().rstrip())
            except Exception as exc:
                print(f"   [unable to read {filename}: {exc}]")
        else:
            print(f"   [unable to locate {filename}]")

    print()

