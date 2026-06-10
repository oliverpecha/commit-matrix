#!/usr/bin/env python3

from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from backend.services.pipeline.pipeline_config import HOST_REPO_NAME, RUBRIC_NAME
from backend.utils.git_ops import get_commit_meta


from datetime import datetime, date as _date


def _parse_pretty_date_to_iso(value: str) -> str | None:
    """
    Convert a pretty git/ledger date like "May 16, '26" into "2026-05-16".
    Returns None if parsing fails.
    """
    s = (value or "").strip()
    if not s or s.lower() == "unknown date":
        return None
    # Try current ledger/get_commit_meta format: "May 16, '26"
    for fmt in ("%b %d, '%y", "%b %d, %Y"):
        try:
            dt = datetime.strptime(s, fmt)
            # Normalize to naive date and ISO YYYY-MM-DD
            return dt.date().isoformat()
        except ValueError:
            continue
    # Already ISO-like?
    try:
        # Accept full ISO timestamp and truncate to date
        if "T" in s:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            return dt.date().isoformat()
        # Accept YYYY-MM-DD directly
        dt = datetime.strptime(s, "%Y-%m-%d")
        return dt.date().isoformat()
    except Exception:
        return None


@dataclass
class CommitRef:
    sha: str
    date: str              # human display, e.g. "May 16, '26"
    subject: str
    topo_id: int | None = None
    date_iso: str | None = None  # canonical, e.g. "2026-05-16"


@dataclass
class SnapshotLifespanMetrics:
    """How long and across how many runs a snapshot was active."""
    total_commits: int
    run_count: int
    first_seen_topo_id: int | None
    last_seen_topo_id: int | None
    first_seen_date: str
    last_seen_date: str
    longest_streak: int


@dataclass
class SnapshotCompositionMetrics:
    """How the snapshot's commits break down by role."""
    successive_commit_count: int
    reappeared_commit_count: int
    operational_commit_count: int
    development_commit_count: int


@dataclass
class SnapshotDominanceMetrics:
    """How dominant a snapshot is within its generation.

    Locked rule:
        effective_commits = total_commits - operational_commit_count
    """
    effective_commits: int
    share_of_generation: float
    longest_streak: int
    reappearance_commit_count: int
    is_dominant: bool
    is_long_lived: bool
    is_short_lived: bool


@dataclass
class GenerationSummaryMetrics:
    """Generation-level summary used by the history printer."""
    generation: int
    cause_tag: str
    cause_label: str
    mapped_commits: int
    snapshot_count: int
    structural_count: int
    incremental_count: int
    dominant_snapshot_sig: str
    dominant_effective_commits: int
    dominant_share_of_generation: float
    repeated_treesig_count: int


@dataclass
class SnapshotEntry:
    generation: int
    sig: str
    shape: str
    generator_version: str
    mode: str
    generated_at: str
    size_bytes: int
    selected_files: str | int
    total_files: str | int
    trigger: CommitRef | None = None
    also_used_by: list[CommitRef] = field(default_factory=list)
    successive_used_by: list[CommitRef] = field(default_factory=list)
    reappeared_runs: list[list[CommitRef]] = field(default_factory=list)
    is_current: bool = False
    shape_label: str | None = None
    lifespan: SnapshotLifespanMetrics | None = None
    composition: SnapshotCompositionMetrics | None = None
    dominance: SnapshotDominanceMetrics | None = None


@dataclass
class CurrentBlueprint:
    sig: str
    generated_at: str
    generator_version: str
    mode: str
    shape: str
    total_files: str | int
    selected_files: str | int


@dataclass
class HistoryReport:
    repo_label: str
    repo_display: str
    total_commits: int
    total_blueprints: int
    total_generations: int
    current: CurrentBlueprint
    entries: list[SnapshotEntry]
    generation_summaries: dict[int, GenerationSummaryMetrics] | None = None


def shape_icon(shape: str) -> str:
    shape = (shape or "").strip().lower()
    if shape.startswith("leaf-only"):
        return "🍃"
    if "restructure" in shape or "split" in shape or "merge" in shape:
        return "🧱"
    if "root" in shape or "major" in shape:
        return "🌳"
    return "•"


