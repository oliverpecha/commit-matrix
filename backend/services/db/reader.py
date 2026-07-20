"""
CommitMatrix SQLite reader — provides snapshot metadata for the orchestrator.

Replaces .meta.json sidecar reads. The orchestrator calls load_snapshot_meta_from_db()
which returns a dict in the same shape as the old sidecar JSON.
"""
import sqlite3
from pathlib import Path


import os
import glob

def resolve_db_path(repo_label: str | None = None) -> str:
    """Robust dynamic path resolution supporting environment targets and overrides."""
    target_repo = os.environ.get("TARGET_REPO")
    if target_repo:
        possible_path = os.path.join(target_repo, "data/db/commit_matrix.db")
        if os.path.exists(possible_path):
            return possible_path

    db_paths = glob.glob('data/*/db/commit_matrix.db')
    if db_paths:
        return db_paths[0]
        
    fallback_label = repo_label or os.environ.get('HOST_REPO_NAME', 'commit-matrix')
    return str(Path("data") / fallback_label / "db" / "commit_matrix.db")

# Retain alias mapping to prevent downstream breaking imports
_default_db_path = resolve_db_path


def load_all_snapshot_meta(repo_label: str, db_path: str | None = None) -> dict[str, dict]:
    """Load metadata for all snapshots from SQLite.

    Returns a dict keyed by snapshot_sig prefix (first 16 chars),
    with values matching the old .meta.json sidecar structure.
    """
    db = db_path or _default_db_path(repo_label)
    if not Path(db).exists():
        return {}

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row

    # Get run_id for this repo
    run_row = conn.execute(
        "SELECT run_id FROM architecture_runs WHERE repo_label = ? LIMIT 1",
        (repo_label,)
    ).fetchone()

    if not run_row:
        conn.close()
        return {}

    run_id = run_row["run_id"]

    # Load all snapshots
    rows = conn.execute("""
        SELECT snapshot_sig, shape, shape_label, generator_version, generator_mode,
               size_bytes, selected_files, total_files, is_current,
               first_seen_topo_id, total_commits
        FROM architecture_snapshots WHERE run_id = ?
    """, (run_id,)).fetchall()

    # Load boundary data for scope (top_level_dirs)
    boundaries = conn.execute("""
        SELECT boundary_commit_sig, boundary_commit_topo_id, scope_dirs, scope_file_count
        FROM architecture_boundaries WHERE run_id = ?
    """, (run_id,)).fetchall()

    # Load commits to find commit_sha for each snapshot trigger
    triggers = conn.execute("""
        SELECT snapshot_sig, commit_sig, topo_id
        FROM architecture_commits WHERE run_id = ? AND role = 'trigger'
    """, (run_id,)).fetchall()

    conn.close()

    # Build trigger lookup
    trigger_by_sig: dict[str, dict] = {}
    for t in triggers:
        trigger_by_sig[t["snapshot_sig"]] = {
            "commit_sha": t["commit_sig"],
            "topo_id": t["topo_id"],
        }

    # Build boundary scope lookup by boundary_commit_sig
    scope_by_boundary: dict[str, dict] = {}
    for b in boundaries:
        if b["boundary_commit_sig"]:
            scope_by_boundary[b["boundary_commit_sig"]] = {
                "top_level_dirs": b["scope_dirs"].split(",") if b["scope_dirs"] else [],
                "file_count": b["scope_file_count"],
                "topo_id": b["boundary_commit_topo_id"],
            }

    # Build result dict matching sidecar structure
    result: dict[str, dict] = {}
    for row in rows:
        sig = row["snapshot_sig"]
        prefix = sig[:16]
        trigger = trigger_by_sig.get(sig, {})

        # Reconstruct the sidecar-compatible dict
        meta = {
            "tree_signature": sig,
            "generator_version": row["generator_version"] or "unknown",
            "generated_at": "—",  # Not stored separately in DB; acceptable default
            "commit_sha": trigger.get("commit_sha", ""),
            "topo_id": trigger.get("topo_id"),
            "commit_index": trigger.get("topo_id"),
            "file_count": row["selected_files"],
            "top_level_dirs": [],
            "change_summary": {
                "change_shape": row["shape"] or "unknown",
                "change_shape_label": row["shape_label"],
                "mode": row["generator_mode"] or "unknown",
                "selected_files_count": row["selected_files"],
                "total_files": row["total_files"],
            },
            "shape_label": row["shape_label"],
        }

        result[prefix] = meta

    return result


def read_scan_range(repo_label: str, db_path: str | None = None) -> dict | None:
    """Read the current scan head/tail/previous_head from the DB."""
    db = db_path or _default_db_path(repo_label)
    if not Path(db).exists():
        return None

    conn = sqlite3.connect(db)
    row = conn.execute(
        "SELECT scan_head_topo, scan_tail_topo, previous_head_topo "
        "FROM architecture_runs WHERE repo_label = ?",
        (repo_label,),
    ).fetchone()
    conn.close()

    if not row:
        return None
    return {
        "scan_head_topo": row[0],
        "scan_tail_topo": row[1],
        "previous_head_topo": row[2],
    }


