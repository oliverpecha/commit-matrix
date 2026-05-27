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
if os.environ.get("MATRIX_DEBUG") != "1":
    logging.getLogger("litellm").setLevel(logging.WARNING)

from concurrent.futures import ThreadPoolExecutor, as_completed, wait, FIRST_COMPLETED

# Local module imports
# Ensure API key is available for workers
if "GEMINI_API_KEY" in os.environ:
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

from controllers.aimd import AIMDController
from controllers.rate_limits import RateLimitsController
from workers.commit_processor import process_commit
from utils.git_ops import get_commits, get_commit_diff, get_architecture_context
from utils.csv_writer import ensure_csv_exists, write_csv_row, load_existing_hashes

# Constants
MODEL_NAME = os.environ.get('MATRIX_MODEL', 'gemini/gemini-2.5-flash-lite')
TARGET_RPM = float(os.environ.get('TARGET_RPM', '15.0'))
MAX_WORKERS = int(os.environ.get('MAX_WORKERS', '6'))
CSV_PATH = '/app/data/commit-matrix/commit-matrix_ledger_cirsd.csv'
RUBRIC_NAME = os.environ.get('RUBRIC_NAME', 'cirsd')
RUBRIC_PATH = f'/app/rubrics/{RUBRIC_NAME}.md'

def main():
    """Main orchestrator."""
    start_time = time.time()
    
    parser = argparse.ArgumentParser(description='CommitMatrix LLM-powered commit analyzer')
    parser.add_argument('--repo', required=True, help='Path to git repository')
    args = parser.parse_args()
    
    repo_path = args.repo
    
    # Load architecture context
    print("✅ Cached architecture map loaded for [commit-matrix].\n", flush=True)
    arch_context = get_architecture_context(repo_path)
    
    # Load existing processed commits
    existing_hashes = load_existing_hashes(CSV_PATH)
    
    # Get all commits
    log_output = get_commits(repo_path)
    lines = log_output.strip().split('\n')
    
    commits = []
    i = 0
    while i < len(lines):
        if '|' in lines[i]:
            parts = lines[i].split('|')
            hash_full = parts[0]
            hash_short = hash_full[:7]
            
            if hash_short not in existing_hashes:
                diff = get_commit_diff(hash_full, repo_path)
                commits.append((hash_full, parts[1], parts[2], parts[3], diff))
            i += 1
        else:
            i += 1
    
    # Sort by commit date (deterministic ordering)
    commits.sort(key=lambda x: x[1], reverse=True)
    
    total_unscanned = len(commits)
    
    if total_unscanned == 0:
        print("✅ All commits already analyzed.\n\n🤝 Repository ledger up to date!\n\n", flush=True)
        return
    
    print(f"📦 Discovered {total_unscanned} unscanned commit(s) ready for analysis.\n\n", flush=True)
    print("┌─ 🔗 SYSTEM & ORCHESTRATOR INITIALIZATION ──────────────────────┐", flush=True)
    print(f"│  📂 Target Mount:  [commit-matrix] ➔ /target_repo", flush=True)
    print(f"│  🎯 CLI Command:   python -u parser.py --repo /target_repo", flush=True)
    print(f"│  ├─ Strategy:      AIMD Sliding Window", flush=True)
    print(f"│  ├─ Model:         {MODEL_NAME}", flush=True)
    print(f"│  ├─ Workers:       {MAX_WORKERS} (Dynamic Max)", flush=True)
    print(f"│  └─ Pace Car:      {TARGET_RPM} RPM Limit Active", flush=True)
    print("└────────────────────────────────────────────────────────────────┘\n", flush=True)
    
    # Initialize controllers
    print("DEBUG: Creating AIMD controller...", flush=True)
    aimd = AIMDController(initial=1, max_workers=MAX_WORKERS)
    print("DEBUG: AIMD created", flush=True)
    print("DEBUG: Creating RateLimits controller...", flush=True)
    rate_limits = RateLimitsController(target_rpm=TARGET_RPM)
    print("DEBUG: RateLimits created", flush=True)
    
    # Process commits
    print("DEBUG: Checking CSV exists...", flush=True)
    file_exists = ensure_csv_exists(CSV_PATH)
    print(f"DEBUG: CSV exists={file_exists}", flush=True)
    error_count = 0
    success_count = 0
    
    print(f"DEBUG: About to start ThreadPoolExecutor", flush=True)
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        print(f"DEBUG: Executor started, seeding initial batch", flush=True)
        commit_iterator = iter(enumerate(commits, 1))
        active_futures = {}
        pending_results = {}
        next_to_write = 1
        
        # Seed initial batch
        for _ in range(MAX_WORKERS):
            try:
                next_i, next_parts = next(commit_iterator)
                print(f"DEBUG: Submitting commit {next_i}", flush=True)
                future = executor.submit(
                    process_commit, next_i, next_parts, total_unscanned,
                    arch_context, MODEL_NAME, RUBRIC_PATH, rate_limits, aimd
                )
                active_futures[future] = next_i
            except StopIteration:
                break
        
        # Process results as they complete
        while active_futures:
            done, _ = wait(active_futures, return_when=FIRST_COMPLETED)

            for future in done:
                commit_i = active_futures.pop(future, "?")
                try:
                    result_i, result = future.result(timeout=120)
                except Exception as e:
                    print(f"⚠️ Worker failed on commit {commit_i}: {e}", flush=True)
                    result_i, result = commit_i, None

                pending_results[result_i] = result

                try:
                    next_i, next_parts = next(commit_iterator)
                    print(f"DEBUG: Submitting commit {next_i}", flush=True)
                    new_future = executor.submit(
                        process_commit, next_i, next_parts, total_unscanned,
                        arch_context, MODEL_NAME, RUBRIC_PATH, rate_limits, aimd
                    )
                    active_futures[new_future] = next_i
                except StopIteration:
                    pass

            # Flush results in order
            while next_to_write in pending_results:
                res = pending_results.pop(next_to_write)
                if res:
                    if isinstance(res, str):
                        error_count += 1
                        print(res, flush=True)
                    else:
                        headers, row, hash_short, ui_block = res
                        success_count += 1
                        write_csv_row(CSV_PATH, headers, row, is_first_write=(next_to_write == 1 and not file_exists))
                        if next_to_write == 1 and not file_exists:
                            file_exists = True
                        existing_hashes.add(hash_short)
                        print(ui_block, flush=True)
                next_to_write += 1
    
    # Final status
    if error_count > 0:
        print(f'⚠️ PROCESS_COMPLETE_WITH_ERRORS: {error_count} failed, {success_count} succeeded.\n\n', flush=True)
    else:
        print('🤝 Repository ledger up to date!\n\n', flush=True)
    
    # Timer
    elapsed = time.time() - start_time
    print(f'⏱️  Total execution time: {int(elapsed//60)}m {int(elapsed%60)}s\n', flush=True)

if __name__ == "__main__":
    main()
