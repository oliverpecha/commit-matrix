"""
CommitMatrix SQLite reader — provides snapshot metadata for the orchestrator.

Replaces .meta.json sidecar reads. The orchestrator calls load_snapshot_meta_from_db()
which returns a dict in the same shape as the old sidecar JSON.
"""
import sqlite3
from pathlib import Path


def _default_db_path(repo_label: str) -> str:
    return str(Path("data") / repo_label / "commit_matrix.db")


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

