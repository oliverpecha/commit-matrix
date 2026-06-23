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
from backend.cli.arch_history.data.metrics import compute_generation_summaries
from backend.services.pipeline.preflight import extract_commit_sha
from backend.services.pipeline.preflight import prepare_commit_work_item


def print_architecture_event(state, repo_label=None, db_path=None):
    if not state.available:
        print("\u2500" * 71, flush=True)
        print("\U0001f3d7\ufe0f  Architecture unavailable", flush=True)
        print(f"    {state.summary}", flush=True)
        print("\u2500" * 71 + "\n", flush=True)
        return

    if not (state.established or state.advanced):
        return

    try:
        from backend.cli.arch_history.taxonomy import get_shape_metadata
        shape_meta = get_shape_metadata(state.change_shape or "unknown")
        icon = shape_meta.get("icon", "\U0001f3d7\ufe0f")
        label = shape_meta.get("label", state.change_shape or "unknown")
    except Exception:
        icon = "\U0001f3d7\ufe0f"
        label = state.change_shape or "unknown"

    if state.established:
        title = f"{icon}  Architecture Head established"
    else:
        title = f"{icon}  New architectural boundary detected"

    # Compute rich metrics if DB available
    metrics_lines = []
    if repo_label and db_path and state.gen:
        try:
            # Import metrics function
            try:
                from backend.cli.arch_history.data.metrics import compute_generation_summaries
            except ImportError:
                from backend.services.architecture.metrics import compute_generation_summaries
            summaries = compute_generation_summaries(repo_label, db_path)
            # Find current generation's metrics
            gen_summary = next((s for s in summaries if s.gen == state.gen), None)
            if gen_summary:
                era_pct = gen_summary.dominant_share_of_generation * 100 if gen_summary.dominant_share_of_generation else 0
                metrics_lines.append(f"    📊 Era     │ {gen_summary.snapshot_count} Snapshots ({gen_summary.structural_count} structural, {gen_summary.incremental_count} incremental)")
                if gen_summary.repeated_treesig_count > 0:
                    metrics_lines.append(f"    🔄 Recycles│ {gen_summary.repeated_treesig_count} repeated tree signature(s) detected")
                if gen_summary.dominant_snapshot_sig:
                    dom_short = gen_summary.dominant_snapshot_sig[:8]
                    metrics_lines.append(f"    👑 Dominant│ {dom_short}... (Holds {era_pct:.0f}% of era history)")
        except Exception as e:
            import sys
            print(f"[metrics warning] {e}", file=sys.stderr)
            pass  # Metrics optional, don't crash on failure

    print("\u2500" * 71, flush=True)
    print(title, flush=True)
    print(f"    Cause     \u2502 {label}", flush=True)
    print(f"    Shape     \u2502 {state.change_shape or 'unknown'}", flush=True)
    print(f"    Mode      \u2502 {state.mode or 'unknown'}", flush=True)
    for line in metrics_lines:
        print(line, flush=True)
    print("\u2500" * 71 + "\n", flush=True)

