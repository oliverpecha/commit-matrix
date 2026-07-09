#!/usr/bin/env python3
"""
CommitMatrix Parser - Modular orchestrator for LLM-based commit analysis.
"""
import os
import sys
import argparse
import time
import subprocess

import logging
import re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED

os.environ["SUPPRESS_LITELLM_LOGS"] = "True"
os.environ["LITELLM_LOG"] = "ERROR"
if str(os.environ.get("MATRIX_DEBUG", "false")).strip().lower() not in ("1", "true", "yes", "on"):
    logging.getLogger("litellm").setLevel(logging.WARNING)

if "GEMINI_API_KEY" in os.environ:
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

from backend.controllers.aimd import AIMDController
from backend.controllers.rate_limiter import RateLimitsController
from backend.services.pipeline.repo_bootstrap import build_commit_queue
from backend.services.pipeline.landing import flush_ready_results, init_flush_state, stash_result
from backend.services.pipeline.executor_flow import replenish_one, seed_initial_batch
from backend.services.pipeline.prep_scoring import prepare_commit_work_item
from backend.services.pipeline.work_item import CommitWorkItem
from backend.workers.worker_results import resolve_future_result
from backend.utils.csv_writer import ensure_csv_exists, load_existing_hashes
from backend.services.pipeline.pipeline_config import (
    MODEL_NAME, TARGET_RPM, MAX_WORKERS, CSV_PATH, RUBRIC_PATH
)
from backend.cli.arch_history.data.metrics import compute_generation_summaries
from backend.services.pipeline.prep_scoring import extract_commit_sha
from backend.services.pipeline.prep_scoring import prepare_commit_work_item

def print_architecture_event(state, repo_label=None, db_path=None):
    if not getattr(state, 'available', True):
        print('─' * 71, flush=True)
        print('🏗️  Architecture unavailable', flush=True)
        return

    if not (getattr(state, 'established', False) or getattr(state, 'advanced', False)):
        return

    from backend.cli.arch_history.taxonomy import get_shape_metadata
    raw_shape = getattr(state, 'change_shape', '')
    meta = get_shape_metadata(raw_shape)
    cause = meta.get('label', raw_shape or 'unknown')
    icon = meta.get('icon', '🕰️')
    title = '📍 Current Architecture Head' if not getattr(state, 'advanced', False) else f'{icon}  Architecture Boundary (Gen {getattr(state, "gen", "?")})'
    
    print('\n' + '─' * 71, flush=True)
    print(title, flush=True)
    print(f'    Cause     │ {cause}', flush=True)
    print(f'    Mode      │ {getattr(state, "mode", "programmatic")}', flush=True)
    print('─' * 71 + '\n', flush=True)