def derive_repo_display(repo_path: Path, repo_label: str) -> str:
    git_dir = repo_path / ".git"
    config_path = git_dir / "config"
    if config_path.exists():
        try:
            config_text = config_path.read_text(encoding="utf-8", errors="replace")
            match = re.search(
                r"url\s*=\s*.*[:/]([^/\s:]+)/([^/\s]+?)(?:\.git)?\s*$",
                config_text,
                re.MULTILINE,
            )
            if match:
                return f"{match.group(1)}/{match.group(2)}"
        except Exception:
            pass
    return f"local/{repo_label}"


def _load_snapshot_meta(snap: Path) -> dict:
    sidecar = snap.with_suffix(".meta.json")
    if sidecar.exists():
        try:
            return json.loads(sidecar.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _compute_generations(snapshots: list[Path]) -> list[tuple[int, Path, dict]]:
    result: list[tuple[int, Path, dict]] = []
    current_gen = 1
    for idx, snap in enumerate(snapshots):
        meta = _load_snapshot_meta(snap)
        shape = (meta.get("change_summary") or {}).get("change_shape", "unknown")
        if idx > 0 and not shape.startswith("leaf-only"):
            current_gen += 1
        result.append((current_gen, snap, meta))
    return result


def _topo_key_for_snapshot(snap: Path, meta: dict, topo_by_sha: dict[str, str]) -> int:
    commit_sha = (meta.get("commit_sha") or "").strip()
    if commit_sha:
        raw = topo_by_sha.get(commit_sha[:7]) or topo_by_sha.get(commit_sha)
        if raw and str(raw).isdigit():
            return int(raw)
    return 10_000_000


def _reassign_generations(entries: list[SnapshotEntry]) -> list[SnapshotEntry]:
    ordered = sorted(
        entries,
        key=lambda e: (e.trigger.topo_id if e.trigger and e.trigger.topo_id is not None else 10_000_000)
    )
    current_gen = 1
    for idx, entry in enumerate(ordered):
        if idx > 0 and not (entry.shape or "").startswith("leaf-only"):
            current_gen += 1
        entry.generation = current_gen
    return ordered


def _reanchor_reuse_by_signature(entries: list[SnapshotEntry]) -> list[SnapshotEntry]:
    ordered = sorted(
        entries,
        key=lambda e: (e.trigger.topo_id if e.trigger and e.trigger.topo_id is not None else 10_000_000)
    )

    preserved_refs: list[tuple[str, CommitRef]] = []
    for entry in ordered:
        if entry.trigger:
            preserved_refs.append((entry.sig, entry.trigger))
        for ref in entry.also_used_by:
            preserved_refs.append((entry.sig, ref))

    for entry in ordered:
        entry.also_used_by = []

    anchors: dict[str, SnapshotEntry] = {}
    for entry in ordered:
        if entry.sig:
            anchors[entry.sig] = entry

    sig_to_trigger_topos: dict[str, set[int]] = {}
    for entry in ordered:
        if entry.sig and entry.trigger and entry.trigger.topo_id is not None:
            sig_to_trigger_topos.setdefault(entry.sig, set()).add(entry.trigger.topo_id)

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
            key=lambda r: (r.topo_id if r.topo_id is not None else 10_000_000, r.sha)
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


def _find_ledger_path(repo_label: str) -> Path | None:
    candidates = [
        Path("data") / repo_label / f"{repo_label}_ledger_cirsd.csv",
        Path("data") / repo_label / f"{repo_label}_ledger_{RUBRIC_NAME}.csv",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _load_used_by_map(repo_label: str) -> tuple[dict[str, list[dict]], dict[str, str], list[dict]]:
    ledger_path = _find_ledger_path(repo_label)
    used_by: dict[str, list[dict]] = {}
    topo_by_sha: dict[str, str] = {}
    ledger_rows: list[dict] = []
    if not ledger_path:
        return used_by, topo_by_sha, ledger_rows

    try:
        with ledger_path.open("r", encoding="utf-8-sig", errors="replace") as f:
            for row in csv.DictReader(f):
                sig = (row.get("TreeSig") or row.get("ArchSig") or "").strip()
                commit_sha = (row.get("Hash") or "").strip()
                date = (row.get("Date") or "").strip()
                subject = (row.get("Subject") or "").strip()
                topo_raw = (row.get("#") or row.get("topo_id") or row.get("n") or "").strip()

                topo_id = int(topo_raw) if topo_raw.isdigit() else None

                if commit_sha and topo_raw:
                    topo_by_sha[commit_sha[:7]] = topo_raw
                    topo_by_sha[commit_sha] = topo_raw

                if not sig or not commit_sha:
                    continue

                row_data = {
                    "sig": sig,
                    "sha": commit_sha,
                    "date": date,
                    "subject": subject,
                    "topo_id": topo_id,
                }
                ledger_rows.append(row_data)
                used_by.setdefault(sig, []).append(row_data)
    except Exception:
        return {}, {}, []

    return used_by, topo_by_sha, ledger_rows


def _is_stash(subject: str) -> bool:
    return subject.startswith("index on ") or subject.startswith("WIP on ")


def _is_operational(subject: str) -> bool:
    """Operational commits are preserved for traceability but discounted in dominance."""
    s = (subject or "").strip()
    if s.startswith("index on "):
        return True
    if s.startswith("WIP on "):
        return True
    if s.startswith("On ") and ": " in s:
        return True
    if "RECOVERY BASELINE" in s:
        return True
    return False


def _compute_tree_sig_eras(ledger_rows: list[dict]) -> tuple[dict[str, int], dict[str, list[list[dict]]]]:
    ordered_rows = sorted(
        [row for row in ledger_rows if row.get("sig") and row.get("topo_id") is not None],
        key=lambda row: row["topo_id"],
    )
    era_by_sha: dict[str, int] = {}
    runs_by_sig: dict[str, list[list[dict]]] = {}

    last_sig = None
    current_run: list[dict] = []

    for row in ordered_rows:
        sig = row["sig"]
        sha = (row.get("sha") or "").strip()
        if not sha:
            continue

        if last_sig is None or sig == last_sig:
            current_run.append(row)
        else:
            runs_by_sig.setdefault(last_sig, []).append(current_run)
            current_run = [row]

        last_sig = sig

    if current_run and last_sig is not None:
        runs_by_sig.setdefault(last_sig, []).append(current_run)

    for sig, runs in runs_by_sig.items():
        for era_index, run in enumerate(runs, start=1):
            for row in run:
                sha = (row.get("sha") or "").strip()
                if sha:
                    era_by_sha[sha] = era_index
                    era_by_sha[sha[:7]] = era_index

    return era_by_sha, runs_by_sig


def _display_mode(raw_mode: str) -> str:
    return "programmatic" if raw_mode.startswith("stub-") else (raw_mode or "unknown")


def human_shape_label(shape: str) -> str:
    s = (shape or "").strip().lower()
    mapping = {
        "major:dirs": "structural: deep single-area shift",
        "multi-dir:dirs": "structural: broad multi-area shift",
        "major:file-count": "structural: file-count jump",
        "major:selected-files": "structural: selected-files jump",
        "major:first-generation": "structural: first generation",
        "leaf-only": "incremental: leaf-only",
    }
    return mapping.get(s, shape or "unknown")


def _resolve_commit_ref(repo_path: Path, row: dict, topo_by_sha: dict[str, str]) -> CommitRef:
    sha_full = (row.get("sha") or "").strip()
    sha7 = sha_full[:7]
    meta = get_commit_meta(str(repo_path), sha_full) if sha_full else None

    topo_id = row.get("topo_id")
    if topo_id is None and sha7:
        raw = topo_by_sha.get(sha7) or topo_by_sha.get(sha_full)
        topo_id = int(raw) if isinstance(raw, str) and raw.isdigit() else None

    pretty_date = (meta or {}).get("date") or row.get("date") or "unknown date"
    # Canonical ISO date (YYYY-MM-DD) for selectors and metrics.
    date_iso = _parse_pretty_date_to_iso(pretty_date)

    return CommitRef(
        sha=sha7 or "unknown",
        date=pretty_date,
        subject=(meta or {}).get("subject") or row.get("subject") or "no subject",
        topo_id=topo_id,
        date_iso=date_iso,
    )


def _compute_snapshot_lifespan_metrics(entry: "SnapshotEntry") -> SnapshotLifespanMetrics:
    runs: list[list[CommitRef]] = []
    main_run: list[CommitRef] = []
    if entry.trigger:
        main_run.append(entry.trigger)
    main_run.extend(entry.successive_used_by)
    if main_run:
        runs.append(main_run)
    runs.extend(entry.reappeared_runs)

    if not runs:
        return SnapshotLifespanMetrics(
            total_commits=0,
            run_count=0,
            first_seen_topo_id=None,
            last_seen_topo_id=None,
            first_seen_date="unknown",
            last_seen_date="unknown",
            longest_streak=0,
        )

    all_refs = [ref for run in runs for ref in run]
    refs_with_topo = [ref for ref in all_refs if ref.topo_id is not None]

    if refs_with_topo:
        first_ref = min(refs_with_topo, key=lambda r: r.topo_id)
        last_ref = max(refs_with_topo, key=lambda r: r.topo_id)
    else:
        first_ref = all_refs[0]
        last_ref = all_refs[-1]

    return SnapshotLifespanMetrics(
        total_commits=len(all_refs),
        run_count=len(runs),
        first_seen_topo_id=first_ref.topo_id,
        last_seen_topo_id=last_ref.topo_id,
        first_seen_date=first_ref.date,
        last_seen_date=last_ref.date,
        longest_streak=max(len(run) for run in runs),
    )


def _compute_snapshot_composition_metrics(entry: "SnapshotEntry") -> SnapshotCompositionMetrics:
    all_refs: list[CommitRef] = []
    if entry.trigger:
        all_refs.append(entry.trigger)
    all_refs.extend(entry.successive_used_by)
    for run in entry.reappeared_runs:
        all_refs.extend(run)

    operational_commit_count = sum(1 for ref in all_refs if _is_operational(ref.subject))
    total_commits = len(all_refs)

    return SnapshotCompositionMetrics(
        successive_commit_count=len(entry.successive_used_by),
        reappeared_commit_count=sum(len(run) for run in entry.reappeared_runs),
        operational_commit_count=operational_commit_count,
        development_commit_count=total_commits - operational_commit_count,
    )


def _compute_snapshot_dominance_metrics(
    entry: "SnapshotEntry",
    generation_effective_total: int,
) -> SnapshotDominanceMetrics:
    if entry.lifespan is None or entry.composition is None:
        raise ValueError("lifespan and composition must be computed before dominance")

    effective_commits = max(0, entry.lifespan.total_commits - entry.composition.operational_commit_count)
    share_of_generation = (
        effective_commits / generation_effective_total
        if generation_effective_total > 0
        else 0.0
    )

    return SnapshotDominanceMetrics(
        effective_commits=effective_commits,
        share_of_generation=share_of_generation,
        longest_streak=entry.lifespan.longest_streak,
        reappearance_commit_count=entry.composition.reappeared_commit_count,
        is_dominant=False,
        is_long_lived=(effective_commits >= 3 and entry.lifespan.longest_streak >= 3),
        is_short_lived=(entry.lifespan.total_commits == 1),
    )


def _assign_dominant_flags(entries: list[SnapshotEntry]) -> None:
    grouped: dict[int, list[SnapshotEntry]] = {}
    for entry in entries:
        grouped.setdefault(entry.generation, []).append(entry)

    for gen_entries in grouped.values():
        ranked = sorted(
            gen_entries,
            key=lambda e: (
                -(e.dominance.effective_commits if e.dominance else 0),
                -(e.dominance.share_of_generation if e.dominance else 0.0),
                -(e.lifespan.longest_streak if e.lifespan else 0),
                -(e.composition.reappeared_commit_count if e.composition else 0),
                (e.lifespan.first_seen_topo_id if e.lifespan and e.lifespan.first_seen_topo_id is not None else 10_000_000),
            ),
        )
        if ranked and ranked[0].dominance is not None:
            ranked[0].dominance.is_dominant = True


def _compute_generation_summaries(entries: list[SnapshotEntry]) -> dict[int, GenerationSummaryMetrics]:
    """Aggregate generation-level metrics from snapshot entries.

    NOTE: At this stage, this is used only by the CLI renderer. JSON/DB wiring
    will consume the same GenerationSummaryMetrics objects later.
    """
    from collections import defaultdict

    grouped: dict[int, list[SnapshotEntry]] = defaultdict(list)
    for e in entries:
        grouped[e.generation].append(e)

    summaries: dict[int, GenerationSummaryMetrics] = {}

    for gen, snaps in grouped.items():
        mapped_commits = 0
        structural_count = 0
        incremental_count = 0
        repeated_treesig_count = 0

        for e in snaps:
            if e.lifespan:
                mapped_commits += e.lifespan.total_commits
                if e.lifespan.run_count > 1:
                    repeated_treesig_count += 1

            shape = (e.shape or "").strip()
            if shape.startswith("major:") or shape.startswith("multi-dir:"):
                structural_count += 1
            else:
                incremental_count += 1

        snapshot_count = len(snaps)

        ranked = sorted(
            snaps,
            key=lambda e: (
                -(e.dominance.effective_commits if e.dominance else 0),
                -(e.dominance.share_of_generation if e.dominance else 0.0),
                -(e.lifespan.longest_streak if e.lifespan else 0),
                -(e.composition.reappeared_commit_count if e.composition else 0),
                (e.lifespan.first_seen_topo_id if e.lifespan and e.lifespan.first_seen_topo_id is not None else 10_000_000),
            ),
        )
        dominant = ranked[0] if ranked else None
        if dominant and dominant.dominance:
            dominant_sig = dominant.sig
            dominant_eff = dominant.dominance.effective_commits
            dominant_share = dominant.dominance.share_of_generation
        else:
            dominant_sig = ""
            dominant_eff = 0
            dominant_share = 0.0

        # Cause tag/label: for now use the shape of the first structural snapshot,
        # falling back to the first snapshot's shape. Agent 2 can later inject a
        # richer cause_label; the renderer will always prefer that when present.
        cause_tag = ""
        cause_label = ""
        structural_first = next((e for e in snaps if (e.shape or "").startswith(("major:", "multi-dir:"))), None)
        anchor_entry = structural_first or snaps[0]

        cause_tag = (anchor_entry.shape or "unknown")
        cause_label = (anchor_entry.shape_label or human_shape_label(cause_tag))

        summaries[gen] = GenerationSummaryMetrics(
            generation=gen,
            cause_tag=cause_tag,
            cause_label=cause_label,
            mapped_commits=mapped_commits,
            snapshot_count=snapshot_count,
            structural_count=structural_count,
            incremental_count=incremental_count,
            dominant_snapshot_sig=dominant_sig,
            dominant_effective_commits=dominant_eff,
            dominant_share_of_generation=dominant_share,
            repeated_treesig_count=repeated_treesig_count,
        )

    return summaries


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
        # Date selector: compare against canonical ISO date (YYYY-MM-DD).
        return (trigger.date_iso or "") == lowered

    if re.fullmatch(r"[0-9a-f]{6,40}", lowered):
        return (trigger.sha or "").lower().startswith(lowered)

    return False


def filter_history_report(
    report: HistoryReport,
    *,
    since: str | None = None,
    until: str | None = None,
    generation: int | None = None,
    sig_prefix: str | None = None,
    only_reappeared: bool = False,
) -> HistoryReport:
    entries = list(report.entries)

    if generation is not None:
        entries = [e for e in entries if e.generation == generation]

    if sig_prefix:
        prefix = sig_prefix.strip().lower()
        entries = [e for e in entries if (e.sig or "").lower().startswith(prefix)]

    if only_reappeared:
        entries = [e for e in entries if e.lifespan is not None and e.lifespan.run_count > 1]

    numeric_since = int(since.strip()) if since and since.strip().isdigit() else None
    numeric_until = int(until.strip()) if until and until.strip().isdigit() else None

    if numeric_since is not None or numeric_until is not None:
        def overlaps_numeric_range(entry: SnapshotEntry) -> bool:
            lifespan = entry.lifespan
            if lifespan is not None:
                first_topo = lifespan.first_seen_topo_id
                last_topo = lifespan.last_seen_topo_id
            else:
                first_topo = entry.trigger.topo_id if entry.trigger else None
                last_topo = entry.trigger.topo_id if entry.trigger else None

            if first_topo is None or last_topo is None:
                return False
            if numeric_since is not None and last_topo < numeric_since:
                return False
            if numeric_until is not None and first_topo > numeric_until:
                return False
            return True

        entries = [e for e in entries if overlaps_numeric_range(e)]
    else:
        if since:
            matched = next((e for e in entries if _matches_selector_value(e, since)), None)
            if matched and matched.trigger and matched.trigger.topo_id is not None:
                since_topo = matched.trigger.topo_id
                entries = [
                    e for e in entries
                    if e.trigger and e.trigger.topo_id is not None and e.trigger.topo_id >= since_topo
                ]
            elif re.fullmatch(r"\d{4}-\d{2}-\d{2}", since.strip()):
                since_iso = since.strip()
                entries = [
                    e for e in entries
                    if e.trigger and e.trigger.date_iso is not None and e.trigger.date_iso >= since_iso
                ]

        if until:
            matched = next((e for e in entries if _matches_selector_value(e, until)), None)
            if matched and matched.trigger and matched.trigger.topo_id is not None:
                until_topo = matched.trigger.topo_id
                entries = [
                    e for e in entries
                    if e.trigger and e.trigger.topo_id is not None and e.trigger.topo_id <= until_topo
                ]
            elif re.fullmatch(r"\d{4}-\d{2}-\d{2}", until.strip()):
                until_iso = until.strip()
                entries = [
                    e for e in entries
                    if e.trigger and e.trigger.date_iso is not None and e.trigger.date_iso <= until_iso
                ]

    generation_summaries = (
        _compute_generation_summaries(entries) if entries else {}
    )
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
    used_by_map, topo_by_sha, ledger_rows = _load_used_by_map(repo_label)

    _dbg(f"ledger: {len(used_by_map)} unique TreeSigs (legacy ArchSig compatible), {len(topo_by_sha)//2} SHAs in topo map")
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
        sig=current_meta.get("tree_signature", ""),
        generated_at=current_meta.get("generated_at", "—"),
        generator_version=current_meta.get("generator_version", "—"),
        mode=(current_meta.get("change_summary") or {}).get("mode", "—"),
        shape=(current_meta.get("change_summary") or {}).get("change_shape", "—"),
        total_files=(current_meta.get("change_summary") or {}).get("total_files", "—"),
        selected_files=(current_meta.get("change_summary") or {}).get("selected_files_count", "—"),
    )
    _dbg(f"current sig: {current.sig[:16]}...")

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
        key=lambda p: _topo_key_for_snapshot(p, _load_snapshot_meta(p), topo_by_sha),
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
            current.sig and (
                current.sig == sig
                or current.sig.startswith(sig[:16])
                or sig.startswith(current.sig[:16])
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

        trigger = _resolve_commit_ref(repo_path, trigger_row, topo_by_sha) if trigger_row else None

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
                ref = _resolve_commit_ref(repo_path, row, topo_by_sha)
                _dbg(f"      also_used: topo={ref.topo_id} sha={ref.sha} subj={ref.subject[:50]}")
                also_used_by.append(ref)

            if current_run_rows:
                seen_trigger = False
                for row in current_run_rows:
                    sha = (row.get("sha") or "").strip()
                    if sha == trigger_sha:
                        seen_trigger = True
                        continue
                    if seen_trigger:
                        successive_used_by.append(_resolve_commit_ref(repo_path, row, topo_by_sha))

            if matched_run_index is not None:
                for run in runs[matched_run_index + 1:]:
                    run_refs = [
                        _resolve_commit_ref(repo_path, row, topo_by_sha)
                        for row in run
                        if (row.get("sha") or "").strip()
                    ]
                    if run_refs:
                        reappeared_runs.append(run_refs)

        entries_out.append(
            SnapshotEntry(
                generation=gen_num,
                sig=sig,
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

    # Per-generation summary metrics for the history view.
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
            f"sig={entry.sig[:16]}... shape={entry.shape} reuse={reuse_topos} "
            f"runs={life.run_count if life else '?'} total={life.total_commits if life else '?'} "
            f"op={comp.operational_commit_count if comp else '?'} "
            f"eff={dom.effective_commits if dom else '?'} dominant={dom.is_dominant if dom else '?'}"
        )

    return HistoryReport(
        repo_label=repo_label,
        repo_display=repo_display,
        total_commits=len(all_used_commits),
        total_blueprints=len(snapshots),
        total_generations=max_gen,
        current=current,
        entries=entries_out,
        generation_summaries=generation_summaries,
    )
