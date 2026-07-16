from __future__ import annotations
import sqlite3
import sys
import threading

_ORACLE_READY_EVENT = threading.Event()

def _sqlite_is_macro(tag):
    if not tag: return 0
    t = str(tag).lower()
    if t in ('leaf-only', 'leaf_only', 'major:head', 'head'): return 0
    try:
        from backend.services.architecture.taxonomy import normalize_cause_tag, get_boundary_magnitude
        return 1 if get_boundary_magnitude(normalize_cause_tag(t)) == 'major' else 0
    except:
        return 0

from pathlib import Path
from typing import Tuple, Optional
from backend.services.pipeline.work_item import CommitWorkItem

def _build_oracle_sync(repo_path: str, db_path: str) -> None:
    # This runs in the background thread
    import os
    db_file = Path(db_path)
    if db_file.exists():
        try:
            conn = sqlite3.connect(db_path)
            count = conn.execute("SELECT COUNT(*) FROM architecture_boundaries").fetchone()[0]
            conn.close()
            if count > 0:
                return
        except sqlite3.OperationalError:
            pass

def ensure_architecture_oracle(repo_path: str, db_path: str) -> None:
    """
    Non-blocking Oracle Boot: Dispatches the heavy architecture resolving to a background thread
    so the container can start streaming immediately.
    """
    import os
    from pathlib import Path
    
    db = Path(db_path)
    # If DB already exists and has boundaries, skip thread creation entirely
    if db.exists() and db.stat().st_size > 8192: 
        try:
            import sqlite3
            conn = sqlite3.connect(str(db))
            count = conn.execute("SELECT COUNT(*) FROM architecture_boundaries").fetchone()[0]
            conn.close()
            if count > 0:
                _ORACLE_READY_EVENT.set()
                return
        except Exception:
            pass
            
    _ORACLE_READY_EVENT.clear()
            
    print(f"⚡ [arch-boot] Dispatching Oracle backfill to background thread...", flush=True)
    backfill_thread = threading.Thread(
        target=_build_oracle_sync, 
        args=(repo_path, db_path),
        daemon=True
    )
    backfill_thread.start()

