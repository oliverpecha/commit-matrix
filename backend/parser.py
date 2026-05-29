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
if os.environ.get("MATRIX_DEBUG") != "1":
    logging.getLogger("litellm").setLevel(logging.WARNING)

from concurrent.futures import ThreadPoolExecutor, as_completed, wait, FIRST_COMPLETED

if "GEMINI_API_KEY" in os.environ:
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

from controllers.aimd import AIMDController
from controllers.rate_limits import RateLimitsController
from workers.commit_processor import process_commit
from utils.git_ops import get_commits, get_commit_diff, get_architecture_context
from utils.csv_writer import ensure_csv_exists, write_csv_row, load_existing_hashes

# Constants
MODEL_NAME = os.environ.get('MATRIX_MODEL', 'gemini/gemini-2.5-flash-lite')
TARGET_RPM = float(os.environ.get('MATRIX_RPM_LIMIT', os.environ.get('TARGET_RPM', '15.0')))
MAX_WORKERS = int(os.environ.get('MATRIX_MAX_WORKERS', os.environ.get('MAX_WORKERS', '6')))
HOST_REPO_NAME = os.environ.get('HOST_REPO_NAME', 'commit-matrix')
RUBRIC_NAME = os.environ.get('RUBRIC_NAME', 'cirsd')
CSV_PATH = f'/app/data/{HOST_REPO_NAME}/{HOST_REPO_NAME}_ledger_{RUBRIC_NAME}.csv'
RUBRIC_PATH = f'/app/rubrics/{RUBRIC_NAME}.md'


def build_topo_index(repo_path):
    """Return {hash_short: global_topo_n} oldest->newest from full git history."""
    topo = {}
    log_output = get_commits(repo_path)
    lines = [line for line in log_output.strip().split('\n') if '|' in line]
    lines.reverse()
    for idx, line in enumerate(lines, start=1):
        hash_full = line.split('|')[0].strip()
        topo[hash_full[:7]] = idx
    return topo

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
    topo_map = build_topo_index(repo_path)
    
    # Get all commits
    log_output = get_commits(repo_path)
    lines = log_output.strip().split('\n')
    
    commits = []
    seen_unscanned = set()
    i = 0
    while i < len(lines):
        if '|' in lines[i]:
            parts = lines[i].split('|')
            hash_full = parts[0]
            hash_short = hash_full[:7]
            
            if hash_short not in existing_hashes and hash_short not in seen_unscanned:
                seen_unscanned.add(hash_short)
                diff = get_commit_diff(hash_full, repo_path)
                commits.append((hash_full, parts[1], parts[2], parts[3], diff))
            i += 1
        else:
            i += 1
            
    # --- GLOBAL TOPO IDS + NEWEST-FIRST PROCESSING ---
    # Assign stable global topo IDs from full git history, then process newest first.
    commits_with_ids = []
    seen_topo = set()
    for commit in commits:
        hash_full = commit[0]
        hash_short = hash_full[:7]
        topo_id = topo_map.get(hash_short)
        if topo_id is None or topo_id in seen_topo:
            continue
        seen_topo.add(topo_id)
        commits_with_ids.append((topo_id, commit))

    # Process newest commits first using absolute topo IDs.
    commits_with_ids.sort(key=lambda x: x[0], reverse=True)
    
    # --- TOKEN SAVER: MAX COMMITS LIMIT ---
    total_found = len(commits_with_ids)
    max_commits = int(os.environ.get('MATRIX_MAX_COMMITS', '0'))
    if max_commits > 0 and len(commits_with_ids) > max_commits:
        commits_with_ids = commits_with_ids[:max_commits]
        
    
    total_unscanned = len(commits_with_ids)
    
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
    error_count = 0
    success_count = 0
    
    # --- WRITE QUEUE & PROGRESS TRACKING ---
    expected_write_order = [c[0] for c in commits_with_ids]
    write_index = 0
    processed_count = 1

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        commit_iterator = iter(commits_with_ids)
        active_futures = {}
        pending_results = {}
        
        # Seed initial batch
        for _ in range(MAX_WORKERS):
            try:
                next_i, next_parts = next(commit_iterator)
                future = executor.submit(
                    process_commit, next_i, next_parts, total_unscanned, processed_count,
                    arch_context, MODEL_NAME, RUBRIC_PATH, rate_limits, aimd
                )
                processed_count += 1
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
                    new_future = executor.submit(
                        process_commit, next_i, next_parts, total_unscanned, processed_count,
                        arch_context, MODEL_NAME, RUBRIC_PATH, rate_limits, aimd
                    )
                    processed_count += 1
                    active_futures[new_future] = next_i
                except StopIteration:
                    pass

            # Flush results in order of expected_write_order (Newest First)
            while write_index < len(expected_write_order) and expected_write_order[write_index] in pending_results:
                res_id = expected_write_order[write_index]
                res = pending_results.pop(res_id)
                if res:
                    if isinstance(res, str):
                        error_count += 1
                        print(res, flush=True)
                    else:
                        headers, row, hash_short, ui_block = res
                        success_count += 1
                        is_first = (write_index == 0 and not file_exists)
                        write_csv_row(CSV_PATH, headers, row, is_first_write=is_first)
                        if is_first:
                            file_exists = True
                        existing_hashes.add(hash_short)
                        print(ui_block, flush=True)
                write_index += 1
    
    if error_count > 0:
        print(f'⚠️ PROCESS_COMPLETE_WITH_ERRORS: {error_count} failed, {success_count} succeeded.\n\n', flush=True)
    else:
        print('🤝 Repository ledger up to date!\n\n', flush=True)
    
    elapsed = time.time() - start_time
    print(f'⏱️  Total execution time: {int(elapsed//60)}m {int(elapsed%60)}s\n', flush=True)

if __name__ == "__main__":
    main()
