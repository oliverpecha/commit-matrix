#!/usr/bin/env python3
"""
CommitMatrix Parser - Modular orchestrator for LLM-based commit analysis.
"""
import os
import sys
import argparse
import time
import logging
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
from backend.services.pipeline.preflight import prepare_commit_work_item
from backend.services.pipeline.work_item import CommitWorkItem
from backend.workers.worker_results import resolve_future_result
from backend.utils.csv_writer import ensure_csv_exists, load_existing_hashes
from backend.services.pipeline.pipeline_config import (
    MODEL_NAME,
    TARGET_RPM,
    MAX_WORKERS,
    CSV_PATH,
    RUBRIC_PATH,
)
from backend.services.architecture.arch_resolver import ArchitectureResolver
from backend.services.pipeline.preflight import extract_commit_sha
from backend.services.pipeline.preflight import prepare_commit_work_item


def print_architecture_event(state):
    if not state.available:
        print("─────────────────────────────────────────────────────────────────────────", flush=True)
        print("🏗️  Architecture unavailable", flush=True)
        print(f"Summary   │ {state.summary}", flush=True)
        print("─────────────────────────────────────────────────────────────────────────\n", flush=True)
        return

    if not (state.established or state.advanced):
        return

    title = (
        f"🏗️  Architecture established at Gen #{state.gen}"
        if state.established
        else f"🏗️  Architecture advanced to Gen #{state.gen}"
    )

    print("─────────────────────────────────────────────────────────────────────────", flush=True)
    print(title, flush=True)
    print(f"Change    │ {state.change_shape or 'unknown'}", flush=True)
    print(f"Summary   │ {state.summary}", flush=True)
    print(f"Mode      │ {state.mode or 'unknown'}", flush=True)
    print("─────────────────────────────────────────────────────────────────────────\n", flush=True)



def main():
    start_time = time.time()

    parser = argparse.ArgumentParser(description="CommitMatrix LLM-powered commit analyzer")
    parser.add_argument("--repo", required=True, help="Path to git repository")
    args = parser.parse_args()

    repo_path = args.repo
    repo_label = os.path.basename(repo_path.rstrip("/")) or repo_path
    tracker = ArchitectureResolver(repo_path, max_retries=3)

    existing_hashes = load_existing_hashes(CSV_PATH)
    queue_meta = build_commit_queue(repo_path, existing_hashes)
    commits_with_ids = queue_meta["commits_with_ids"]
    total_found = queue_meta["total_found"]
    max_commits = queue_meta["max_commits"]
    total_unscanned = queue_meta["total_unscanned"]

    if total_unscanned == 0:
        print("✅ All commits already analyzed.\n\n🤝 Repository ledger up to date!\n\n", flush=True)
        return

    if max_commits > 0:
        print(f"📦 Discovered {total_found} unscanned commits.\n\n🛡️ TOKEN SAVER ACTIVE: Focusing on the {max_commits} newest commits for this run.\n", flush=True)
    else:
        print(f"📦 Discovered {total_found} unscanned commit(s) ready for analysis.\n\n", flush=True)

    print("┌─ 🔗 SYSTEM & ORCHESTRATOR INITIALIZATION ──────────────────────┐", flush=True)
    print(f"│  📂 Target Mount:  [{repo_label}] ➔ /target_repo", flush=True)
    print("│  🎯 CLI Command:   python -u commit_pipeline.py --repo /target_repo", flush=True)
    print("│  ├─ Strategy:      AIMD Sliding Window", flush=True)
    print(f"│  ├─ Model:         {MODEL_NAME}", flush=True)
    print(f"│  ├─ Workers:       {MAX_WORKERS} (Dynamic Max)", flush=True)
    print(f"│  └─ Pace Car:      {TARGET_RPM} RPM Limit Active", flush=True)
    print("└────────────────────────────────────────────────────────────────┘\n", flush=True)

    aimd = AIMDController(initial=1, max_workers=MAX_WORKERS)
    rate_limits = RateLimitsController(target_rpm=TARGET_RPM)
    file_exists = ensure_csv_exists(CSV_PATH)

    display_commits = [
        (ordinal_in_window, topo_id, commit_parts)
        for ordinal_in_window, (topo_id, commit_parts) in enumerate(commits_with_ids, start=1)
    ]

    flush_state = init_flush_state([
        (topo_id, commit_parts)
        for _, topo_id, commit_parts in display_commits
    ])
    processed_count = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        work_item_iter_ref = iter(
            prepare_commit_work_item(
                topo_id=topo_id,
                commit_parts=commit_parts,
                total_unscanned=total_unscanned,
                processed_count=ordinal_in_window,
                ordinal_in_window=ordinal_in_window,
                model_name=MODEL_NAME,
                rubric_path=RUBRIC_PATH,
                tracker=tracker,
            )[0]
            for ordinal_in_window, topo_id, commit_parts in display_commits
        )
        active_futures = {}

        active_futures, processed_count = seed_initial_batch(
            executor,
            work_item_iter_ref,
            MAX_WORKERS,
            total_unscanned,
            processed_count,
            "",
            MODEL_NAME,
            RUBRIC_PATH,
            rate_limits,
            aimd,
            arch_tree_signature=None,
            arch_gen=None,
        )

        while active_futures:
            done, _ = wait(active_futures, return_when=FIRST_COMPLETED)

            for future in done:
                topo_id = active_futures.pop(future, "?")
                result_i, result, log_msg = resolve_future_result(future, topo_id, timeout=120)
                if log_msg:
                    print(log_msg, flush=True)

                stash_result(flush_state, result_i, result)

                replenish_one(
                    executor,
                    work_item_iter_ref,
                    active_futures,
                    rate_limits,
                    aimd,
                )

            file_exists, ready_outputs = flush_ready_results(
                flush_state, CSV_PATH, file_exists, existing_hashes
            )
            for output in ready_outputs:
                print(output, flush=True)

    # Record scan range and detect vacuums (M3)
    processed_topos = [topo_id for topo_id, _ in commits_with_ids]
    if processed_topos:
        _scan_head = max(processed_topos)
        _scan_tail = min(processed_topos)
        try:
            from backend.services.db.writer import update_scan_range, detect_and_record_vacuums
            update_scan_range(repo_label, _scan_head, _scan_tail)
            detect_and_record_vacuums(repo_label, _scan_head, _scan_tail)
        except Exception as _e:
            import sys as _sys
            print(f"[arch-history] scan range recording failed: {_e}", file=_sys.stderr)

    error_count = flush_state["error_count"]
    success_count = flush_state["success_count"]

    if error_count > 0:
        print(f"⚠️ PROCESS_COMPLETE_WITH_ERRORS: {error_count} failed, {success_count} succeeded.\n\n", flush=True)
    else:
        print("🤝 Repository ledger up to date!\n\n", flush=True)


    elapsed = time.time() - start_time
    print(f"⏱️  Total execution time: {int(elapsed // 60)}m {int(elapsed % 60)}s\n", flush=True)


if __name__ == "__main__":
    main()