def _build_oracle_sync(repo_path: str, db_path: str) -> None:
    db_file = Path(db_path)
    if db_file.exists():
        try:
            conn = sqlite3.connect(db_path)
            count = conn.execute("SELECT COUNT(*) FROM architecture_boundaries").fetchone()[0]
            conn.close()
            if count > 0:
                return
        except sqlite3.OperationalError:
            pass

    if str(__import__("os").environ.get("MATRIX_DEBUG", "")).lower() in ("1", "true", "yes"):
        print("\n[arch-oracle] 🏗️  Cold start detected. Initializing database state...", flush=True)

    try:
        from backend.services.pipeline.repo_bootstrap import build_commit_queue
        from backend.utils.csv_writer import load_existing_hashes, ensure_csv_exists
        from backend.services.pipeline.pipeline_config import CSV_PATH
        from backend.services.architecture.arch_resolver import ArchitectureResolver
        from backend.services.db.schema import SCHEMA_SQL

        existing_hashes = load_existing_hashes(CSV_PATH)
        ensure_csv_exists(CSV_PATH)
        bootstrap_res = build_commit_queue(repo_path, existing_hashes)
        commits_with_ids = bootstrap_res.get("commits_with_ids", [])

        if str(__import__("os").environ.get("MATRIX_DEBUG", "")).lower() in ("1", "true", "yes"):
            print("[arch-oracle] 💾 Populating relational schema...", flush=True)

        with sqlite3.connect(db_path) as _conn:
            _conn.executescript(SCHEMA_SQL)

        tracker = ArchitectureResolver(repo_path=repo_path)
        from backend.services.architecture.taxonomy import get_boundary_magnitude

        # Pass 1: Resolve architecture states in the required Head -> 1 direction
        resolved_states = []
        for topo_id, commit_parts in commits_with_ids:
            commit_hash = str(commit_parts[0]).strip()
            date_str = str(commit_parts[1]) if len(commit_parts) > 1 else ""
            subject = str(commit_parts[3]) if len(commit_parts) > 3 else ""

            absolute_head_topo = commits_with_ids[0][0] if commits_with_ids else topo_id
            is_head_fallback = (topo_id == absolute_head_topo)
            state, meta = tracker.resolve_for_commit(commit_hash, topo_id=topo_id, is_head_fallback=is_head_fallback)
            
            if state and getattr(state, "signature", None):
                resolved_states.append({
                    "topo_id": topo_id, "commit_hash": commit_hash, "date_str": date_str, 
                    "subject": subject, "is_head_fallback": is_head_fallback, 
                    "current_sig": getattr(state, "signature"), "shape": getattr(state, "change_shape", "")
                })

        # Pass 2: Evaluate boundaries and write to DB Reverse-Chronologically (Head -> 1)
        # Leading-edge tracking captures the exact moment a baseline opens an era.
        last_sig = None
        for item in resolved_states:
            current_sig = item["current_sig"]
            is_new_sig = (current_sig != last_sig)
            last_sig = current_sig
            
            with sqlite3.connect(db_path) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                run_row = conn.execute("SELECT run_id FROM architecture_runs ORDER BY run_id DESC LIMIT 1").fetchone()
                if not run_row: continue
                run_id = run_row[0]

                                # Prune branch merge commits (>1 parent) to prevent structural delta track-jumping hallucinations
                is_merge = False
                try:
                    import subprocess
                    parents_out = subprocess.check_output(
                        ["git", "-C", repo_path, "log", "-1", "--pretty=%P", item["commit_hash"]],
                        text=True
                    ).strip()
                    if len(parents_out.split()) > 1:
                        is_merge = True
                except Exception:
                    pass

                is_trigger = is_new_sig and (not is_merge or item["is_head_fallback"])
                role = "trigger" if is_trigger else "successive"
                
                conn.execute(
                    """UPDATE architecture_commits 
                       SET date = ?, subject = ?, role = ?
                       WHERE run_id = ? AND topo_id = ?""",
                    (item["date_str"], item["subject"], role, run_id, item["topo_id"])
                )

                if is_trigger:
                    # SSOT Sync: Fetch authoritative shape from architecture_snapshots to ensure 1:1 mapping with the stream sensor
                    snap_row = conn.execute("SELECT shape FROM architecture_snapshots WHERE snapshot_sig = ?", (current_sig,)).fetchone()
                    official_shape = snap_row[0] if snap_row else item.get("shape", "leaf-only")
                    
                    shape_str = str(official_shape).lower()
                    is_macro = ("major:" in shape_str or "multi-dir:" in shape_str or "isolated" in shape_str or "genesis" in shape_str or "critical" in shape_str)
                    
                    if is_macro or item["is_head_fallback"]:
                        exists = conn.execute(
                            "SELECT id FROM architecture_boundaries WHERE run_id = ? AND boundary_commit_topo_id = ?",
                            (run_id, item["topo_id"])
                        ).fetchone()
                        if not exists:
                            from backend.services.architecture.taxonomy import normalize_cause_tag
                            conn.execute(
                                "INSERT INTO architecture_boundaries (run_id, boundary_commit_sig, boundary_commit_topo_id, boundary_commit_date, boundary_commit_subject, cause_tag, magnitude) "
                                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                                (run_id, item["commit_hash"][:7], item["topo_id"], item["date_str"], item["subject"], normalize_cause_tag(official_shape), "structural")
                            )
                conn.commit()

        with sqlite3.connect(db_path) as conn:
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
        _ORACLE_READY_EVENT.set() # Ensure we don't permanently lock on failure
        print(f"❌ FATAL [prep-scoring]: Oracle bootstrap failed: {e}", file=sys.stderr)
        sys.exit(1)


def _resolve_db_arch_context(
    db_path: str,
    repo_label: str,
    topo_id: int,
) -> Tuple[Optional[str], Optional[str], Optional[int], Optional[str], Optional[str]]:
    """Resolve architecture context for scoring by reading the flat commit mapping directly."""
    conn = sqlite3.connect(db_path)
    try:
        conn.create_function('IS_MACRO', 1, _sqlite_is_macro)
        cur = conn.cursor()

        # Direct lookups from the flat architecture tracking tables
        cur.execute(
            """
            SELECT ac.snapshot_sig, ab.cause_tag, ab.magnitude, ac.run_id, ac.role
            FROM architecture_commits ac
            LEFT JOIN architecture_boundaries ab ON ab.boundary_commit_topo_id = ac.topo_id AND ab.run_id = ac.run_id
            WHERE ac.topo_id = ?
            ORDER BY ac.run_id DESC LIMIT 1
            """,
            (topo_id,),
        )
        row = cur.fetchone()
        if not row or not row[0]:
            # Fallback to the latest available snapshot if a flat commit record isn't committed yet
            cur.execute("SELECT snapshot_sig, 'Stable Implementation Refinement', 'incremental', run_id, 'successive' FROM architecture_commits WHERE run_id = (SELECT run_id FROM architecture_runs ORDER BY run_id DESC LIMIT 1) AND snapshot_sig IS NOT NULL ORDER BY topo_id ASC LIMIT 1")
            row = cur.fetchone()
            if not row:
                return None, None, None, None, None

        dominant_snapshot_sig, cause_tag, magnitude, run_id, role = row
        if not cause_tag:
            cause_tag = "Stable Implementation Refinement"


        cur.execute(
            """
            SELECT COUNT(DISTINCT boundary_commit_topo_id)
            FROM architecture_boundaries
            WHERE boundary_commit_topo_id <= (
                SELECT MIN(boundary_commit_topo_id)
                FROM architecture_boundaries
                WHERE boundary_commit_topo_id >= ?
                  AND run_id = (SELECT run_id FROM architecture_runs ORDER BY run_id DESC LIMIT 1)
            )
              AND run_id = (SELECT run_id FROM architecture_runs ORDER BY run_id DESC LIMIT 1)
            """,
            (topo_id,),
        )
        gen_row = cur.fetchone()
        generation = gen_row[0] if gen_row and gen_row[0] is not None else None

        snapshot_path = None
        if dominant_snapshot_sig:
            cur.execute(
                """
                SELECT snapshot_path
                FROM architecture_snapshots
                WHERE snapshot_sig = ?
                LIMIT 1
                """,
                (dominant_snapshot_sig,),
            )
            sp_row = cur.fetchone()
            if sp_row:
                snapshot_path = sp_row[0]

        arch_context: Optional[str] = None
        if snapshot_path:
            md_path = Path(snapshot_path)

            if md_path.is_absolute():
                candidate = md_path
            elif md_path.exists():
                candidate = md_path
            else:
                candidate = Path("data") / repo_label / "past_blueprints" / md_path.name

            if candidate.exists():
                arch_context = candidate.read_text(encoding="utf-8")

        return arch_context, cause_tag, generation, dominant_snapshot_sig, role
    finally:
        conn.close()


