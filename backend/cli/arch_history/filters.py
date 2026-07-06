from __future__ import annotations

import re
from typing import List

from backend.cli.arch_history.models import HistoryReport, SnapshotEntry
from backend.cli.arch_history.arch_selectors import Selector, SelectorCategory, parse_selector, resolve_sig_category
from backend.cli.arch_history.data.metrics import _compute_generation_summaries


def _find_entry_by_commit_sig_prefix(entries: List[SnapshotEntry], prefix: str) -> SnapshotEntry | None:
    lowered = (prefix or "").strip().lower()
    if not lowered:
        return None
    for e in entries:
        t = e.trigger
        if t and (t.commit_sig or "").lower().startswith(lowered):
            return e
    return None


def _find_snapshot_by_sig_prefix(entries: List[SnapshotEntry], prefix: str) -> SnapshotEntry | None:
    lowered = (prefix or "").strip().lower()
    if not lowered:
        return None
    for e in entries:
        if (e.snapshot_sig or "").lower().startswith(lowered):
            return e
    return None


def _matches_selector_value(entry: SnapshotEntry, selector: str) -> bool:
    value = (selector or "").strip()
    if not value:
        return False

    trigger = entry.trigger
    if trigger is None:
        return False

    if value.isdigit():
        topo = int(value)
        lifespan = entry.lifespan
        if lifespan is not None:
            first_topo = lifespan.first_seen_topo_id
            last_topo = lifespan.last_seen_topo_id
            if first_topo is not None and last_topo is not None:
                return first_topo <= topo <= last_topo
        return trigger.topo_id == topo

    lowered = value.lower()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", lowered):
        return (trigger.date or "") == lowered

    if re.fullmatch(r"[0-9a-f]{6,40}", lowered):
        return (trigger.commit_sig or "").lower().startswith(lowered)

    return False


def filter_history_report(
    report: HistoryReport,
    *,
    since: str | None = None,
    until: str | None = None,
    generation: str | None = None,
    snapshot_prefix: str | None = None,
    commit_target: str | None = None,
    smart_target: str | None = None,
    only_reappeared: bool = False,
) -> HistoryReport:
    entries = list(report.entries)
    since_selector: Selector | None = parse_selector(since) if since else None
    until_selector: Selector | None = parse_selector(until) if until else None

    # Resolve hex-like selectors into COMMIT_SIG or SNAPSHOT_SIG categories.
    if since_selector and since_selector.category is None:
        since_selector = resolve_sig_category(since_selector, report)
    if until_selector and until_selector.category is None:
        until_selector = resolve_sig_category(until_selector, report)

    # Enforce that since and until, if both present, use the same selector category.
    if since_selector and until_selector:
        if since_selector.category != until_selector.category:
            raise ValueError(
                "since and until must use the same type: "
                "both topo-id, both date, both commit signature, or both snapshot signature."
            )

    if generation is not None:
        if "-" in str(generation):
            start_g, end_g = map(int, generation.split("-"))
            entries = [e for e in entries if start_g <= e.generation <= end_g]
        else:
            entries = [e for e in entries if e.generation == int(generation)]

    target_val = smart_target or commit_target or snapshot_prefix
    if target_val:
        strict_type = "commit" if commit_target else ("snapshot" if snapshot_prefix else None)

        def deep_find_topo(val_str):
            if not val_str:
                return None
            v = str(val_str).strip().lower()

            matches: list[dict] = []
            if v.isdigit():
                matches.append({"topo": int(v), "type": "commit"})

            for e in report.entries:
                if e.snapshot_sig and e.snapshot_sig.lower().startswith(v):
                    matches.append(
                        {
                            "topo": e.trigger.topo_id if e.trigger else 0,
                            "type": "snapshot",
                        }
                    )
                if e.trigger and e.trigger.commit_sig and e.trigger.commit_sig.lower().startswith(v):
                    matches.append({"topo": e.trigger.topo_id, "type": "commit"})
                for c in (e.successive_used_by or []):
                    if c.commit_sig.lower().startswith(v):
                        matches.append({"topo": c.topo_id, "type": "commit"})
                for run in (e.reappeared_runs or []):
                    for c in run:
                        if c.commit_sig.lower().startswith(v):
                            matches.append({"topo": c.topo_id, "type": "commit"})

            if not matches:
                return None

            if strict_type and not any(m["type"] == strict_type for m in matches):
                found_type = matches[0]["type"]
                raise ValueError(
                    f"'{val_str}' is a {found_type} signature, but you used the --{strict_type} flag. "
                    f"Use --{found_type} or omit strict flags entirely for argument auto-detection to filter mixed types."
                )

            valid_matches = [m for m in matches if m["type"] == strict_type] if strict_type else matches
            return valid_matches[0]["topo"]

        if "-" in str(target_val):
            c1, c2 = str(target_val).split("-", 1)
            t1 = deep_find_topo(c1)
            t2 = deep_find_topo(c2)
            t1_bound = t1 if t1 is not None else 0
            t2_bound = t2 if t2 is not None else 999999
            if t1_bound > t2_bound:
                t1_bound, t2_bound = t2_bound, t1_bound
            entries = [
                e for e in entries
                if e.trigger and t1_bound <= e.trigger.topo_id <= t2_bound
            ]
        else:
            deep_find_topo(target_val)  # Triggers validation exception immediately if mismatched

            def contains_target(e, tgt):
                tgt_low = str(tgt).lower()
                if (strict_type == "snapshot" or not strict_type) and e.snapshot_sig and e.snapshot_sig.lower().startswith(tgt_low):
                    return True
                if strict_type == "snapshot":
                    return False

                if e.trigger and (str(e.trigger.topo_id) == tgt_low or e.trigger.commit_sig.lower().startswith(tgt_low)):
                    return True
                for c in (e.successive_used_by or []):
                    if str(c.topo_id) == tgt_low or c.commit_sig.lower().startswith(tgt_low):
                        return True
                for run in (e.reappeared_runs or []):
                    for c in run:
                        if str(c.topo_id) == tgt_low or c.commit_sig.lower().startswith(tgt_low):
                            return True
                return False

            entries = [e for e in entries if contains_target(e, target_val)]

    if only_reappeared:
        entries = [e for e in entries if e.lifespan is not None and e.lifespan.run_count > 1]

    if since_selector:
        entries = [e for e in entries if _matches_selector_value(e, since_selector.value)]
    if until_selector:
        entries = [e for e in entries if _matches_selector_value(e, until_selector.value)]

    generation_summaries = _compute_generation_summaries(entries) if entries else {}
    total_generations = max((e.generation for e in entries), default=0)

    return HistoryReport(
        repo_label=report.repo_label,
        repo_display=report.repo_display,
        total_commits=report.total_commits,
        total_blueprints=len(entries),
        total_generations=total_generations,
        current=report.current,
        entries=entries,
        generation_summaries=generation_summaries,
    )
