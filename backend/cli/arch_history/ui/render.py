from __future__ import annotations
from pathlib import Path
from backend.cli.arch_history.models import (
    HistoryReport, SnapshotEntry, GenerationSummaryMetrics
)
from backend.cli.arch_history.ui.format import (
    COMPACT_OMISSION_LIMIT, truncate_subject, fmt_subject,
    _format_lifespan_date_span, shape_icon, _shape_icon_fallback,
    _operational_kind, _is_operational_ref
)
from backend.cli.arch_history.ui.markers import TimelineMarkers

def render_summary(report: HistoryReport) -> None:
    print(f"\n🏗️  Architecture Blueprint History — [{report.repo_display}]")
    print()
    print("   Snapshot Summary")
    print(f"   {'─' * 83}")
    print(f"   💾 Commits       {report.total_commits:<3}  (raw history)")
    print(f"   📐 Snapshots     {report.total_blueprints:<3}  (architecture artifacts)")
    print(f"   🕰️  Generations  {report.total_generations:<3}  (grouped by change_shape)")
    print()

def _render_filtered_header(
    report: HistoryReport, entries: list[SnapshotEntry], reverse: bool = False,
    since: str | None = None, until: str | None = None, generation: str | None = None,
    snapshot_prefix: str | None = None, commit_target: str | None = None,
    only_reappeared: bool = False, compact: bool = False, markers: TimelineMarkers | None = None
) -> None:
    topo_ids = [e.trigger.topo_id for e in report.entries if e.trigger and e.trigger.topo_id is not None]
    if markers:
        if markers.start: topo_ids.append(markers.start['topo'])
        if markers.end: topo_ids.append(markers.end['topo'])
    generations = sorted({e.generation for e in report.entries})
    generation_label = (f"{generations[0]}" if len(generations) == 1 else f"{generations[0]}..{generations[-1]}") if generations else "?"
    range_label = f"topo IDs {min(topo_ids)}..{max(topo_ids)}" if topo_ids else "selected history window"
    filters = []
    if since: filters.append(f"since={since}")
    if until: filters.append(f"until={until}")
    if generation is not None: filters.append(f"generation={generation}")
    if snapshot_prefix: filters.append(f"snapshot={snapshot_prefix}")
    if commit_target: filters.append(f"commit={commit_target}")
    if only_reappeared: filters.append("only_reappeared")
    filter_label = ", ".join(filters) if filters else "none"
    order_label = ", ".join(["newest → oldest" if reverse else "oldest → newest"] + (["compact"] if compact else []))
    print(f"\n🔎 Architecture Blueprint Slice — [{report.repo_display}]\n   Filters: {filter_label}\n   Range: {range_label}\n   Generations: {generation_label}\n   Order: {order_label}")
    if compact:
        print("   Note: Compact mode displays only dominant snapshots per generation.\n         Lifespan and reappearance metadata preserve full historical context\n         and may extend outside the exact numeric filter bounds.")
    else:
        print("   Note: Snapshot lifespan and reappearance metadata may extend beyond the selected range.\n         This intentionally preserves the full lifecycle of any snapshot overlapping the window.")
    print()

def _render_generation_panel(report: HistoryReport, generation: int, compact: bool = False, filtered: bool = False) -> None:
    summary = (report.generation_summaries or {}).get(generation)
    if summary is None:
        print(f" 🕰️  Architecture Generation #{generation}")
        return
    panel_width = 56
    def row(label: str, value: str) -> None:
        inner = f" {label:<16} {value}"
        print(f" │  │{inner:<{panel_width}}│")
    def structural_mix_value() -> str:
        parts = []
        if summary.incremental_count: parts.append(f"{summary.incremental_count} incremental")
        if summary.structural_count: parts.append(f"{summary.structural_count} structural")
        return " / ".join(parts) if parts else "0"
    dom_sig = summary.dominant_snapshot_sig[:24] if summary.dominant_snapshot_sig else "n/a"
    generation_share_pct = int(round(summary.dominant_share_of_generation * 100)) if summary.dominant_share_of_generation > 0 else 0
    repo_share_pct = int(round((summary.generation_distinct_commit_count / report.total_commits) * 100)) if report.total_commits > 0 else 0
    print(f" 🕰️  Architecture Generation #{generation}\n │")
    title_padded = " Generation Summary "
    print(f" │  ┌{title_padded}{'─' * (56 - len(title_padded))}┐")
    row("Boundary cause", summary.cause_label)
    snapshots_value = str(summary.snapshot_count) + (f" · {summary.repeated_treesig_count} {'TreeSig' if summary.repeated_treesig_count == 1 else 'TreeSigs'}" if summary.repeated_treesig_count else "")
    row("Snapshots", snapshots_value)
    row("Generation span", f"{summary.generation_distinct_commit_count} commits")
    row("Repo share", f"{repo_share_pct}%")
    row("Structural mix", structural_mix_value())
    print(" │  │-- Dominant snapshot -----------------------------------│\n │  │ " + f"{dom_sig:<55}│")
    row("Lifespan", f"{summary.dominant_effective_commits} commits")
    row("Generation share", f"{generation_share_pct}%")
    if summary.repeated_treesig_count: row("Repeated TreeSigs", str(summary.repeated_treesig_count))
    print(" │  └────────────────────────────────────────────────────────┘\n │")