def read_vacuums(repo_label: str, db_path: str | None = None) -> list[dict]:
    """Read all unresolved vacuums for this repo."""
    db = db_path or _default_db_path(repo_label)
    if not Path(db).exists():
        return []

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row

    run_row = conn.execute(
        "SELECT run_id FROM architecture_runs WHERE repo_label = ? LIMIT 1",
        (repo_label,),
    ).fetchone()

    if not run_row:
        conn.close()
        return []

    rows = conn.execute(
        """SELECT vacuum_start_topo, vacuum_end_topo, commit_count, detected_at
        FROM scan_vacuums
        WHERE run_id = ? AND resolved_at IS NULL
        ORDER BY vacuum_start_topo""",
        (run_row["run_id"],),
    ).fetchall()
    conn.close()

    return [dict(row) for row in rows]



def get_structural_boundaries_for_stream(repo_label: str, db_path: str = None) -> dict:
    import sqlite3
    from pathlib import Path
    
    if not db_path:
        db_path = str(Path("data") / repo_label / "db" / "commit_matrix.db")
        try:
            __import__("os").makedirs(__import__("os").path.dirname(db_path), exist_ok=True)
        except Exception:
            pass
        
    schedule = {}
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            run_row = conn.execute("SELECT run_id FROM architecture_runs ORDER BY run_id DESC LIMIT 1").fetchone()
            if not run_row: return schedule
            
            rows = conn.execute("""
                SELECT boundary_commit_topo_id, cause_tag, magnitude, boundary_commit_sig, boundary_commit_date, boundary_commit_subject
                FROM architecture_boundaries
                WHERE run_id = ?
                ORDER BY boundary_commit_topo_id DESC
            """, (run_row["run_id"],)).fetchall()
            
            # Pure 1:1 physical mapping. No era collapsing. Every structural mutation gets its own generation banner.
            gen_id = 1
            for r in rows:
                topo_id = r["boundary_commit_topo_id"]
                schedule[topo_id] = {
                    "cause_tag": r["cause_tag"],
                    "magnitude": r["magnitude"],
                    "commit_sig": r["boundary_commit_sig"],
                    "subject": r["boundary_commit_subject"] or "",
                    "gen_id": gen_id
                }
                gen_id += 1
    except Exception as e:
        import os
        if str(os.environ.get("MATRIX_DEBUG", "false")).lower() in ("1", "true", "yes"):
            print(f"[arch-boundaries] ⚠️ Error reading raw schedule: {e}")
            
    return schedule



def _sqlite_is_macro(tag):
    if not tag: return 0
    t = str(tag).lower()
    if t in ('leaf-only', 'leaf_only'): return 0
    if t in ('major:head', 'head'): return 1
    try:
        from backend.services.architecture.taxonomy import normalize_cause_tag, get_boundary_magnitude
        return 1 if get_boundary_magnitude(normalize_cause_tag(t)) == 'major' else 0
    except:
        return 0

def get_commit_arch_context(repo_label: str, topo_id: int, db_path: str = None):
    from typing import Tuple, Optional
    db = db_path or resolve_db_path(repo_label)
    if not Path(db).exists():
        return None, None, None, None, None
        
    conn = sqlite3.connect(db)
    try:
        conn.create_function('IS_MACRO', 1, _sqlite_is_macro)
        cur = conn.cursor()
        cur.execute("SELECT ac.snapshot_sig, ab.cause_tag, ab.magnitude, ac.run_id, ac.role FROM architecture_commits ac LEFT JOIN architecture_boundaries ab ON ab.boundary_commit_topo_id = ac.topo_id AND ab.run_id = ac.run_id WHERE ac.topo_id = ? ORDER BY ac.run_id DESC LIMIT 1", (topo_id,))
        row = cur.fetchone()
        if not row or not row[0]:
            cur.execute("SELECT snapshot_sig, 'Stable Implementation Refinement', 'incremental', run_id, 'successive' FROM architecture_commits WHERE snapshot_sig IS NOT NULL ORDER BY topo_id DESC LIMIT 1")
            row = cur.fetchone()
            if not row: return None, None, None, None, None

        dominant_snapshot_sig, cause_tag, magnitude, run_id, role = row
        if not cause_tag: cause_tag = "Stable Implementation Refinement"

        cur.execute("SELECT COUNT(DISTINCT boundary_commit_topo_id) FROM architecture_boundaries WHERE boundary_commit_topo_id <= (SELECT MIN(boundary_commit_topo_id) FROM architecture_boundaries WHERE boundary_commit_topo_id >= ?) AND run_id = (SELECT run_id FROM architecture_runs ORDER BY run_id DESC LIMIT 1)", (topo_id,))
        gen_row = cur.fetchone()
        generation = gen_row[0] if gen_row and gen_row[0] is not None else None
        
        snapshot_path = None
        if dominant_snapshot_sig:
            cur.execute("SELECT snapshot_path FROM architecture_snapshots WHERE snapshot_sig = ? LIMIT 1", (dominant_snapshot_sig,))
            sp_row = cur.fetchone()
            if sp_row: snapshot_path = sp_row[0]

        arch_context = None
        if snapshot_path:
            md_path = Path(snapshot_path)
            candidate = md_path if md_path.is_absolute() or md_path.exists() else Path("data") / repo_label / "past_blueprints" / md_path.name
            if candidate.exists(): arch_context = candidate.read_text(encoding="utf-8")

        return arch_context, cause_tag, generation, dominant_snapshot_sig, role
    finally: 
        conn.close()
