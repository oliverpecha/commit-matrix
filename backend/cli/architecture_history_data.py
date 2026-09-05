#!/usr/bin/env python3

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from backend.services.pipeline.pipeline_config import HOST_REPO_NAME, RUBRIC_NAME
from backend.utils.git_ops import get_commit_meta


@dataclass
class CommitRef:
    sha: str
    date: str
    subject: str
    topo_id: int | None = None


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
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            pass
    return f"local/{repo_label}"


def _load_snapshot_meta(snap: Path) -> dict:
    sidecar = snap.with_suffix(".meta.json")
    if sidecar.exists():
        try:
            return json.loads(sidecar.read_text(encoding="utf-8"))
        except (KeyboardInterrupt, SystemExit):
            raise
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
        (Path("data") / (os.environ.get("HOST_REPO_OWNER") or "local") / repo_label) / f"{repo_label}_ledger_unknown.csv",
        (Path("data") / (os.environ.get("HOST_REPO_OWNER") or "local") / repo_label) / f"{repo_label}_ledger_{RUBRIC_NAME}.csv",
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
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        return {}, {}, []

    return used_by, topo_by_sha, ledger_rows


def _is_stash(subject: str) -> bool:
    return subject.startswith("index on ") or subject.startswith("WIP on ")


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


def _resolve_commit_ref(repo_path: Path, row: dict, topo_by_sha: dict[str, str]) -> CommitRef:
    sha_full = (row.get("sha") or "").strip()
    sha7 = sha_full[:7]
    meta = get_commit_meta(str(repo_path), sha_full) if sha_full else None

    topo_id = row.get("topo_id")
    if topo_id is None and sha7:
        raw = topo_by_sha.get(sha7) or topo_by_sha.get(sha_full)
        topo_id = int(raw) if isinstance(raw, str) and raw.isdigit() else None

    return CommitRef(
        sha=sha7 or "unknown",
        date=(meta or {}).get("date") or row.get("date") or "unknown date",
        subject=(meta or {}).get("subject") or row.get("subject") or "no subject",
        topo_id=topo_id,
    )


def build_history_report(repo_label: str | None = None, debug: bool | None = None) -> HistoryReport:
    import os
    _debug = debug if debug is not None else os.environ.get("ARCH_DEBUG", "").strip() == "1"

    def _dbg(*args) -> None:
        if _debug:
            print("[arch:dbg]", *args, flush=True)

    repo_label = repo_label or HOST_REPO_NAME
    repo_path = Path(".").resolve()
    repo_display = derive_repo_display(repo_path, repo_label)

    data_dir = (Path("data") / (os.environ.get("HOST_REPO_OWNER") or "local") / repo_label)
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
        except (KeyboardInterrupt, SystemExit):
            raise
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
            if _is_stash(subj) or not sha7 or sha7 in seen_shas:
                _dbg(f"        drop sha={sha7} (stash={_is_stash(subj)} dup={sha7 in seen_shas})")
                continue
            seen_shas.add(sha7)
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
            )
        )

    entries_out = _reanchor_reuse_by_signature(entries_out)
    entries_out = _reassign_generations(entries_out)
    max_gen = entries_out[-1].generation if entries_out else 0

    _dbg(f"\n  total entries built: {len(entries_out)}")
    for entry in entries_out:
        topo = entry.trigger.topo_id if entry.trigger else None
        reuse_topos = [ref.topo_id for ref in entry.also_used_by if ref.topo_id is not None]
        _dbg(
            f"  final entry gen={entry.generation} topo={topo} "
            f"sig={entry.sig[:16]}... shape={entry.shape} reuse={reuse_topos}"
        )

    return HistoryReport(
        repo_label=repo_label,
        repo_display=repo_display,
        total_commits=len(all_used_commits),
        total_blueprints=len(snapshots),
        total_generations=max_gen,
        current=current,
        entries=entries_out,
    )