def _render_lifespan_and_badges(entry: SnapshotEntry, branch: str, trunk: str, markers: TimelineMarkers) -> None:
    icon = shape_icon(entry.shape) or _shape_icon_fallback(entry.shape)
    if icon == "•": icon = _shape_icon_fallback(entry.shape)
    badges = []
    if entry.dominance:
        if entry.dominance.is_dominant: badges.append("[dominant]")
        if entry.dominance.is_long_lived: badges.append("[long-lived]")
        if entry.dominance.is_short_lived: badges.append("[short-lived]")
    if entry.lifespan and entry.lifespan.run_count > 1: badges.append("[repeat]")
    if entry.is_current: badges.append("            ← [CURRENT]")
    marker = markers.get_snapshot_marker(entry.trigger.topo_id) if entry.trigger else ""
    print(f" {branch} {icon} {entry.snapshot_sig[:24]:<26} [{entry.shape_label or entry.shape or 'unknown'}]{(' · ' + ' · '.join(badges)) if badges else ''}{marker}")
    if entry.lifespan:
        if entry.lifespan.run_count <= 1:
            print(f" {trunk}   ├- Lifespan: {entry.lifespan.total_commits} commit{'s' if entry.lifespan.total_commits != 1 else ''} · {_format_lifespan_date_span(entry.lifespan.first_seen_date, entry.lifespan.last_seen_date)}")
        else:
            print(f" {trunk}   ├- Lifespan: {entry.lifespan.total_commits} commits across {entry.lifespan.run_count} runs · first {entry.lifespan.first_seen_date} · last {entry.lifespan.last_seen_date}")

def _render_commit_line(ref, trunk: str, annotate_operational: bool = False, markers: TimelineMarkers = None) -> None:
    rid_label = f"ID #{ref.topo_id}" if ref.topo_id is not None else f"commit {ref.commit_sig}"
    kind = _operational_kind(ref.subject) if annotate_operational and _is_operational_ref(ref) else ""
    print(f" {trunk}   │      {rid_label} · {ref.date} · {ref.commit_sig}{f' · [operational: {kind}]' if kind else ''}{markers.get_commit_marker(ref.topo_id) if markers else ''}\n {trunk}   │      {fmt_subject(ref.subject)}")

def _render_commit_block(rows: list, trunk: str, show_operational: bool = True, compact: bool = False, markers: TimelineMarkers = None) -> None:
    vis = [r for r in rows if not _is_operational_ref(r) or show_operational]
    hid = [r for r in rows if _is_operational_ref(r) and not show_operational]
    for r in vis: _render_commit_line(r, trunk, show_operational, markers)
    if hid: print(f" {trunk}   │      · {len(hid)} operational omitted ({truncate_subject('/'.join(sorted(set(filter(None, (_operational_kind(x.subject) for x in hid))))), limit=COMPACT_OMISSION_LIMIT)}); use --show-operational")

def _render_trigger(entry: SnapshotEntry, trunk: str, markers: TimelineMarkers) -> None:
    print(f" {trunk}   ├- Trigger:")
    if entry.trigger and entry.trigger.commit_sig:
        print(f" {trunk}   │      {f'ID #{entry.trigger.topo_id}' if entry.trigger.topo_id is not None else 'ID #?'} · {entry.trigger.date} · {entry.trigger.commit_sig}{markers.get_commit_marker(entry.trigger.topo_id)}")
        print(f" {trunk}   │      {fmt_subject(entry.trigger.subject)}")
    else:
        print(f" {trunk}   │      unavailable")

def _render_also_used(entry: SnapshotEntry, trunk: str, show_operational: bool = True, compact: bool = False, reverse: bool = False, markers: TimelineMarkers = None) -> None:
    s = list(reversed(entry.successive_used_by)) if reverse and entry.successive_used_by else list(entry.successive_used_by or [])
    r = [list(reversed(x)) for x in reversed(entry.reappeared_runs or [])] if reverse else list(entry.reappeared_runs or [])
    if s:
        print(f" {trunk}   ├- Also used by {len(s)} other successive {'commit' if len(s) == 1 else 'commits'}:")
        _render_commit_block(s, trunk, show_operational, compact, markers)
    for run in r:
        print(f" {trunk}   ├- Reappeared in {len(run)} later {'commit' if len(run) == 1 else 'commits'}:")
        _render_commit_block(run, trunk, show_operational, compact, markers)

