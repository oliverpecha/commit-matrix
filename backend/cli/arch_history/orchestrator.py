from __future__ import annotations

import json
import re
from dataclasses import asdict
from pathlib import Path

from backend.services.pipeline.pipeline_config import HOST_REPO_NAME

from backend.cli.arch_history.models import (
    BoundaryInfo,
    BoundaryScope,
    CurrentBlueprint,
    DisplacedSnapshot,
    GenerationSummaryMetrics,
    HistoryReport,
    SnapshotEntry,
    CommitRef,
)
from backend.cli.arch_history.taxonomy import (
    normalize_cause_tag,
    get_boundary_cause_label,
    get_boundary_magnitude,
)
from backend.cli.arch_history.arch_selectors import Selector, SelectorCategory, parse_selector, resolve_sig_category
from backend.cli.arch_history.data.loader import (
    _load_used_by_map,
    _compute_tree_sig_eras,
    derive_repo_display,
    _load_snapshot_meta,
    _compute_generations,
    _topo_key_for_snapshot,
    _resolve_commit_ref,
    _is_operational,
    _display_mode,
    human_shape_label,
)
from backend.cli.arch_history.data.metrics import (
    _compute_snapshot_lifespan_metrics,
    _compute_snapshot_composition_metrics,
    _compute_snapshot_dominance_metrics,
    _assign_dominant_flags,
    _compute_generation_summaries,
    validate_commit_snapshot_invariant,
)

def _reassign_generations(entries: list[SnapshotEntry]) -> list[SnapshotEntry]:
    ordered = sorted(
        entries,
        key=lambda e: (e.trigger.topo_id if e.trigger and e.trigger.topo_id is not None else 10_000_000)
    )
    current_gen = 1
    gen_idx = 0
    for idx, entry in enumerate(ordered):
        if idx > 0 and not (entry.shape or "").startswith("leaf-only"):
            current_gen += 1
            gen_idx = 0
        entry.generation = current_gen
        entry.generation_index = gen_idx
        gen_idx += 1
    return ordered