def main():
    start_time = time.time()
    parser = argparse.ArgumentParser(description="Process Git commits via LLM")
    parser.add_argument("--repo", type=str, default=".", help="Path to Git repository")
    args = parser.parse_args()
    repo_path = args.repo

    repo_label = os.environ.get("HOST_REPO_NAME")
    if not repo_label:
        try:
            repo_label = os.path.basename(repo_path.rstrip("/"))
        except NameError:
            repo_label = "commit-matrix"

    if repo_label in (".", "target_repo", "", "app", None):
        repo_label = "commit-matrix"

    db_path = f"data/{repo_label}/commit_matrix.db"

    from backend.services.pipeline.prep_scoring import ensure_architecture_oracle
    ensure_architecture_oracle(repo_path, db_path)

    existing_hashes = load_existing_hashes(CSV_PATH)
    bootstrap_res = build_commit_queue(repo_path, existing_hashes)
    commits_with_ids = bootstrap_res['commits_with_ids']
    total_unscanned = bootstrap_res.get('total_found', len(commits_with_ids))

    aimd = AIMDController(initial=1, max_workers=MAX_WORKERS)
    rate_limits = RateLimitsController(target_rpm=TARGET_RPM)
    file_exists = ensure_csv_exists(CSV_PATH)

    display_commits = [
        (ordinal_in_window, topo_id, commit_parts)
        for ordinal_in_window, (topo_id, commit_parts) in enumerate(commits_with_ids, start=1)
    ]
    
    topo_to_sha = {tid: str(cp[0])[:7] if cp and len(cp) > 0 else "unknown" for _, tid, cp in display_commits}

    flush_state = init_flush_state([
        (topo_id, commit_parts)
        for _, topo_id, commit_parts in display_commits
    ])
    processed_count = 0

    import sqlite3 as _summary_sq
    try:
        with _summary_sq.connect(db_path) as _conn_b:
            _b_count = _conn_b.execute("SELECT COUNT(*) FROM architecture_boundaries").fetchone()[0]
            _s_count = _conn_b.execute("SELECT COUNT(*) FROM architecture_snapshots").fetchone()[0]
        print('\n' + '─' * 71, flush=True)
        print('🏗️  Architecture Summary', flush=True)
        print(f"    Boundaries    │ {_b_count} structural shifts detected", flush=True)
        print(f"    Snapshots     │ {_s_count} unique architecture states", flush=True)
        print(f"    Commits       │ analysis stream tracking initialized...", flush=True)
        print('─' * 71 + '\n', flush=True)
    except Exception:
        pass

    boundary_registry = {}
    from collections import defaultdict
    snapshot_commits: dict[tuple, list] = defaultdict(list)
    gen_stats: dict[int, dict] = defaultdict(lambda: {
        "structural_count": 0,
        "incremental_count": 0,
        "snapshot_sigs": set(),
    })
    gen_boundaries: dict[int, int] = {}

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        def _prepare_and_report(ordinal, topo_id, commit_parts):
            work_item, arch_meta = prepare_commit_work_item(
                topo_id=topo_id, commit_parts=commit_parts, total_unscanned=total_unscanned,
                processed_count=ordinal, ordinal_in_window=ordinal, model_name=MODEL_NAME,
                rubric_path=RUBRIC_PATH, repo_label=repo_label, db_path=db_path,
            )
            cause_tag = arch_meta.get("cause_tag")
            generation = arch_meta.get("generation")
            work_item.arch_change_shape = cause_tag or "unknown"
            work_item.arch_meta = arch_meta
            work_item._snap_sig = arch_meta.get("snapshot_sig")
            work_item._snap_gen = generation
            work_item._snap_reappeared = arch_meta.get("reappeared", False)
            
            if arch_meta.get("snapshot_sig"):
                work_item.arch_tree_signature = arch_meta.get("snapshot_sig")

            if generation is not None:
                print_architecture_event(arch_meta, repo_label, db_path)

            _snap_sig = arch_meta.get("snapshot_sig")
            if _snap_sig is not None and generation is not None:
                _reappeared = arch_meta.get("reappeared", False)
                _entry = {
                    "topo_id": topo_id,
                    "commit_hash": str(commit_parts[0] if len(commit_parts) > 0 else "")[:7],
                    "reappeared": bool(_reappeared),
                    "date": str(commit_parts[1] if len(commit_parts) > 1 else ""),
                    "subject": str(commit_parts[2] if len(commit_parts) > 2 else ""),
                }
                snapshot_commits[(_snap_sig, generation)].append(_entry)
            return work_item

        work_item_map = {}
        def _prepare_and_register(ordinal, topo_id, commit_parts):
            wi = _prepare_and_report(ordinal, topo_id, commit_parts)
            work_item_map[topo_id] = wi
            return wi

        _prepped_items = [
            _prepare_and_register(ordinal_in_window, topo_id, commit_parts)
            for ordinal_in_window, topo_id, commit_parts in display_commits
        ]
        work_item_iter_ref = iter(_prepped_items)
        active_futures = {}

        active_futures, processed_count = seed_initial_batch(
            executor, work_item_iter_ref, MAX_WORKERS, total_unscanned, processed_count,
            "", MODEL_NAME, RUBRIC_PATH, rate_limits, aimd, arch_tree_signature=None, arch_gen=None,
        )

        while active_futures:
            done, _ = wait(active_futures, return_when=FIRST_COMPLETED)
            for future in done:
                topo_id = active_futures.pop(future, "?")
                result_i, result, log_msg = resolve_future_result(future, topo_id, timeout=120)
                stash_result(flush_state, result_i, result)
                
                _sha = topo_to_sha.get(topo_id, "unknown")
                if log_msg and _sha == "unknown":
                    _m = re.search(r'Scored ([a-f0-9]{7,40})', log_msg)
                    if _m: _sha = _m.group(1)[:7]
                    
                print(f"⚙️  Commit #{topo_id} - {_sha} scored asynchronously -> Queued for ledger flush...", flush=True)
                replenish_one(executor, work_item_iter_ref, active_futures, rate_limits, aimd)

            file_exists, ready_outputs = flush_ready_results(
                flush_state, CSV_PATH, file_exists, existing_hashes
            )
            for output in ready_outputs:
                clean_output = re.sub(r" __TOPO:\d+__", "", output)
                print(clean_output, flush=True)
                if "🧬 Commit #" in output:
                    try:
                        m = re.search(r"__TOPO:(\d+)__", output)
                        if m:
                            res_topo = int(m.group(1))
                            import sqlite3 as _sq
                            _conn = _sq.connect(db_path)
                            _cursor = _conn.cursor()
                            _cursor.execute("SELECT cause_tag, magnitude FROM architecture_boundaries WHERE boundary_commit_topo_id = ? LIMIT 1", (res_topo,))
                            _row = _cursor.fetchone()
                            if _row:
                                cause_raw = _row[0]
                                magnitude_raw = _row[1]
                                _cursor.execute("SELECT COUNT(DISTINCT boundary_commit_topo_id) FROM architecture_boundaries WHERE boundary_commit_topo_id <= ?", (res_topo,))
                                t_gen = _cursor.fetchone()[0]
                                _conn.close()

                                from backend.cli.arch_history.taxonomy import get_shape_metadata
                                meta = get_shape_metadata(cause_raw)
                                cause_label = meta.get('label', cause_raw or 'unknown')
                                icon = meta.get('icon', '🕰️')

                                print('\n' + '─' * 71, flush=True)
                                print(f"{icon}  Architecture Boundary (Gen {t_gen})", flush=True)
                                print(f"    Cause      │ {cause_label}", flush=True)
                                print(f"    Magnitude  │ {magnitude_raw if magnitude_raw else 'structural-shift'}", flush=True)
                                print('─' * 71 + '\n', flush=True)
                            else:
                                _conn.close()
                    except Exception:
                        pass

    if boundary_registry:
        import sys as _sys
        print(f"[arch] warning: unflushed boundaries remain: {sorted(boundary_registry.keys())}", file=_sys.stderr)

    try:
        if commits_with_ids:
            head_topo = commits_with_ids[0][0]
            tail_topo = commits_with_ids[-1][0]
            from backend.services.db.writer import update_scan_range
            update_scan_range(repo_label, head_topo, tail_topo)
    except Exception:
        pass

    error_count = flush_state["error_count"]
    success_count = flush_state["success_count"]

    try:
        from backend.services.db.reader import read_scan_range, read_vacuums
        scan = read_scan_range(repo_label)
        vacuums = read_vacuums(repo_label)

        print('─' * 71, flush=True)
        if scan:
            print(f"    Commits       │ processed (#{scan['scan_head_topo']} to #{scan['scan_tail_topo']})", flush=True)
        if vacuums:
            total_vac = sum(v.get("commit_count", 0) for v in vacuums)
            print(f"    Vacuums       │ {total_vac} unscanned", flush=True)
        print('─' * 71 + '\n', flush=True)
    except Exception:
        pass

    if error_count > 0:
        print(f"⚠️ PROCESS_COMPLETE_WITH_ERRORS: {error_count} failed, {success_count} succeeded.\n", flush=True)
    else:
        print("🤝 Repository ledger up to date!\n", flush=True)

    elapsed = time.time() - start_time
    print(f"⏱️  Total execution time: {int(elapsed // 60)}m {int(elapsed % 60)}s", flush=True)

if __name__ == "__main__":
    main()
