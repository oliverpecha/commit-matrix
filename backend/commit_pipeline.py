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
from backend.services.architecture.metrics import compute_generation_summaries
from backend.services.pipeline.prep_scoring import extract_commit_sha
from backend.utils.logger import DualLogger
from backend.services.pipeline.pipeline_presentation import render_bootstrap_banner, print_debug_boundary_table, print_oracle_initialization

def get_db_connection(db_path: str):
    import sqlite3
    conn = sqlite3.connect(db_path, timeout=10.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn



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
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            repo_label = "commit-matrix"

    if repo_label in (".", "target_repo", "", "app", None):
        repo_label = "commit-matrix"

    timestamp = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
    log_dir = f"/app/data/{(os.environ.get('HOST_REPO_OWNER') or 'local')}/{repo_label}/pipeline_runs" if os.path.exists("/.dockerenv") else f"data/{(os.environ.get('HOST_REPO_OWNER') or 'local')}/{repo_label}/pipeline_runs"
    log_filename = f"run_{timestamp}_UTC.log"
    full_log_path = os.path.join(log_dir, log_filename)

    try:
        logger_instance = DualLogger(sys.stdout, full_log_path)
        sys.stdout = logger_instance
        sys.stderr = logger_instance
        
        # --- Universal Container Heartbeat ---
        import sqlite3, atexit, socket
        _clear_heartbeat = lambda: None
        r_db = "/app/data/registry.db" if os.path.exists("/.dockerenv") else "data/registry.db"
        try:
            container_id = socket.gethostname()
            def _heartbeat_conn():
                conn = sqlite3.connect(r_db, timeout=15.0)
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("CREATE TABLE IF NOT EXISTS repositories (repo_name TEXT PRIMARY KEY, owner TEXT, remote_url TEXT, target_branch TEXT, repo_path TEXT, root_commit TEXT, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
                cols = {row[1] for row in conn.execute("PRAGMA table_info(repositories)").fetchall()}
                for col in ("active_container_id", "active_log_path", "exec_mode"):
                    if col not in cols:
                        conn.execute(f"ALTER TABLE repositories ADD COLUMN {col} TEXT")
                conn.commit()
                return conn

            def _register_heartbeat():
                try:
                    conn = _heartbeat_conn()
                    try:
                        conn.execute("INSERT OR IGNORE INTO repositories (repo_name) VALUES (?)", (repo_label,))
                        exec_mode = "docker" if os.path.exists("/.dockerenv") else os.environ.get("EXEC_MODE", "native")
                        conn.execute(
                            "UPDATE repositories SET active_container_id=?, active_log_path=?, exec_mode=? WHERE repo_name=?",
                            (container_id, full_log_path, exec_mode, repo_label)
                        )
                        conn.commit()
                    finally:
                        conn.close()
                    print(f"💓 Heartbeat registered → {exec_mode} run '{container_id}' linked to {repo_label} (log={full_log_path})", flush=True)
                except (KeyboardInterrupt, SystemExit):
                    raise
                except Exception as e:
                    print(f"⚠️ Heartbeat registration failed: {e}", flush=True)

            def _clear_heartbeat():
                try:
                    conn = _heartbeat_conn()
                    try:
                        conn.execute(
                            "UPDATE repositories SET active_container_id=NULL, active_log_path=NULL, exec_mode=NULL WHERE repo_name=?",
                            (repo_label,)
                        )
                        conn.commit()
                    finally:
                        conn.close()
                except Exception: pass

            _register_heartbeat()
            atexit.register(_clear_heartbeat)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:
            print(f"⚠️ Telemetry setup failed: {e}", flush=True)
        
        def handle_termination(signum, frame):
            _clear_heartbeat()
            print(f"\n🛑 Pipeline interrupted by signal ({signum}). Flushing buffers and closing logs.", flush=True)
            logger_instance.close()
            os._exit(128 + signum)
            
        import signal
        signal.signal(signal.SIGINT, handle_termination)
        signal.signal(signal.SIGTERM, handle_termination)
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as e:
        logger_instance = None
        print(f"⚠️ Logger initialization failed: {e}. Defaulting to standard stdout.", flush=True)

    print(render_bootstrap_banner(repo_path, repo_label, full_log_path if logger_instance else None), flush=True)

    db_path = f"data/{(os.environ.get('HOST_REPO_OWNER') or 'local')}/{repo_label}/db/{repo_label}.db"
    try:
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        pass
    
    _csv_owner = os.environ.get('HOST_REPO_OWNER') or 'local'
    _csv_rubric = os.environ.get('RUBRIC_NAME', 'unknown')
    CSV_PATH = f"data/{_csv_owner}/{repo_label}/db/{repo_label}_ledger_{_csv_rubric}.csv"
    _csv_owner = os.environ.get('HOST_REPO_OWNER') or 'local'
    _csv_rubric = os.environ.get('RUBRIC_NAME', 'unknown')
    CSV_PATH = f"data/{_csv_owner}/{repo_label}/db/{repo_label}_ledger_{_csv_rubric}.csv"
    _csv_path = Path(CSV_PATH)
    is_genuine_warm_start = _csv_path.exists() and _csv_path.stat().st_size > 50

    from backend.services.architecture.arch_sync import ensure_architecture_oracle, wait_for_oracle_sync
    ensure_architecture_oracle(repo_path, db_path)
    wait_for_oracle_sync(repo_path=repo_path, db_path=db_path, timeout=120.0)

    import sqlite3 as _boot_sq
    
    from backend.services.pipeline.repo_bootstrap import sync_central_registry
    sync_central_registry(db_path, repo_path)

    if is_genuine_warm_start:
        try:
            with get_db_connection(db_path) as _b_conn:
                _t_exists = _b_conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='architecture_boundaries'").fetchone()
                if _t_exists:
                    _rubric = os.environ.get("RUBRIC_NAME", "unknown")
                    _r_row = _b_conn.execute("SELECT run_id FROM architecture_runs WHERE repo_label = ?", (repo_label,)).fetchone()
                    _run_id = _r_row[0] if _r_row else -1
                    _b_count = _b_conn.execute("SELECT COUNT(*) FROM architecture_boundaries WHERE run_id = ?", (_run_id,)).fetchone()[0] if _run_id != -1 else 0
                    if _b_count > 0:
                        print("\n[arch-oracle] ♨️  Warm start detected. Linking to existing ledger...", flush=True)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            pass

    # Display Architecture Boundary Map during standard execution
    print_oracle_initialization(repo_label, db_path, is_genuine_warm_start)

    print(flush=True)
    print_debug_boundary_table(repo_label, db_path)

    existing_hashes = load_existing_hashes(CSV_PATH)
    bootstrap_res = build_commit_queue(repo_path, existing_hashes)
    commits_with_ids = bootstrap_res['commits_with_ids']
    total_unscanned = bootstrap_res.get('total_found', len(commits_with_ids))

    if total_unscanned == 0 and len(existing_hashes) == 0:
        print('\n⚠️ FATAL: No commits found in target repository.')
        print(f'Please ensure the source code is present at: {repo_path}')
        print('Pipeline aborting to prevent empty ledger creation.\n', flush=True)
        sys.exit(1)

    aimd = AIMDController(initial=1, max_workers=MAX_WORKERS)
    rate_limits = RateLimitsController(target_rpm=TARGET_RPM)
    file_exists = ensure_csv_exists(CSV_PATH)

    display_commits = [
        (ordinal_in_window, int(topo_id), commit_parts)
        for ordinal_in_window, (topo_id, commit_parts) in enumerate(commits_with_ids, start=1)
    ]
    
    topo_to_sha = {tid: str(cp[0])[:7] if cp and len(cp) > 0 else "unknown" for _, tid, cp in display_commits}

    flush_state = init_flush_state([
        (topo_id, commit_parts)
        for _, topo_id, commit_parts in display_commits
    ])
    processed_count = 0

    boundary_registry = {}
    from collections import defaultdict
    snapshot_commits = defaultdict(list)

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

        try:
            from backend.services.db.reader import get_structural_boundaries_for_stream
            boundary_schedule = get_structural_boundaries_for_stream(repo_label, db_path)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            boundary_schedule = {}

        while active_futures:
            done, _ = wait(active_futures, return_when=FIRST_COMPLETED)
            for future in done:
                topo_id = active_futures.pop(future, "?")
                resolved = resolve_future_result(future, topo_id, timeout=120)
                result_i, result, log_msg = resolved
                
                if isinstance(result, tuple) and len(result) == 4:
                    headers, row, hash_short, ui_block = result
                    ui_str = str(ui_block)
                    if '__TOPO:' not in ui_str:
                        ui_str = ui_str.replace(f'🧬 Matrix #{topo_id}', f'🧬 Commit #{topo_id} __TOPO:{topo_id}__', 1)
                        ui_str = ui_str.replace(f'🧬 Commit #{topo_id}', f'🧬 Commit #{topo_id} __TOPO:{topo_id}__', 1)
                    result = (headers, row, hash_short, ui_str)
                elif isinstance(result, dict) and result.get('success'):
                    wi = work_item_map.get(topo_id)
                    pct = int((processed_count / total_unscanned) * 100) if total_unscanned else 100
                    filled = int((processed_count / total_unscanned) * 16) if total_unscanned else 16
                    p_data = {'pct': pct, 'filled': filled, 'remaining': max(0, total_unscanned - processed_count)}
                    from backend.services.pipeline.pipeline_presentation import render_commit_score_card
                    ui_card = render_commit_score_card(wi, result, p_data)
                    headers = result.get('headers', result.get('csv_headers', []))
                    row = result.get('row', result.get('csv_row', []))
                    hash_short = wi.arch_meta.get('commit_sha', 'unknown')[:7] if wi and getattr(wi, 'arch_meta', None) else "unknown"
                    result = (headers, row, hash_short, ui_card)

                stash_result(flush_state, int(topo_id), result)
                
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
                m = re.search(r"__TOPO:(\d+)__", output)
                if "🧬 Commit #" in output and m:
                    try:
                        res_topo = int(m.group(1))
                        import sqlite3 as _sq
                        _conn = get_db_connection(db_path)
                        _cursor = _conn.cursor()

                        _cursor.execute("SELECT snapshot_sig, commit_sig FROM architecture_commits WHERE topo_id = ?", (res_topo,))
                        _curr = _cursor.fetchone()
                        if _curr and _curr[0]:
                            curr_sig, curr_commit = _curr
                            
                            _cursor.execute("SELECT snapshot_sig FROM architecture_commits WHERE topo_id < ? AND snapshot_sig IS NOT NULL ORDER BY topo_id DESC LIMIT 1", (res_topo,))
                            _prev_row = _cursor.fetchone()
                            prev_sig = _prev_row[0] if _prev_row else curr_sig
                            
                            is_era_trigger = (res_topo in boundary_schedule)
                            if curr_sig != prev_sig or is_era_trigger:
                                _cursor.execute("SELECT shape FROM architecture_snapshots WHERE snapshot_sig = ?", (curr_sig,))
                                _shape_row = _cursor.fetchone()
                                
                                is_head_root = is_era_trigger and boundary_schedule[res_topo].get("cause_tag") in ("head", "major:head", "current architecture head")
                                raw_shape = "head" if is_head_root else (_shape_row[0] if _shape_row else "leaf-only")
                                effective_era_trigger = is_era_trigger if not is_head_root else False
                                
                                from backend.services.pipeline.pipeline_presentation import report_sensor_mutation
                                report_sensor_mutation(curr_commit, prev_sig, curr_sig, raw_shape, effective_era_trigger)

                        if res_topo in boundary_schedule:
                            try:
                                from backend.services.pipeline.pipeline_presentation import render_boundary_banner
                                banner = render_boundary_banner(boundary_schedule[res_topo], curr_sig or "pending")
                                if banner:
                                    print("\n" + banner, end="", flush=True)
                            except (KeyboardInterrupt, SystemExit):
                                raise
                            except Exception:
                                pass

                        _conn.close()
                    except (KeyboardInterrupt, SystemExit):
                        raise
                    except Exception:
                        pass
                
                clean_output = re.sub(r" __TOPO:\d+__", "", output)
                print(clean_output, flush=True)

    try:
        if commits_with_ids:
            head_topo = commits_with_ids[0][0]
            tail_topo = commits_with_ids[-1][0]
            from backend.services.db.writer import update_scan_range
            _rubric = os.environ.get("RUBRIC_NAME", "unknown")
            update_scan_range(repo_label, head_topo, tail_topo)
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        pass

    error_count = flush_state["error_count"]
    success_count = flush_state["success_count"]

    from backend.services.pipeline.pipeline_presentation import print_final_pipeline_summary_report
    print_final_pipeline_summary_report(repo_label, db_path, commits_with_ids)

    if error_count > 0:
        print(f"⚠️ PROCESS_COMPLETE_WITH_ERRORS: {error_count} failed, {success_count} succeeded.\n", flush=True)
    else:
        print("🤝 Repository ledger up to date!\n", flush=True)

    elapsed = time.time() - start_time
    print(f"⏱️  Total execution time: {int(elapsed // 60)}m {int(elapsed % 60)}s", flush=True)

if __name__ == "__main__":
    main()