def _reanchor_reuse_by_signature(entries: list[SnapshotEntry]) -> list[SnapshotEntry]:
    ordered = sorted(
        entries,
        key=lambda e: (e.trigger.topo_id if e.trigger and e.trigger.topo_id is not None else 10_000_000)
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
            key=lambda r: (r.topo_id if r.topo_id is not None else 10_000_000, r.commit_sig)
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

def _find_entry_by_commit_sig_prefix(entries: list[SnapshotEntry], prefix: str) -> SnapshotEntry | None:
    lowered = (prefix or "").strip().lower()
    if not lowered:
        return None
    for e in entries:
        t = e.trigger
        if t and (t.commit_sig or "").lower().startswith(lowered):
            return e
    return None


def _find_snapshot_by_sig_prefix(entries: list[SnapshotEntry], prefix: str) -> SnapshotEntry | None:
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
        strict_type = 'commit' if commit_target else ('snapshot' if snapshot_prefix else None)

        def deep_find_topo(val_str):
            if not val_str: return None
            v = str(val_str).strip().lower()
            
            matches = []
            if v.isdigit(): matches.append({'topo': int(v), 'type': 'commit'})

            for e in report.entries:
                if e.snapshot_sig and e.snapshot_sig.lower().startswith(v): 
                    matches.append({'topo': e.trigger.topo_id if e.trigger else 0, 'type': 'snapshot'})
                if e.trigger and e.trigger.commit_sig and e.trigger.commit_sig.lower().startswith(v): 
                    matches.append({'topo': e.trigger.topo_id, 'type': 'commit'})
                for c in (e.successive_used_by or []):
                    if c.commit_sig.lower().startswith(v): matches.append({'topo': c.topo_id, 'type': 'commit'})
                for run in (e.reappeared_runs or []):
                    for c in run:
                        if c.commit_sig.lower().startswith(v): matches.append({'topo': c.topo_id, 'type': 'commit'})

            if not matches: return None
            
            if strict_type and not any(m['type'] == strict_type for m in matches):
                found_type = matches[0]['type']
                raise ValueError(f"'{val_str}' is a {found_type} signature, but you used the --{strict_type} flag. Use --{found_type} or omit strict flags entirely for argument auto-detection to filter mixed types.")
                
            valid_matches = [m for m in matches if m['type'] == strict_type] if strict_type else matches
            return valid_matches[0]['topo']

        if "-" in str(target_val):
            c1, c2 = str(target_val).split("-", 1)
            t1 = deep_find_topo(c1)
            t2 = deep_find_topo(c2)
            t1_bound = t1 if t1 is not None else 0
            t2_bound = t2 if t2 is not None else 999999
            if t1_bound > t2_bound: t1_bound, t2_bound = t2_bound, t1_bound
            entries = [e for e in entries if e.trigger and t1_bound <= e.trigger.topo_id <= t2_bound]
        else:
            deep_find_topo(target_val) # Triggers validation exception immediately if mismatched
            def contains_target(e, tgt):
                tgt_low = str(tgt).lower()
                if (strict_type == 'snapshot' or not strict_type) and e.snapshot_sig and e.snapshot_sig.lower().startswith(tgt_low): return True
                if strict_type == 'snapshot': return False
                
                if e.trigger and (str(e.trigger.topo_id) == tgt_low or e.trigger.commit_sig.lower().startswith(tgt_low)): return True
                for c in (e.successive_used_by or []):
                    if str(c.topo_id) == tgt_low or c.commit_sig.lower().startswith(tgt_low): return True
                for run in (e.reappeared_runs or []):
                    for c in run:
                        if str(c.topo_id) == tgt_low or c.commit_sig.lower().startswith(tgt_low): return True
                return False
                
            entries = [e for e in entries if contains_target(e, target_val)]

    if only_reappeared:
        entries = [e for e in entries if e.lifespan is not None and e.lifespan.run_count > 1]

    if since:
        entries = [e for e in entries if e.trigger and e.trigger.date and e.trigger.date >= since]
    if until:
        entries = [e for e in entries if e.trigger and e.trigger.date and e.trigger.date <= until]

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

def history_report_to_dict(report: HistoryReport) -> dict:
    """DEPRECATED — use serialize_history_report_to_contract().

    Raw ``dataclasses.asdict()`` pass-through with no schema stability
    guarantees.  Scheduled for removal once all consumers migrate to C1.
    """
    import warnings
    warnings.warn(
        "history_report_to_dict() is deprecated; "
        "use serialize_history_report_to_contract()",
        DeprecationWarning,
        stacklevel=2,
    )
    return asdict(report)

def build_history_report(repo_label: str | None = None, debug: bool | None = None) -> HistoryReport:
    import os
    _debug = debug if debug is not None else os.environ.get("ARCH_DEBUG", "").strip() == "1"

    def _dbg(*args) -> None:
        if _debug:
            print("[arch:dbg]", *args, flush=True)

    repo_label = repo_label or HOST_REPO_NAME
    repo_path = Path(".").resolve()
    repo_display = derive_repo_display(repo_path, repo_label)

    data_dir = Path("data") / repo_label
    meta_path = data_dir / f"{repo_label}_arch_blueprint.meta.json"
    versions_dir = data_dir / "architecture_versions"
    used_by_map, topo_by_commit_sig, ledger_rows = _load_used_by_map(repo_label)

    _dbg(f"ledger: {len(used_by_map)} unique TreeSigs (legacy ArchSig compatible), {len(topo_by_commit_sig)//2} commit signatures in topo map")
    era_by_sha, runs_by_sig = _compute_tree_sig_eras(ledger_rows)
    _dbg(f"eras: {sum(len(runs) for runs in runs_by_sig.values())} contiguous TreeSig eras across {len(ledger_rows)} ledger rows")

    current_meta: dict = {}
    if meta_path.exists():
        try:
            raw = meta_path.read_text(encoding="utf-8").strip()
            if raw:
                current_meta = json.loads(raw)
        except Exception:
            current_meta = {}

    current = CurrentBlueprint(
        snapshot_sig=current_meta.get("tree_signature", ""),
        generated_at=current_meta.get("generated_at", "—"),
        generator_version=current_meta.get("generator_version", "—"),
        mode=(current_meta.get("change_summary") or {}).get("mode", "—"),
        shape=(current_meta.get("change_summary") or {}).get("change_shape", "—"),
        total_files=(current_meta.get("change_summary") or {}).get("total_files", "—"),
        selected_files=(current_meta.get("change_summary") or {}).get("selected_files_count", "—"),
    )
    _dbg(f"current sig: {current.snapshot_sig[:16]}...")

    if not versions_dir.exists():
        _dbg("no versions_dir found, returning empty report")
        return HistoryReport(
            repo_label=repo_label,
            repo_display=repo_display,
            total_commits=0,
            total_blueprints=0,
            total_generations=0,
            current=current,
            entries=[],
        )

    raw_snapshots = [p for p in versions_dir.glob("arch-*.md") if p.is_file()]
    snapshots = sorted(
        raw_snapshots,
        key=lambda p: _topo_key_for_snapshot(p, _load_snapshot_meta(p), topo_by_commit_sig),
    )
    generations = _compute_generations(snapshots) if snapshots else []
    max_gen = generations[-1][0] if generations else 0

    _dbg(f"snapshots: {len(snapshots)}  generations span: 1..{max_gen}")
    for gen_num, snap, meta in generations:
        sig = meta.get("tree_signature", snap.stem[len("arch-"):])
        shape = (meta.get("change_summary") or {}).get("change_shape", "unknown")
        _dbg(f"  snap [{gen_num}] {sig[:16]}... shape={shape} file={snap.name}")

    all_used_commits: set[str] = set()
    for entries in used_by_map.values():
        for row in entries:
            sha = (row.get("sha") or "").strip()
            if sha:
                all_used_commits.add(sha)

    entries_out: list[SnapshotEntry] = []

    for gen_num, snap, meta in generations:
        sig = meta.get("tree_signature", snap.stem[len("arch-"):])
        shape = (meta.get("change_summary") or {}).get("change_shape", "—")
        mode = (meta.get("change_summary") or {}).get("mode", "—")
        generated_at = meta.get("generated_at", "—")[:19].replace("T", " ")
        size = snap.stat().st_size

        is_current = bool(
            current.snapshot_sig and (
                current.snapshot_sig == sig
                or current.snapshot_sig.startswith(sig[:16])
                or sig.startswith(current.snapshot_sig[:16])
            )
        )

        _dbg(f"\n  --- building entry gen={gen_num} sig={sig[:16]}... shape={shape}")

        all_used_rows = used_by_map.get(sig, [])
        _dbg(f"      ledger rows for sig: {len(all_used_rows)}")
        for r in all_used_rows:
            _dbg(f"        topo={r.get('topo_id')} sha={r.get('sha','')[:7]} subj={r.get('subject','')[:50]}")

        cleaned_rows: list[dict] = []
        seen_shas: set[str] = set()
        for row in all_used_rows:
            subj = row.get("subject") or ""
            sha_full = (row.get("sha") or "").strip()
            sha7 = sha_full[:7]
            if not sha7 or sha7 in seen_shas:
                _dbg(f"        skip sha={sha7} (dup={sha7 in seen_shas})")
                continue
            seen_shas.add(sha7)
            row = dict(row)
            row["is_operational"] = _is_operational(subj)
            if row["is_operational"]:
                _dbg(f"        operational sha={sha7} subj={subj[:60]}")
            cleaned_rows.append(row)

        _dbg(f"      cleaned rows: {len(cleaned_rows)}")

        for row in cleaned_rows:
            sha_full = (row.get("sha") or "").strip()
            row["era_index"] = era_by_sha.get(sha_full) or era_by_sha.get(sha_full[:7]) or 1

        trigger_row = None
        if cleaned_rows:
            rows_with_topo = [r for r in cleaned_rows if isinstance(r.get("topo_id"), int)]
            trigger_row = min(rows_with_topo, key=lambda r: r["topo_id"]) if rows_with_topo else cleaned_rows[0]
            _dbg(
                f"      trigger_row: topo={trigger_row.get('topo_id')} "
                f"sha={trigger_row.get('sha','')[:7]} "
                f"subj={trigger_row.get('subject','')[:50]}"
            )
        else:
            _dbg("      no cleaned_rows — trigger unavailable")

        trigger = _resolve_commit_ref(repo_path, trigger_row, topo_by_commit_sig) if trigger_row else None

        also_used_by: list[CommitRef] = []
        successive_used_by: list[CommitRef] = []
        reappeared_runs: list[list[CommitRef]] = []

        runs = runs_by_sig.get(sig, [])
        trigger_sha = ((trigger_row or {}).get("sha") or "").strip()
        matched_run_index = None
        current_run_rows: list[dict] = []

        for idx, run in enumerate(runs):
            if any(((row.get("sha") or "").strip() == trigger_sha) for row in run):
                matched_run_index = idx
                current_run_rows = run
                break

        if trigger_row:
            for row in cleaned_rows:
                if row is trigger_row:
                    continue
                ref = _resolve_commit_ref(repo_path, row, topo_by_commit_sig)
                _dbg(f"      also_used: topo={ref.topo_id} sig={ref.commit_sig} subj={ref.subject[:50]}")
                also_used_by.append(ref)

            if current_run_rows:
                seen_trigger = False
                for row in current_run_rows:
                    sha = (row.get("sha") or "").strip()
                    if sha == trigger_sha:
                        seen_trigger = True
                        continue
                    if seen_trigger:
                        successive_used_by.append(_resolve_commit_ref(repo_path, row, topo_by_commit_sig))

            if matched_run_index is not None:
                for run in runs[matched_run_index + 1:]:
                    run_refs = [
                        _resolve_commit_ref(repo_path, row, topo_by_commit_sig)
                        for row in run
                        if (row.get("sha") or "").strip()
                    ]
                    if run_refs:
                        reappeared_runs.append(run_refs)

        entries_out.append(
            SnapshotEntry(
                generation=gen_num,
                generation_index=0,
                snapshot_sig=sig,
                shape=shape,
                generator_version=meta.get("generator_version", "—"),
                mode=_display_mode(mode),
                generated_at=generated_at,
                size_bytes=size,
                selected_files=(meta.get("change_summary") or {}).get("selected_files_count", "—"),
                total_files=(meta.get("change_summary") or {}).get("total_files", "—"),
                trigger=trigger,
                also_used_by=also_used_by,
                successive_used_by=successive_used_by,
                reappeared_runs=reappeared_runs,
                is_current=is_current,
                shape_label=meta.get("shape_label")
                or (meta.get("change_summary") or {}).get("change_shape_label")
                or human_shape_label(shape),
            )
        )

    entries_out = _reanchor_reuse_by_signature(entries_out)
    entries_out = _reassign_generations(entries_out)
    max_gen = entries_out[-1].generation if entries_out else 0

    for entry in entries_out:
        entry.lifespan = _compute_snapshot_lifespan_metrics(entry)
        entry.composition = _compute_snapshot_composition_metrics(entry)

    generation_effective_totals: dict[int, int] = {}
    for entry in entries_out:
        if entry.lifespan is None or entry.composition is None:
            raise ValueError("snapshot metrics missing before dominance pass")
        effective = max(0, entry.lifespan.total_commits - entry.composition.operational_commit_count)
        generation_effective_totals[entry.generation] = generation_effective_totals.get(entry.generation, 0) + effective

    for entry in entries_out:
        entry.dominance = _compute_snapshot_dominance_metrics(
            entry,
            generation_effective_total=generation_effective_totals.get(entry.generation, 0),
        )

    _assign_dominant_flags(entries_out)

    # Filter out zombie blueprints that have zero corresponding ledger history records
    entries_out = [e for e in entries_out if e.lifespan and e.lifespan.total_commits > 0]

    # Filter out zombie blueprints that have zero corresponding ledger history records
    entries_out = [e for e in entries_out if e.lifespan and e.lifespan.total_commits > 0]

    generation_summaries = _compute_generation_summaries(entries_out)
    topo_ids = [e.trigger.topo_id for e in entries_out if e.trigger and e.trigger.topo_id is not None]
    if topo_ids:
        _dbg(
            f"\n  coverage: {len(entries_out)} entries, topo range {min(topo_ids)}..{max(topo_ids)}"
        )
    else:
        _dbg("\n  coverage: no topo ids present on final entries")

    gen_sizes: dict[int, int] = {}
    for e in entries_out:
        gen_sizes[e.generation] = gen_sizes.get(e.generation, 0) + 1
    _dbg(f"  generation sizes: {gen_sizes}")

    _dbg(f"\n  total entries built: {len(entries_out)}")
    for entry in entries_out:
        topo = entry.trigger.topo_id if entry.trigger else None
        reuse_topos = [ref.topo_id for ref in entry.also_used_by if ref.topo_id is not None]
        dom = entry.dominance
        life = entry.lifespan
        comp = entry.composition
        _dbg(
            f"  final entry gen={entry.generation} topo={topo} "
            f"sig={entry.snapshot_sig[:16]}... shape={entry.shape} reuse={reuse_topos} "
            f"runs={life.run_count if life else '?'} total={life.total_commits if life else '?'} "
            f"op={comp.operational_commit_count if comp else '?'} "
            f"eff={dom.effective_commits if dom else '?'} dominant={dom.is_dominant if dom else '?'}"
        )

    try:
        import subprocess
        # Native, non-hack query to fetch every commit node across all graph branches combined
        proc = subprocess.run(["git", "rev-list", "--all", "--count"], capture_output=True, text=True, check=True)
        real_commit_count = int(proc.stdout.strip())
    except Exception as e:
        print(f"[arch-history debug] git total graph count failed: {e}")
        real_commit_count = len(all_used_commits)

    report = HistoryReport(
        repo_label=repo_label,
        repo_display=repo_display,
        total_commits=real_commit_count,
        total_blueprints=len(snapshots),
        total_generations=max_gen,
        current=current,
        entries=entries_out,
        generation_summaries=generation_summaries,
    )

    # Validate commit→snapshot invariant (warn by default, raise in debug mode).
    validate_commit_snapshot_invariant(report, debug=_debug)
    return report


# ─── C1 Contract Serialization ───────────────────────────────────────────────
#
# Design: canonical state (flags) + derived view (badges).
#   * flags  — authoritative typed booleans; agents/CI/policy use these.
#   * badges — read-only presentation tokens derived deterministically
#              from flags; UI renders these directly.  Never accepted as
#              input.  On conflict, flags wins.
#
# cause_tag / cause_label in generation summaries are routed through
# taxonomy.py boundary functions so internal classification changes
# never break the external contract.
#
# See: docs/architecture_history_metric_contract.md (ADR)
# ─────────────────────────────────────────────────────────────────────────────

CONTRACT_VERSION = "1.0"

_BOOLEAN_BADGE_RULES: list[tuple[str, str]] = [
    # (badge_token, flags_key)
    ("current",  "is_current"),
    ("dominant", "is_dominant"),
]

_LIFESPAN_BADGE_MAP: dict[str, str] = {
    "long":  "long_lived",
    "short": "short_lived",
}


def derive_badges(flags: dict) -> list[str]:
    """Deterministic derivation: flags dict -> badge token list.

    Handles boolean flags and the lifespan_class enum.
    Public so contract tests can assert:
        snapshot["badges"] == derive_badges(snapshot["flags"])
    """
    badges = [token for token, key in _BOOLEAN_BADGE_RULES if flags.get(key, False)]
    lc = flags.get("lifespan_class", "standard")
    if lc in _LIFESPAN_BADGE_MAP:
        badges.append(_LIFESPAN_BADGE_MAP[lc])
    return badges


def _build_snapshot_flags(entry: SnapshotEntry) -> dict:
    """Collapse scattered booleans into a single canonical flags dict.

    Internal model uses separate is_long_lived / is_short_lived booleans.
    External contract consolidates into a single lifespan_class enum:
      "long"     -- effective_commits >= 3 and longest_streak >= 3
      "short"    -- total_commits == 1
      "standard" -- everything else
    """
    dom = entry.dominance
    if dom:
        if dom.is_long_lived:
            lifespan_class = "long"
        elif dom.is_short_lived:
            lifespan_class = "short"
        else:
            lifespan_class = "standard"
    else:
        lifespan_class = "standard"

    return {
        "is_current":     entry.is_current,
        "is_dominant":    dom.is_dominant if dom else False,
        "lifespan_class": lifespan_class,
    }


def _serialize_commit_ref(ref: CommitRef) -> dict:
    return {
        "commit_sig": ref.commit_sig,
        "topo_id":    ref.topo_id,
        "date":       ref.date,
        "subject":    ref.subject,
    }


def _serialize_snapshot_entry(entry: SnapshotEntry) -> dict:
    flags = _build_snapshot_flags(entry)

    return {
        "generation":        entry.generation,
        "generation_index":  entry.generation_index,
        "snapshot_sig":      entry.snapshot_sig,
        "shape":             entry.shape,
        "shape_label":       entry.shape_label,
        "generator_version": entry.generator_version,
        "mode":              entry.mode,
        "generated_at":      entry.generated_at,
        "size_bytes":        entry.size_bytes,
        "selected_files":    entry.selected_files,
        "total_files":       entry.total_files,

        # -- commit graph --
        "trigger":            _serialize_commit_ref(entry.trigger) if entry.trigger else None,
        "also_used_by":       [_serialize_commit_ref(r) for r in entry.also_used_by],
        "successive_used_by": [_serialize_commit_ref(r) for r in entry.successive_used_by],
        "reappeared_runs":    [
            [_serialize_commit_ref(r) for r in run]
            for run in entry.reappeared_runs
        ],

        # -- canonical state + derived view --
        "flags":  flags,
        "badges": derive_badges(flags),

        # -- metrics (numerical only; booleans live in flags) --
        "lifespan_metrics": {
            "total_commits":      entry.lifespan.total_commits,
            "run_count":          entry.lifespan.run_count,
            "first_seen_topo_id": entry.lifespan.first_seen_topo_id,
            "last_seen_topo_id":  entry.lifespan.last_seen_topo_id,
            "first_seen_date":    entry.lifespan.first_seen_date,
            "last_seen_date":     entry.lifespan.last_seen_date,
            "longest_streak":     entry.lifespan.longest_streak,
        } if entry.lifespan else None,

        "composition_metrics": {
            "successive_commit_count":  entry.composition.successive_commit_count,
            "reappeared_commit_count":  entry.composition.reappeared_commit_count,
            "operational_commit_count": entry.composition.operational_commit_count,
            "development_commit_count": entry.composition.development_commit_count,
        } if entry.composition else None,

        "dominance_metrics": {
            "effective_commits":   entry.dominance.effective_commits,
            "share_of_generation": entry.dominance.share_of_generation,
        } if entry.dominance else None,
    }


def _load_snapshot_sidecar(snapshot_sig: str) -> dict:
    """Load the .meta.json sidecar for a snapshot, if it exists."""
    from backend.services.pipeline.pipeline_config import HOST_REPO_NAME
    repo_label = HOST_REPO_NAME
    versions_dir = Path("data") / repo_label / "architecture_versions"
    prefix = snapshot_sig[:16]
    sidecar = versions_dir / f"arch-{prefix}.meta.json"
    if sidecar.exists():
        try:
            import json as _json
            return _json.loads(sidecar.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _compute_generation_boundaries(
    entries: list[SnapshotEntry],
    generation_summaries: dict[int, GenerationSummaryMetrics],
) -> dict[int, BoundaryInfo]:
    """Compute boundary rationale for each generation.

    For each generation:
      - cause_tag/cause_label: from the generation summary (already normalized)
      - magnitude: derived from taxonomy family mapping
      - commit: trigger of the first structural snapshot in the generation
      - scope: top_level_dirs and file_count from the boundary snapshot's sidecar
      - displaced: last snapshot of the previous generation
    """
    if not entries:
        return {}

    # Group entries by generation
    by_gen: dict[int, list[SnapshotEntry]] = {}
    for e in entries:
        by_gen.setdefault(e.generation, []).append(e)

    # Sort each generation's entries by topo_id
    for gen_entries in by_gen.values():
        gen_entries.sort(
            key=lambda e: e.trigger.topo_id if e.trigger and e.trigger.topo_id is not None else 10_000_000
        )

    sorted_gens = sorted(by_gen.keys())
    boundaries: dict[int, BoundaryInfo] = {}

    for idx, gen_id in enumerate(sorted_gens):
        summary = generation_summaries.get(gen_id)
        if summary is None:
            continue

        tag = normalize_cause_tag(summary.cause_tag)
        label = get_boundary_cause_label(tag)
        magnitude = get_boundary_magnitude(tag)

        gen_entries = by_gen[gen_id]

        # Boundary commit: trigger of the first entry in this generation
        boundary_commit = gen_entries[0].trigger if gen_entries else None

        # Scope: from the first entry's meta sidecar
        scope = None
        if gen_entries:
            sidecar = _load_snapshot_sidecar(gen_entries[0].snapshot_sig)
            if sidecar:
                scope = BoundaryScope(
                    top_level_dirs=sidecar.get("top_level_dirs", []),
                    file_count=sidecar.get("file_count") or (sidecar.get("change_summary") or {}).get("total_files"),
                )

        # Displaced: last snapshot of the previous generation
        displaced = None
        if idx > 0:
            prev_gen = sorted_gens[idx - 1]
            prev_entries = by_gen.get(prev_gen, [])
            if prev_entries:
                prev_last = prev_entries[-1]
                prev_dom = prev_last.dominance

                if prev_dom:
                    if prev_dom.is_long_lived:
                        lc = "long"
                    elif prev_dom.is_short_lived:
                        lc = "short"
                    else:
                        lc = "standard"
                else:
                    lc = "standard"

                displaced = DisplacedSnapshot(
                    snapshot_sig=prev_last.snapshot_sig,
                    lifespan_class=lc,
                    was_dominant=prev_dom.is_dominant if prev_dom else False,
                )

        boundaries[gen_id] = BoundaryInfo(
            cause_tag=tag,
            cause_label=label,
            magnitude=magnitude,
            commit=boundary_commit,
            scope=scope,
            displaced=displaced,
        )

    return boundaries


def _serialize_boundary(boundary: BoundaryInfo | None) -> dict | None:
    if boundary is None:
        return None
    return {
        "cause_tag":   boundary.cause_tag,
        "cause_label": boundary.cause_label,
        "magnitude":   boundary.magnitude,
        "commit":      _serialize_commit_ref(boundary.commit) if boundary.commit else None,
        "scope": {
            "top_level_dirs": boundary.scope.top_level_dirs,
            "file_count":     boundary.scope.file_count,
        } if boundary.scope else None,
        "displaced": {
            "snapshot_sig":   boundary.displaced.snapshot_sig,
            "lifespan_class": boundary.displaced.lifespan_class,
            "was_dominant":   boundary.displaced.was_dominant,
        } if boundary.displaced else None,
    }


def _serialize_generation_summary(
    summary: GenerationSummaryMetrics,
    boundary: BoundaryInfo | None = None,
) -> dict:
    tag = normalize_cause_tag(summary.cause_tag)
    result = {
        "generation":                       summary.generation,
        "cause_tag":                        tag,
        "cause_label":                      get_boundary_cause_label(tag),
        "generation_distinct_commit_count": summary.generation_distinct_commit_count,
        "snapshot_count":                   summary.snapshot_count,
        "structural_count":                 summary.structural_count,
        "incremental_count":                summary.incremental_count,
        "dominant_snapshot_sig":             summary.dominant_snapshot_sig,
        "dominant_effective_commits":        summary.dominant_effective_commits,
        "dominant_share_of_generation":      summary.dominant_share_of_generation,
        "repeated_treesig_count":           summary.repeated_treesig_count,
    }
    serialized_boundary = _serialize_boundary(boundary)
    if serialized_boundary is not None:
        result["boundary"] = serialized_boundary
    return result


def serialize_history_report_to_contract(report: HistoryReport) -> dict:
    """C1 contract serializer -- hand-rolled, stable external schema.

    Replaces the legacy ``history_report_to_dict()`` (raw asdict).

    Key differences from the legacy serializer:
      * ``contract_version`` field for consumer version-gating.
      * Snapshot booleans consolidated into ``flags`` (authoritative).
      * ``badges`` derived deterministically from ``flags`` (readOnly view).
      * Metrics namespaced: ``lifespan_metrics``, ``composition_metrics``,
        ``dominance_metrics`` -- dominance booleans excluded from metrics.
      * cause_tag / cause_label routed through taxonomy.py boundary layer.
      * Internal dataclass field names decoupled from external contract keys.
    """
    return {
        "contract_version": CONTRACT_VERSION,
        "repo_label":        report.repo_label,
        "repo_display":      report.repo_display,
        "total_commits":     report.total_commits,
        "total_blueprints":  report.total_blueprints,
        "total_generations": report.total_generations,
        "current": {
            "snapshot_sig":      report.current.snapshot_sig,
            "generated_at":      report.current.generated_at,
            "generator_version": report.current.generator_version,
            "mode":              report.current.mode,
            "shape":             report.current.shape,
            "total_files":       report.current.total_files,
            "selected_files":    report.current.selected_files,
        },
        "entries": [_serialize_snapshot_entry(e) for e in report.entries],
        # Compute boundary rationale for each generation
        "generation_summaries": (lambda: {
            str(gen_id): _serialize_generation_summary(
                summary,
                boundary=_compute_generation_boundaries(
                    report.entries,
                    report.generation_summaries or {},
                ).get(gen_id),
            )
            for gen_id, summary in sorted(
                (report.generation_summaries or {}).items()
            )
        })(),
    }

