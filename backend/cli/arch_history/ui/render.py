from __future__ import annotations
from pathlib import Path
from backend.services.architecture.models import (
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
    print("   Summary")
    print(f"   {'─' * 83}")
    # Safeguard against None totals in DB-first reports.
    total_commits = report.total_commits or 0
    total_blueprints = report.total_blueprints or 0
    total_generations = report.total_generations or 0
    _p_topos = [e.trigger.topo_id for e in report.entries if e.trigger and e.trigger.topo_id is not None]
    if _p_topos:
        _p_range = f"#{min(_p_topos)}-#{max(_p_topos)}"
        _p_count = max(_p_topos) - min(_p_topos) + 1
    else:
        _p_range = "none"
        _p_count = 0
    print(f"   💾 Commits       {total_commits:<3}  (total repo history)")
    if 0 < _p_count < total_commits:
        _p_range_desc = f"#{max(_p_topos)} to #{min(_p_topos)}"
        # Count includes both trigger and successive-use commits
        _total_processed = len(getattr(report, 'processed_commits', []))
        print(f"   📊 Processed     {_total_processed:<3}  ({_p_range_desc})")
    print(f"   📐 Snapshots     {total_blueprints:<3}  (architecture artifacts)")
    print(f"   🕰️  Boundaries    {total_generations:<3} (structural shifts)")
    try:
        from backend.services.db.reader import read_vacuums
        _vacs = read_vacuums(report.repo_label)
        if _vacs:
            _v_total = sum(v["commit_count"] for v in _vacs)
            _v_ranges = ", ".join(f"#{v['vacuum_start_topo']}-#{v['vacuum_end_topo']}" for v in _vacs)
            print(f"   ⚠️  Vacuums       {len(_vacs):<3}  ({_v_total} commits: {_v_ranges})")
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        pass
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
    generation_label = (f"{generations[0]}" if len(generations) == 1 else f"last {len(generations)} ({generations[0]}..{generations[-1]})") if generations else "?"
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
    print(f"\n🔎 Architecture Blueprint Slice — [{report.repo_display}]\n   Filters: {filter_label}\n   Range: {range_label}\n   Boundaries: {generation_label}\n   Order: {order_label}")
    if compact:
        print("   Note: Compact mode displays only dominant snapshots per boundary era.\n         Lifespan and reappearance metadata preserve full historical context\n         and may extend outside the exact numeric filter bounds.")
    else:
        print("   Note: Snapshot lifespan and reappearance metadata may extend beyond the selected range.\n         This intentionally preserves the full lifecycle of any snapshot overlapping the window.")
    print()

def _render_era_panel(report: HistoryReport, generation: int, compact: bool = False, filtered: bool = False) -> None:
    summary = (report.generation_summaries or {}).get(generation)
    max_gen = max((e.generation for e in report.entries), default=generation)
    is_head_era = (generation == max_gen)

    head_is_structural = False
    if is_head_era:
        head_entries = [e for e in report.entries if e.generation == generation]
        if head_entries:
            head_shape = head_entries[0].shape or ""
            head_is_structural = any(
                head_shape.startswith(p) for p in ("major:", "multi-dir:")
            ) and head_shape != "major:head"

    panel_width = 56
    dash_char = '\u2500'

    # Build title and top border line
    if is_head_era:
        if head_is_structural:
            title = " Current Architecture Head \u2014 structural shift "
        else:
            title = " Current Architecture Head "
        dashes = "\u2500" * max(0, panel_width - len(title))
        top_line = f" \U0001f4cd \u250c{title}{dashes}\u2510"
    else:
        back_n = max_gen - generation
        unit = "Boundary" if back_n == 1 else "Boundaries"
        title = f" {back_n} {unit} back "
        dashes = "\u2500" * max(0, panel_width - len(title))
        top_line = f"\U0001f570\ufe0f   \u250c{title}{dashes}\u2510"

    if summary is None:
        print(top_line)
        dash = '\u2500'
        print(f" \u2502  \u2514{dash_char * panel_width}\u2518")
        return

    def row(label: str, value: str) -> None:
        inner = f" {label:<16} {value}"
        emoji_extra = sum(1 for c in inner if ord(c) > 0x2600)
        effective_len = len(inner) + emoji_extra
        if effective_len > panel_width:
            over = effective_len - panel_width + 1
            inner = inner[:len(inner) - over] + "\u2026"
            emoji_extra = sum(1 for c in inner if ord(c) > 0x2600)
        pad = panel_width - len(inner) - emoji_extra
        if pad > 0:
            inner = inner + " " * pad
        print(f" \u2502  \u2502{inner}\u2502")

    from backend.cli.arch_history.ui.format import shape_icon as _cause_icon
    cause_emoji = _cause_icon(summary.cause_tag)

    era_share_pct = int(round(summary.dominant_share_of_generation * 100)) if summary.dominant_share_of_generation > 0 else 0
    # Safeguard against None total_commits in DB-first reports.
    total_commits = report.total_commits or 0
    repo_share_pct = int(round((summary.generation_distinct_commit_count / total_commits) * 100)) if total_commits > 0 else 0

    def structural_mix_value() -> str:
        parts = []
        if summary.incremental_count: parts.append(f"{summary.incremental_count} incremental")
        if summary.structural_count: parts.append(f"{summary.structural_count} structural")
        return " + ".join(parts) if parts else "0"

    dom_sig = summary.dominant_snapshot_sig[:24] if summary.dominant_snapshot_sig else "n/a"

    print(top_line)
    row("Boundary cause", f"{cause_emoji} {summary.cause_label}")
    row("Repo share", f"{repo_share_pct}%")
    snapshots_value = str(summary.snapshot_count) + (f" \u00b7 {summary.repeated_treesig_count} {'TreeSig' if summary.repeated_treesig_count == 1 else 'TreeSigs'}" if summary.repeated_treesig_count else "")
    row("Snapshots", snapshots_value)
    row("Structural mix", structural_mix_value())
    row("Era span", f"{summary.generation_distinct_commit_count} commits")
    print(f" \u2502  \u2502{'-- Dominant snapshot -----------------------------------'}\u2502")
    print(f" \u2502  \u2502 {dom_sig:<{panel_width - 1}}\u2502")
    row("Era share", f"{era_share_pct}%")
    row("Lifespan", f"{summary.dominant_effective_commits} commits")
    if summary.repeated_treesig_count:
        row("Repeated TreeSigs", str(summary.repeated_treesig_count))
    print(f" \u2502  \u2514{dash_char * panel_width}\u2518")
    print(" \u2502")


def _render_lifespan_and_badges(entry: SnapshotEntry, branch: str, trunk: str, markers: TimelineMarkers) -> None:
    from backend.services.architecture.taxonomy import get_shape_metadata
    
    raw_shape = entry.shape or ""
    meta = get_shape_metadata(raw_shape)
    
    if raw_shape == "major:head":
        icon = "──"
        icon_pad = ""
    else:
        icon = meta.get("icon", "•")
        icon_pad = " "

    badges = []
    if entry.dominance and entry.dominance.is_dominant:
        badges.append("[dominant]")
    if entry.lifespan and entry.lifespan.run_count > 1:
        badges.append("[reappeared]")

    badge_str = f" · {' · '.join(badges)}" if badges else ""
    if entry.is_current:
        badge_str += "            ← [CURRENT]"

    marker = markers.get_snapshot_marker(entry.trigger.topo_id) if entry.trigger else ""
    
    display_label = entry.shape_label or meta.get("label", raw_shape or "unknown")
    
    print(f" {branch}{icon_pad}{icon} {entry.snapshot_sig[:24]:<26} [{display_label}]{badge_str}{marker}")

    if entry.lifespan:
        life_label = ""
        if entry.dominance and not entry.is_current:
            if entry.dominance.is_long_lived: life_label = " [long-lived]"
            elif entry.dominance.is_short_lived: life_label = " [short-lived]"

        if entry.lifespan.run_count <= 1:
            print(f" {trunk}   ├- Lifespan: {entry.lifespan.total_commits} commit{'s' if entry.lifespan.total_commits != 1 else ''} · {_format_lifespan_date_span(entry.lifespan.first_seen_date, entry.lifespan.last_seen_date)}{life_label}")
        else:
            print(f" {trunk}   ├- Lifespan: {entry.lifespan.total_commits} commits across {entry.lifespan.run_count} runs · first {entry.lifespan.first_seen_date} · last {entry.lifespan.last_seen_date}{life_label}")

def _fmt_date(iso_date: str | None) -> str:
    """Format ISO date (2026-05-16) to human display (May 16, '26)."""
    if not iso_date:
        return "?"
    try:
        from datetime import datetime
        dt = datetime.strptime(iso_date, "%Y-%m-%d")
        return dt.strftime("%b %d, '%y")
    except (ValueError, TypeError):
        return iso_date


def _render_commit_line(ref, trunk: str, annotate_operational: bool = False, markers: TimelineMarkers = None, is_last: bool = False) -> None:
    rid_label = f"ID #{ref.topo_id}" if ref.topo_id is not None else f"commit {ref.commit_sig}"
    kind = _operational_kind(ref.subject) if annotate_operational and _is_operational_ref(ref) else ""
    inner = " " if is_last else "│"
    print(f" {trunk}   {inner}      {rid_label} · {_fmt_date(ref.date)} · {ref.commit_sig}{f' · [operational: {kind}]' if kind else ''}{markers.get_commit_marker(ref.topo_id) if markers else ''}\n {trunk}   {inner}      {fmt_subject(ref.subject)}")

def _render_commit_block(rows: list, trunk: str, show_operational: bool = True, compact: bool = False, markers: TimelineMarkers = None, is_last: bool = False) -> None:
    vis = [r for r in rows if not _is_operational_ref(r) or show_operational]
    hid = [r for r in rows if _is_operational_ref(r) and not show_operational]
    for r in vis: _render_commit_line(r, trunk, show_operational, markers, is_last)
    if hid: 
        inner = " " if is_last else "│"
        print(f" {trunk}   {inner}      · {len(hid)} operational omitted ({truncate_subject('/'.join(sorted(set(filter(None, (_operational_kind(x.subject) for x in hid))))), limit=COMPACT_OMISSION_LIMIT)}); use --show-operational")

def _render_trigger(entry: SnapshotEntry, trunk: str, markers: TimelineMarkers, is_last: bool = False) -> None:
    cap = "└-" if is_last else "├-"
    inner = " " if is_last else "│"
    print(f" {trunk}   {cap} Trigger:")
    if entry.trigger and entry.trigger.commit_sig:
        print(f" {trunk}   {inner}      {f'ID #{entry.trigger.topo_id}' if entry.trigger.topo_id is not None else 'ID #?'} · {_fmt_date(entry.trigger.date)} · {entry.trigger.commit_sig}{markers.get_commit_marker(entry.trigger.topo_id)}")
        print(f" {trunk}   {inner}      {fmt_subject(entry.trigger.subject)}")
    else:
        print(f" {trunk}   {inner}      unscored workspace state (run scoring pipeline to link)")

def _render_also_used(entry: SnapshotEntry, trunk: str, show_operational: bool = True, compact: bool = False, reverse: bool = False, markers: TimelineMarkers = None) -> None:
    s = list(reversed(entry.successive_used_by)) if reverse and entry.successive_used_by else list(entry.successive_used_by or [])
    r = [list(reversed(x)) for x in reversed(entry.reappeared_runs or [])] if reverse else list(entry.reappeared_runs or [])
    
    total_blocks = (1 if s else 0) + len(r)
    current_block = 0
    
    if s:
        current_block += 1
        is_last = (compact and current_block == total_blocks)
        cap = "└-" if is_last else "├-"
        if compact and len(s) > 1:
            print(f" {trunk}   {cap} Also used by {len(s)} other successive commits until:")
            _render_commit_block([s[-1]], trunk, show_operational, compact, markers, is_last)
        else:
            print(f" {trunk}   {cap} Also used by {len(s)} other successive {'commit' if len(s) == 1 else 'commits'}:")
            _render_commit_block(s, trunk, show_operational, compact, markers, is_last)
    for run in r:
        current_block += 1
        is_last = (compact and current_block == total_blocks)
        cap = "└-" if is_last else "├-"
        if compact and len(run) > 1:
            print(f" {trunk}   {cap} Reappeared in {len(run)} later commits until:")
            _render_commit_block([run[-1]], trunk, show_operational, compact, markers, is_last)
        else:
            print(f" {trunk}   {cap} Reappeared in {len(run)} later {'commit' if len(run) == 1 else 'commits'}:")
            _render_commit_block(run, trunk, show_operational, compact, markers, is_last)

def _era_clip_counts(report: HistoryReport, entries: list[SnapshotEntry], generation: int) -> tuple[list[SnapshotEntry], list[SnapshotEntry]]:
    # Sort purely by generation index to guarantee chronological sequence
    all_gen = sorted([e for e in report.entries if e.generation == generation], key=lambda x: x.generation_index)
    v = sorted([e for e in entries if e.generation == generation], key=lambda x: x.generation_index)
    
    if not v or not all_gen: 
        return [], []
        
    # Match the exact absolute array indices to prevent off-by-one errors
    first_idx = next((i for i, e in enumerate(all_gen) if e.snapshot_sig == v[0].snapshot_sig), 0)
    last_idx = next((i for i, e in enumerate(all_gen) if e.snapshot_sig == v[-1].snapshot_sig), len(all_gen) - 1)
    
    return all_gen[:first_idx], all_gen[last_idx + 1:]

def render_entry(report: HistoryReport, entry: SnapshotEntry, next_gen: int | None, open_g: int | None, compact: bool, show_op: bool, filtered_g: bool, top_omission: list, bottom_omission: list, reverse: bool, markers: TimelineMarkers) -> int:
    is_last_in_era = (next_gen != entry.generation)
    
    # If we have hidden snapshots trailing below, hold the tree trunk open!
    if compact and bottom_omission:
        is_last_in_era = False

    b = "└" if is_last_in_era else "├"
    t = " " if is_last_in_era else "│"

    if open_g != entry.generation:
        if open_g is not None: print()
        _render_era_panel(report, entry.generation, compact, filtered_g)
        open_g = entry.generation

    # Print top omission (chronologically later snapshots hidden above)
    if compact and top_omission:
        suffix = "s" if len(top_omission) != 1 else ""
        label = "later" if reverse else "earlier"
        print(f" │   … {len(top_omission)} {label} snapshot{suffix} compacted")

    _render_lifespan_and_badges(entry, b, t, markers)
    has_also_used = bool(entry.successive_used_by or entry.reappeared_runs)
    _render_trigger(entry, t, markers, is_last=(compact and not has_also_used))
    _render_also_used(entry, t, show_op, compact, reverse, markers)

    import os
    is_debug = str(os.environ.get("MATRIX_DEBUG", "false")).lower() in ("1", "true", "yes", "on")
    if not compact:
        if is_debug:
            print(f" {t}   ├- Details: {entry.generator_version} · {entry.mode} · sampled {entry.selected_files} of {entry.total_files} files")
            val_mode = f' · validation={entry.mode.split("-")[-1]}' if '-' in entry.mode else ''
            print(f' {t}   └- Debug: generated {entry.generated_at}{val_mode} · {entry.size_bytes}B')
        else:
            print(f" {t}   └ Details: {entry.generator_version} · {entry.mode} · sampled {entry.selected_files} of {entry.total_files} files")

    # Print bottom omission (chronologically earlier snapshots hidden below)
    if compact and bottom_omission:
        suffix = "s" if len(bottom_omission) != 1 else ""
        label = "earlier" if reverse else "later"
        cap = "└" if (next_gen != entry.generation) else "├"
        print(f" {cap}   … {len(bottom_omission)} {label} snapshot{suffix} compacted")

    return open_g

def render_history_report(report: HistoryReport, reverse: bool = False, compact: bool = False, show_operational: bool = True, since: str | None = None, until: str | None = None, generation: str | None = None, snapshot_prefix: str | None = None, commit_target: str | None = None, smart_target: str | None = None, only_reappeared: bool = False) -> None:
    total_blueprints = report.total_blueprints or 0
    total_commits = report.total_commits or 0
    if total_blueprints == 0 and total_commits == 0:
        print("\n  (no snapshot files found)\n")
        return
    markers = TimelineMarkers(report, commit_target=commit_target, snapshot_prefix=snapshot_prefix, smart_target=smart_target, since=since, until=until)
    entries = [e for e in (report.entries if not reverse else reversed(report.entries)) if not compact or (e.dominance and e.dominance.is_dominant)]
    if not entries:
        print("\n  (no snapshots matched the current filters)\n")
        return
        
    filtered_g = (len(report.entries) != report.total_blueprints or len({e.generation for e in report.entries}) != report.total_generations) or generation is not None
    if not filtered_g:
        render_summary(report)
    else:
        _render_filtered_header(report, entries, reverse, since, until, generation, snapshot_prefix, commit_target, only_reappeared, compact, markers)

    open_g = None
    for idx, entry in enumerate(entries):
        es, ls = _era_clip_counts(report, entries, entry.generation)
        
        # When printing Head->Tail, "later" commits occurred after the dominant one, so they print above it
        top_omission = ls if reverse else es
        bottom_omission = es if reverse else ls
        
        next_g = entries[idx + 1].generation if idx + 1 < len(entries) else None
        
        open_g = render_entry(report, entry, next_g, open_g, compact, show_operational, filtered_g, top_omission, bottom_omission, reverse, markers)

    if compact: print()

    try:
        from backend.services.db.reader import read_vacuums
        _bottom_vacs = read_vacuums(report.repo_label)
        if _bottom_vacs:
            _bv_total = sum(v.get("commit_count", 0) for v in _bottom_vacs)
            _bv_parts = []
            for v in _bottom_vacs:
                s = v.get("vacuum_end_topo", "?")
                e = v.get("vacuum_start_topo", "?")
                _bv_parts.append(f"#{s} to #{e}")
            print(f"\n ⚠️  Vacuum: {_bv_total} unscanned commits ({', '.join(_bv_parts)})")
    except Exception as _ve:
        pass

    _p_topos2 = [e2.trigger.topo_id for e2 in report.entries if e2.trigger and e2.trigger.topo_id is not None]
    if _p_topos2:
        _min_topo = min(_p_topos2)
        if _min_topo > 1:
            _unscanned = _min_topo - 1
            print(f"\n ⚠️  Vacuum: {_unscanned} unscanned commits (#{_min_topo - 1} to #1)")

    print()
