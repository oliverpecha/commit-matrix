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
    MATRIX_ARCH_ENABLED,
    MATRIX_ARCH_ALLOW_STALE_CONTINUE,
)
from backend.services.architecture_generator import ensure_fresh_architecture_context, build_arch_gen_trail, ArchStatus


# ---------------------------------------------------------------------------
# Architecture Generation mapping
# ---------------------------------------------------------------------------
def _compute_arch_gen(versions_dir: "Path", arch_tree_signature: str) -> int | None:
    """Map a tree signature to an Architecture Generation number.

    Rule:
    - First snapshot => Generation #1.
    - Each subsequent snapshot whose change_shape does NOT start with "leaf-only"
      bumps the Generation number by 1.
    - leaf-only snapshots stay in the same Generation as the previous snapshot.
    """
    import json as _json

    if not versions_dir.exists():
        return None

    snapshots = sorted(p for p in versions_dir.glob("arch-*.md") if p.is_file())
    if not snapshots:
        return None

    current_gen = 1
    found_gen = None

    for idx, snap in enumerate(snapshots):
        meta_sidecar = snap.with_suffix(".meta.json")
        snap_sig = ""
        shape = "unknown"

        if meta_sidecar.exists():
            try:
                meta = _json.loads(meta_sidecar.read_text(encoding="utf-8"))
                snap_sig = meta.get("tree_signature", "") or ""
                shape = (meta.get("change_summary") or {}).get("change_shape", "unknown")
            except Exception:
                snap_sig = ""
                shape = "unknown"

        if not snap_sig:
            snap_sig = snap.stem[len("arch-"):]

        if idx > 0 and not shape.startswith("leaf-only"):
            current_gen += 1

        if (
            snap_sig == arch_tree_signature
            or arch_tree_signature.startswith(snap_sig)
            or snap_sig.startswith(arch_tree_signature[:16])
        ):
            found_gen = current_gen

    return found_gen


def main():
    """Main orchestrator."""
    start_time = time.time()
    
    parser = argparse.ArgumentParser(description='CommitMatrix LLM-powered commit analyzer')
    parser.add_argument('--repo', required=True, help='Path to git repository')
    parser.add_argument('--arch-test-only', action='store_true',
                        help='Run only the architecture context gate and exit before scoring')
    args = parser.parse_args()
    
    repo_path = args.repo

    # --- ARCHITECTURE CONTEXT GATE (Milestone 1 skeleton) ---
    arch_gate = ensure_fresh_architecture_context(repo_path)
    if arch_gate.status == ArchStatus.FAILED:
        repo_label = os.path.basename(repo_path) or repo_path
        print(f"❌ Architecture context unavailable for [{repo_label}]: {arch_gate.reason}", flush=True)
        sys.exit(1)

    # Architecture context status line
    # NOTE: if running in arch-test-only mode, exit after printing status.
    if args.arch_test_only:
        return

    meta = arch_gate.metadata or {}
    cs = meta.get("change_summary") or {}
    generated_at = meta.get("generated_at")

    age_desc = "age: unknown"
    mins = None
    if generated_at:
        from datetime import datetime, timezone
        try:
            ts = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
            delta = datetime.now(timezone.utc) - ts
            mins = int(delta.total_seconds() // 60)
            if mins < 60:
                age_desc = f"age: {mins}m"
            else:
                hours = mins // 60
                age_desc = f"age: {hours}h"
        except Exception:
            age_desc = "age: unknown"
            mins = None

    selected_count = cs.get("selected_files_count")
    total_files = cs.get("total_files")
    mode = cs.get("mode", "unknown")

    includes_desc = f"includes: {selected_count} system files" if selected_count is not None else "includes: unknown files"
    tree_desc = f"tree size: {total_files}" if total_files is not None else "tree size: unknown"

    if arch_gate.reason and "existing architecture blueprint is current" in arch_gate.reason:
        # Reuse: blueprint was already current for this ArchSig
        print(f"🧩  Reusing architecture blueprint ({age_desc}, {includes_desc}, {tree_desc}, mode={mode})", flush=True)
    else:
        # This run generated a fresh blueprint
        print(f"🧩  Generated fresh new architecture blueprint ({includes_desc}, {tree_desc}, mode={mode})", flush=True)

    print("", flush=True)

    # --- EMOJI & ARCHITECTURE FIX ---
    arch_context = get_architecture_context(repo_path)
    arch_tree_signature = (arch_gate.metadata or {}).get("tree_signature", "")

    if not arch_tree_signature and MATRIX_ARCH_ENABLED:
        print("❌ ArchSig is missing while MATRIX_ARCH_ENABLED is true. Aborting.", flush=True)
        sys.exit(1)

    if arch_tree_signature:
        # --- M3[B+C]: architecture change + generation number ---
        try:
            repo_label = os.path.basename(repo_path) or HOST_REPO_NAME
            data_dir = Path("data") / repo_label
            data_dir.mkdir(parents=True, exist_ok=True)
            marker_path = data_dir / "last_arch_sig"

            last_sig = marker_path.read_text(encoding="utf-8").strip() if marker_path.exists() else None

            # Compute Architecture Generation # using change_shape-aware mapping
            versions_dir = data_dir / "architecture_versions"
            arch_gen = _compute_arch_gen(versions_dir, arch_tree_signature)

            changed = bool(last_sig and last_sig != arch_tree_signature)
            if changed:
                # Show full signatures when changed
                print(f"🧬 Architecture Signature changed: {last_sig} ➔ {arch_tree_signature}", flush=True)
            else:
                # First run or same sig: single line with gen number if known
                if arch_gen is not None:
                    print(f"🧬 Architecture Signature {arch_tree_signature} (Architecture Gen #{arch_gen})", flush=True)
                else:
                    print(f"🧬 Architecture Signature {arch_tree_signature}", flush=True)

            marker_path.write_text(arch_tree_signature, encoding="utf-8")
        except Exception:
            # observability-only; do not break orchestration
            pass

        print("", flush=True)

    is_reuse = bool(arch_gate.reason and "existing architecture blueprint is current" in arch_gate.reason)

    if arch_context and len(arch_context.strip()) > 10:
        repo_label = os.path.basename(repo_path)
        if is_reuse:
            print(f"🗺️  Cached architecture map loaded for [{repo_label}].\n", flush=True)
        else:
            print(f"🗺️  Architecture map initialized for [{repo_label}].\n", flush=True)
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
            arch_context, MODEL_NAME, RUBRIC_PATH, rate_limits, aimd,
            arch_tree_signature=arch_tree_signature,
            arch_gen=arch_gen,
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
                    arch_context, MODEL_NAME, RUBRIC_PATH, rate_limits, aimd,
                    arch_tree_signature=arch_tree_signature,
                    arch_gen=arch_gen,
                    arch_gen_trail=arch_gen_trail,
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
