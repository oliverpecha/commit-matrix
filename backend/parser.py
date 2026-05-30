#!/usr/bin/env python3
"""
CommitMatrix Parser - Modular orchestrator for LLM-based commit analysis.
"""
import os
import sys
import csv
import argparse
import time
import logging
import os
os.environ['SUPPRESS_LITELLM_LOGS'] = 'True'
os.environ['LITELLM_LOG'] = 'ERROR'
if str(os.environ.get("MATRIX_DEBUG", "false")).strip().lower() not in ("1", "true", "yes", "on"):
    logging.getLogger("litellm").setLevel(logging.WARNING)

from concurrent.futures import ThreadPoolExecutor, as_completed, wait, FIRST_COMPLETED

if "GEMINI_API_KEY" in os.environ:
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

from controllers.aimd import AIMDController
from controllers.rate_limits import RateLimitsController
from utils.git_ops import get_architecture_context
from backend.services.queue_builder import build_commit_queue
from backend.services.result_flusher import (
    flush_ready_results,
    init_flush_state,
    stash_result,
)
from backend.services.executor_flow import (
    replenish_one,
    seed_initial_batch,
)
from backend.services.worker_results import resolve_future_result
from utils.csv_writer import ensure_csv_exists, write_csv_row, load_existing_hashes
from backend.services.parser_config import (
    MODEL_NAME,
    TARGET_RPM,
    MAX_WORKERS,
    HOST_REPO_NAME,
    RUBRIC_NAME,
    CSV_PATH,
    RUBRIC_PATH,
)

def main():
    """Main orchestrator."""
    start_time = time.time()
    
    parser = argparse.ArgumentParser(description='CommitMatrix LLM-powered commit analyzer')
    parser.add_argument('--repo', required=True, help='Path to git repository')
    args = parser.parse_args()
    
    repo_path = args.repo
    
    # --- EMOJI & ARCHITECTURE FIX ---
    arch_context = get_architecture_context(repo_path)
    if arch_context and len(arch_context.strip()) > 10:
        print(f"🗺️  Cached architecture map loaded for [{os.path.basename(repo_path)}].\n", flush=True)
    else:
        print(f"🗄️  No architecture map found for [{os.path.basename(repo_path)}]. Using default.\n", flush=True)
    
    # Load existing processed commits
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
        print(f"📦 Discovered {total_found} unscanned commits.\n\n🛡️ TOKEN SAVER ACTIVE: Throttling queue to the {max_commits} newest.\n", flush=True)
    else:
        print(f"📦 Discovered {total_found} unscanned commit(s) ready for analysis.\n\n", flush=True)
    print("┌─ 🔗 SYSTEM & ORCHESTRATOR INITIALIZATION ──────────────────────┐", flush=True)
    print(f"│  📂 Target Mount:  [{os.path.basename(repo_path)}] ➔ /target_repo", flush=True)
    print(f"│  🎯 CLI Command:   python -u parser.py --repo /target_repo", flush=True)
    print(f"│  ├─ Strategy:      AIMD Sliding Window", flush=True)
    print(f"│  ├─ Model:         {MODEL_NAME}", flush=True)
    print(f"│  ├─ Workers:       {MAX_WORKERS} (Dynamic Max)", flush=True)
    print(f"│  └─ Pace Car:      {TARGET_RPM} RPM Limit Active", flush=True)
    print("└────────────────────────────────────────────────────────────────┘\n", flush=True)
    
    aimd = AIMDController(initial=1, max_workers=MAX_WORKERS)
    rate_limits = RateLimitsController(target_rpm=TARGET_RPM)
    
    file_exists = ensure_csv_exists(CSV_PATH)
    
    # --- WRITE QUEUE & PROGRESS TRACKING ---
    flush_state = init_flush_state(commits_with_ids)
    processed_count = 1

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        commit_iterator = iter(commits_with_ids)
        active_futures = {}
        
        # Seed initial batch
        active_futures, processed_count = seed_initial_batch(
            executor, commit_iterator, MAX_WORKERS, total_unscanned, processed_count,
            arch_context, MODEL_NAME, RUBRIC_PATH, rate_limits, aimd
        )
        
        # Process results as they complete
        while active_futures:
            done, _ = wait(active_futures, return_when=FIRST_COMPLETED)

            for future in done:
                commit_i = active_futures.pop(future, "?")
                result_i, result, log_msg = resolve_future_result(future, commit_i, timeout=120)
                if log_msg:
                    print(log_msg, flush=True)

                stash_result(flush_state, result_i, result)

                processed_count = replenish_one(
                    executor, commit_iterator, active_futures, total_unscanned, processed_count,
                    arch_context, MODEL_NAME, RUBRIC_PATH, rate_limits, aimd
                )

            # Flush results in order of expected_write_order (Newest First)
            file_exists, ready_outputs = flush_ready_results(
                flush_state, CSV_PATH, file_exists, existing_hashes
            )
            for output in ready_outputs:
                print(output, flush=True)
    
    error_count = flush_state["error_count"]
    success_count = flush_state["success_count"]

    if error_count > 0:
        print(f'⚠️ PROCESS_COMPLETE_WITH_ERRORS: {error_count} failed, {success_count} succeeded.\n\n', flush=True)
    else:
        print('🤝 Repository ledger up to date!\n\n', flush=True)
    
    elapsed = time.time() - start_time
    print(f'⏱️  Total execution time: {int(elapsed//60)}m {int(elapsed%60)}s\n', flush=True)

if __name__ == "__main__":
    main()
