from __future__ import annotations
import sys
import threading
from pathlib import Path

_ORACLE_READY_EVENT = threading.Event()

def wait_for_oracle_sync(timeout: float = 120.0) -> bool:
    return _ORACLE_READY_EVENT.wait(timeout)

def ensure_architecture_oracle(repo_path: str, db_path: str) -> None:
    db = Path(db_path)
    if db.exists() and db.stat().st_size > 8192: 
        try:
            import sqlite3
            conn = sqlite3.connect(str(db))
            _table_check = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='architecture_commits'").fetchone()
            max_db_topo = 0
            if _table_check:
                max_db_topo = conn.execute("SELECT MAX(topo_id) FROM architecture_commits").fetchone()[0] or 0
                count = conn.execute("SELECT COUNT(*) FROM architecture_boundaries").fetchone()[0]
                conn.close()
                
                if count > 0:
                    from backend.services.pipeline.repo_bootstrap import build_commit_queue
                    bootstrap_res = build_commit_queue(repo_path, set())
                    max_git_topo = max([int(t) for t, _ in bootstrap_res.get("commits_with_ids", [])]) if bootstrap_res.get("commits_with_ids") else 0
                    
                    if max_git_topo <= max_db_topo:
                        _ORACLE_READY_EVENT.set()
                        return
                    else:
                        print(f"\n🔄 Incremental sync needed: DB head is #{max_db_topo}, Git head is #{max_git_topo}. Processing delta...", flush=True)
            else:
                conn.close()
        except Exception:
            pass
            
    _ORACLE_READY_EVENT.clear()
    backfill_thread = threading.Thread(
        target=_build_oracle_sync, 
        args=(repo_path, db_path),
        daemon=True
    )
    backfill_thread.start()

def _build_oracle_sync(repo_path: str, db_path: str) -> None:
    if str(__import__("os").environ.get("MATRIX_DEBUG", "")).lower() in ("1", "true", "yes"):
        print("\n[arch-oracle] 🧊 Cold start detected. Initializing database state...", flush=True)

    try:
        import sqlite3
        from backend.services.pipeline.repo_bootstrap import build_commit_queue
        from backend.utils.csv_writer import ensure_csv_exists
        from backend.services.pipeline.pipeline_config import CSV_PATH
        from backend.services.architecture.arch_resolver import ArchitectureResolver
        from backend.services.db.schema import SCHEMA_SQL
        from backend.services.architecture.arch_storage import repo_id_from_path

        ensure_csv_exists(CSV_PATH)
        bootstrap_res = build_commit_queue(repo_path, set())
        all_commits = bootstrap_res.get("commits_with_ids", [])
        
        with sqlite3.connect(db_path) as _conn:
            _table_exists = _conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='architecture_commits'").fetchone()
            max_db_topo = 0
            if _table_exists:
                max_db_topo = _conn.execute("SELECT MAX(topo_id) FROM architecture_commits").fetchone()[0] or 0
            else:
                _conn.executescript(SCHEMA_SQL)
                
        commits_with_ids = [(t, c) for t, c in all_commits if int(t) > max_db_topo]

        if commits_with_ids:
            with sqlite3.connect(db_path) as _conn:
                _conn.execute("PRAGMA journal_mode=WAL")
                _conn.execute("UPDATE architecture_snapshots SET shape = 'leaf-only', shape_label = 'Stable Implementation Refinement' WHERE shape = 'head'")
                _conn.execute("DELETE FROM architecture_boundaries WHERE cause_tag IN ('head', 'major:head', 'current architecture head', 'Stable Implementation Refinement', 'leaf-only') OR boundary_commit_topo_id = ?", (max_db_topo,))
                _conn.execute("UPDATE architecture_commits SET role = 'successive' WHERE topo_id = ?", (max_db_topo,))
                _conn.commit()

        tracker = ArchitectureResolver(repo_path=repo_path)
        resolved_states = []
        for topo_id, commit_parts in commits_with_ids:
            commit_hash = str(commit_parts[0]).strip()
            date_str = str(commit_parts[1]) if len(commit_parts) > 1 else ""
            subject = str(commit_parts[3]) if len(commit_parts) > 3 else ""

            absolute_head_topo = max([int(t) for t, _ in all_commits]) if all_commits else int(topo_id)
            is_head_fallback = (int(topo_id) == absolute_head_topo)
            state, meta = tracker.resolve_for_commit(commit_hash, topo_id=topo_id, is_head_fallback=is_head_fallback)
            
            if state and getattr(state, "signature", None):
                is_merge = False
                try:
                    import subprocess
                    parents_out = subprocess.check_output(
                        ["git", "-C", repo_path, "log", "-1", "--pretty=%P", commit_hash], text=True
                    ).strip()
                    if len(parents_out.split()) > 1: is_merge = True
                except: pass
            
                resolved_states.append({
                    "topo_id": topo_id, "commit_hash": commit_hash, "date_str": date_str, 
                    "subject": subject, "is_head_fallback": is_head_fallback, 
                    "current_sig": getattr(state, "signature"), "shape": getattr(state, "change_shape", ""),
                    "is_merge": is_merge
                })

        if resolved_states:
            from backend.services.db.writer import incremental_sync_commit_states
            repo_label = repo_id_from_path(repo_path)
            incremental_sync_commit_states(repo_label, db_path, resolved_states)

        with sqlite3.connect(db_path) as conn:
            _check = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='architecture_snapshots'").fetchone()
            if _check:
                from backend.services.db.reader import _sqlite_is_macro
                conn.create_function("IS_MACRO", 1, _sqlite_is_macro)
                snap_count = conn.execute("SELECT COUNT(*) FROM architecture_snapshots").fetchone()[0]
                bound_count = conn.execute("SELECT COUNT(*) FROM architecture_boundaries").fetchone()[0]
                commit_count = conn.execute("SELECT COUNT(*) FROM architecture_commits").fetchone()[0]
                
                print("\n" + "─" * 71, flush=True)
                print("✅ Oracle Initialization Confirmed (Phase 2 Complete)", flush=True)
                print(f"    Snapshots Generated │ {snap_count}", flush=True)
                print(f"    Boundaries Mapped   │ {bound_count}", flush=True)
                print(f"    Commits Linked      │ {commit_count}", flush=True)
                print("─" * 71 + "\n", flush=True)
                
        _ORACLE_READY_EVENT.set()
    except Exception as e:
        _ORACLE_READY_EVENT.set()
        print(f"❌ FATAL [arch_sync]: Oracle bootstrap failed: {e}", file=sys.stderr)
        sys.exit(1)