def _generation_clip_counts(report: HistoryReport, entries: list[SnapshotEntry], generation: int) -> tuple[list[SnapshotEntry], list[SnapshotEntry]]:
    all_gen = [e for e in report.entries if e.generation == generation]
    v = sorted([e for e in entries if e.generation == generation], key=lambda x: x.generation_index)
    return (all_gen[:v[0].generation_index] if v else [], all_gen[v[-1].generation_index + 1:] if v else [])

def render_entry(report: HistoryReport, entry: SnapshotEntry, next_gen: int | None, open_g: int | None, compact: bool = False, show_op: bool = True, filtered_g: bool = False, show_sum: bool = True, early_omit: int = 0, reverse: bool = False, early_m: str = "", markers: TimelineMarkers = None) -> int:
    b, t = ("└" if next_gen != entry.generation else "├"), (" " if next_gen != entry.generation else "│")
    if open_g != entry.generation:
        if open_g is not None: print()
        if show_sum: _render_generation_panel(report, entry.generation, compact, filtered_g)
        else: print(f" 🕰️  Architecture Generation #{entry.generation}\n │")
        if early_omit > 0: print(f" │  … {early_omit} {'later' if reverse else 'earlier'} snapshots compacted{early_m}")
        open_g = entry.generation
    _render_lifespan_and_badges(entry, b, t, markers)
    _render_trigger(entry, t, markers)
    _render_also_used(entry, t, show_op, compact, reverse, markers)
    print(f" {t}   └ Details: {entry.generator_version} · {entry.mode} · {entry.selected_files}/{entry.total_files} files · {entry.size_bytes}B" if compact else f" {t}   ├- Details: {entry.generator_version} · {entry.mode} · sampled {entry.selected_files} of {entry.total_files} files\n {t}   └- Debug: generated {entry.generated_at}{f' · validation={entry.mode.split("-")[-1]}' if "-" in entry.mode else ''} · {entry.size_bytes}B")
    return open_g

def render_history_report(report: HistoryReport, reverse: bool = False, compact: bool = False, show_operational: bool = True, since: str | None = None, until: str | None = None, generation: str | None = None, snapshot_prefix: str | None = None, commit_target: str | None = None, smart_target: str | None = None, only_reappeared: bool = False) -> None:
    if report.total_blueprints == 0 and report.total_commits == 0:
        print("\n  (no snapshot files found)\n")
        return
    markers = TimelineMarkers(report, commit_target=commit_target, snapshot_prefix=snapshot_prefix, smart_target=smart_target, since=since, until=until)
    entries = [e for e in (report.entries if not reverse else reversed(report.entries)) if not compact or (e.dominance and e.dominance.is_dominant)]
    if not entries:
        print("\n  (no snapshots matched the current filters)\n")
        return
    if not (len(report.entries) != report.total_blueprints or len({e.generation for e in report.entries}) != report.total_generations):
        render_summary(report)
    else:
        _render_filtered_header(report, entries, reverse, since, until, generation, snapshot_prefix, commit_target, only_reappeared, compact, markers)
    def get_hidden_m(s_list):
        if not compact or not s_list: return ""
        t = set()
        for x in s_list:
            if x.trigger: t.add(x.trigger.topo_id)
            for c in (x.successive_used_by or []): t.add(c.topo_id)
            for run in (x.reappeared_runs or []):
                for c in run: t.add(c.topo_id)
        hs, he = (markers.start and markers.start['topo'] in t), (markers.end and markers.end['topo'] in t)
        if hs and he: return f"          <- [{'Target' if markers.is_single else 'Range Start & End'} hidden by --compact]"
        if hs: return f"          <- [{'Target' if markers.is_single else 'Range Start'} hidden by --compact]"
        if he: return "          <- [Range End hidden by --compact]"
        return ""
    open_g = None
    for idx, entry in enumerate(entries):
        es, ls = _generation_clip_counts(report, entries, entry.generation)
        se_s, sl_s = (ls if reverse else es), (es if reverse else ls)
        next_g = entries[idx + 1].generation if idx + 1 < len(entries) else None
        open_g = render_entry(report, entry, next_g, open_g, compact, show_operational, len(entries) < len(report.entries), not (len(report.entries) != report.total_blueprints or len({e.generation for e in report.entries}) != report.total_generations) or generation is not None, len(se_s), reverse, get_hidden_m(se_s), markers)
        if next_g != entry.generation and sl_s: print(f" │  … {len(sl_s)} {'earlier' if reverse else 'later'} snapshots compacted{get_hidden_m(sl_s)}")
    if compact: print()
    else:
        latest = entries[-1] if entries else None
        if latest and not (len(report.entries) != report.total_blueprints):
            print(f"\n   Current Blueprint  arch-G{latest.generation}-{latest.snapshot_sig[:16]}.md")
            for cand in [Path(f"arch-G{latest.generation}-{latest.snapshot_sig[:16]}.md"), Path(".architecture") / f"arch-G{latest.generation}-{latest.snapshot_sig[:16]}.md"]:
                if cand.exists():
                    try: print(cand.read_text().rstrip())
                    except: pass
                    break
    print()