def prepare_commit_work_item(
    topo_id: int,
    commit_parts: tuple,
    total_unscanned: int,
    processed_count: int,
    ordinal_in_window: int,
    model_name: str,
    rubric_path: str,
    repo_label: str,
    db_path: str,
) -> Tuple[CommitWorkItem, dict]:
    """Scoring prep function upgraded to run structural scope heuristics on the main thread."""
    commit_sha = extract_commit_sha(commit_parts)
    subject = str(commit_parts[3]) if len(commit_parts) > 3 else ""
    diff = str(commit_parts[4]) if len(commit_parts) > 4 else ""

    # 1. Deterministic Scope Type Extraction
    commit_type = "commit"
    commit_scope = ""
    if subject.startswith("feat"):
        commit_type = "feat"
        commit_scope = subject.split("(")[1].split(")")[0] if "(" in subject else "core"
    elif subject.startswith("fix"):
        commit_type = "fix"
        commit_scope = subject.split("(")[1].split(")")[0] if "(" in subject else "core"
    elif subject.startswith("chore"):
        commit_type = "chore"
        commit_scope = subject.split("(")[1].split(")")[0] if "(" in subject else ""

    # 2. Additions and Deletions Counting
    additions = diff.count("\n+") - diff.count("\n+++")
    deletions = diff.count("\n-") - diff.count("\n---")

    # 3. Deterministic Scope Tags
    diff_lower = diff.lower()
    scope_tags = []
    if any(x in diff_lower for x in ("backend/parser.py", "backend/main.py", "dockerfile")):
        scope_tags.append("scripts")
    if ".json" in diff_lower or "config" in diff_lower:
        scope_tags.append("config")
    if "dashboard" in diff_lower or "index.html" in diff_lower:
        scope_tags.append("dashboard")
    if "readme" in diff_lower or ".md" in diff_lower:
        scope_tags.append("docs")
    if "metrics" in diff_lower:
        scope_tags.append("metrics")
    
    # Wait for the background thread to finish populating the Oracle
    _ORACLE_READY_EVENT.wait(timeout=60.0)

    arch_context, cause_tag, generation, snapshot_sig, role = _resolve_db_arch_context(
        db_path=db_path,
        repo_label=repo_label,
        topo_id=topo_id,
    )

    # 4. Pack pre-calculated heuristics into metadata for the presentation layer
    arch_meta = {
        "cause_tag": cause_tag,
        "generation": generation,
        "architecture_context": arch_context or "",
        "commit_sha": commit_sha,
        "topo_id": topo_id,
        "snapshot_sig": snapshot_sig,
        "role": role,
        "heuristics": {
            "type": commit_type,
            "scope": commit_scope,
            "tags": ", ".join(scope_tags) if scope_tags else "None",
            "additions": f"+{additions}",
            "deletions": f"-{deletions}"
        }
    }

    work_item = CommitWorkItem(
        topo_id=topo_id,
        commit_parts=commit_parts,
        total_unscanned=total_unscanned,
        processed_count=processed_count,
        ordinal_in_window=ordinal_in_window,
        model_name=model_name,
        rubric_path=rubric_path,
        arch_context=arch_context or "",
        arch_tree_signature=snapshot_sig,
        arch_gen=generation,
        arch_meta=arch_meta,
    )

    return work_item, arch_meta


def extract_commit_sha(commit_parts: tuple) -> str:
    return str(commit_parts[0]).strip()


def wait_for_oracle_sync(timeout: float = 120.0) -> bool:
    """Blocks until the background Oracle thread completes phase 2 initialization."""
    return _ORACLE_READY_EVENT.wait(timeout)