def main():
    start_time = time.time()

    parser = argparse.ArgumentParser(description="CommitMatrix LLM-powered commit analyzer")
    parser.add_argument("--repo", required=True, help="Path to git repository")
    args = parser.parse_args()

    repo_path = args.repo
    repo_label = os.path.basename(repo_path.rstrip("/")) or repo_path
    db_path = f"data/{repo_label}/commit_matrix.db"
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
        # Registry to hold boundaries until their trigger commit is flushed
        boundary_registry = {}
        
        def _prepare_and_report(ordinal, topo_id, commit_parts):
            work_item, arch_state = prepare_commit_work_item(
                topo_id=topo_id,
                commit_parts=commit_parts,
                total_unscanned=total_unscanned,
                processed_count=ordinal,
                ordinal_in_window=ordinal,
                model_name=MODEL_NAME,
                rubric_path=RUBRIC_PATH,
                tracker=tracker,
            )
            # Thread architecture metadata for commit cards
            work_item.arch_change_shape = getattr(arch_state, "change_shape", "unknown")
            work_item.arch_meta = getattr(arch_state, "metadata", None)
            
            # Store boundary for synchronized rendering (don't print yet)
            # Exception: Architecture Head prints immediately (no prior commit to anchor to)
            # Architecture Head prints immediately, others synchronized
            if arch_state.established:
                print_architecture_event(arch_state, repo_label, db_path)
            elif arch_state.advanced:
                # Boundary triggered by PREVIOUS commit (current commit is first of new era)
                # Store with previous topo_id so it prints AFTER the trigger commit
                trigger_topo = topo_id - 1
                trigger_hash = work_item.commit_parts[0] if work_item.commit_parts else None
                boundary_registry[trigger_topo] = (arch_state, trigger_hash)
                
                # Persist boundary to DB immediately for CLI consistency
                try:
                    from backend.services.db.writer import write_boundary_state
                    write_boundary_state(
                        repo_label, trigger_topo, trigger_hash,
                        arch_state.change_shape, arch_state.mode, db_path
                    )
                except Exception as e:
                    import sys
                    print(f"[boundary persist warning] {e}", file=sys.stderr)
            
            return work_item

        work_item_iter_ref = iter(
            _prepare_and_report(ordinal_in_window, topo_id, commit_parts)
            for ordinal_in_window, topo_id, commit_parts in display_commits
        )
        active_futures = {}

        # Print Architecture Head BEFORE first commit if it's in registry
        # (It gets stored during seed_initial_batch preparation)
        
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
                # SYNCHRONIZED BOUNDARY RENDERING
                # Strategy: Architecture Head (lowest topo_id) prints before first commit
                # Other boundaries print immediately AFTER their trigger commit card
                if "🧬 Commit #" in output:
                    try:
                        # Parse topo_id from header line
                        header_line = output.split("\n")[1] if "\n" in output else output
                        current_topo = int(header_line.split("🧬 Commit #")[1].split("•")[0].strip())
                        
                        # Check for Architecture Head first (prints before/during first commit)
                        printed_head = False
                        for topo_id, (arch_state, _) in list(boundary_registry.items()):
                            if arch_state.established:
                                boundary_registry.pop(topo_id)
                                print_architecture_event(arch_state, repo_label, db_path)
                                printed_head = True
                                break
                        
                        # Print boundary AFTER its trigger commit
                        if current_topo in boundary_registry:
                            arch_state, _ = boundary_registry.pop(current_topo)
                            print_architecture_event(arch_state, repo_label, db_path)
                    except (ValueError, IndexError, KeyError):
                        pass

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

    # Architecture summary block
    try:
        from backend.services.db.reader import read_scan_range, read_vacuums
        import sqlite3

        scan = read_scan_range(repo_label)
        vacuums = read_vacuums(repo_label)

        conn = sqlite3.connect(db_path)
        snap_count = conn.execute(
            "SELECT COUNT(*) FROM architecture_snapshots WHERE run_id = 1"
        ).fetchone()[0]
        boundary_count = conn.execute(
            "SELECT COUNT(*) FROM architecture_boundaries WHERE run_id = 1"
        ).fetchone()[0]
        conn.close()

        print("─" * 71, flush=True)
        print("🏗️  Architecture Summary", flush=True)
        print(
            f"    Boundaries    │ {boundary_count} structural shifts detected",
            flush=True,
        )
        print(
            f"    Snapshots     │ {snap_count} unique architecture states",
            flush=True,
        )
        if scan:
            print(
                f"    Commits       │ processed (#{scan['scan_head_topo']} to #{scan['scan_tail_topo']})",
                flush=True,
            )
        if vacuums:
            total_vac = sum(v.get("commit_count", 0) for v in vacuums)
            print(
                f"    Vacuums       │ {total_vac} unscanned",
                flush=True,
            )
        print("─" * 71 + "\n", flush=True)
    except Exception:
        pass

    if error_count > 0:
        print(f"⚠️ PROCESS_COMPLETE_WITH_ERRORS: {error_count} failed, {success_count} succeeded.\n\n", flush=True)
    else:
        print("🤝 Repository ledger up to date!\n\n", flush=True)


    elapsed = time.time() - start_time
    print(f"⏱️  Total execution time: {int(elapsed // 60)}m {int(elapsed % 60)}s\n", flush=True)


if __name__ == "__main__":
    main()
