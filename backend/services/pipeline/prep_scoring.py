from __future__ import annotations
import sqlite3
import sys
from pathlib import Path
from typing import Tuple, Optional
from backend.services.pipeline.work_item import CommitWorkItem

def ensure_architecture_oracle(repo_path: str, db_path: str) -> None:
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

        for topo_id, commit_parts in commits_with_ids:
            commit_hash = str(commit_parts[0]).strip()
            date_str = str(commit_parts[1]) if len(commit_parts) > 1 else ""
            subject = str(commit_parts[2]) if len(commit_parts) > 2 else ""

            state, meta = tracker.resolve_for_commit(commit_hash, topo_id=topo_id)
            if not state or not getattr(state, "signature", None):
                continue

            with sqlite3.connect(db_path) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                run_row = conn.execute("SELECT run_id FROM architecture_runs ORDER BY run_id DESC LIMIT 1").fetchone()
                if not run_row:
                    continue
                run_id = run_row[0]

                role = "trigger" if (getattr(state, "advanced", False) or getattr(state, "change_shape", "") == "major:head") else "successive"
                conn.execute(
                    "INSERT INTO architecture_commits (run_id, snapshot_sig, topo_id, commit_sig, date, subject, role) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (run_id, state.signature, topo_id, commit_hash[:7], date_str, subject, role)
                )

                if getattr(state, "advanced", False) or getattr(state, "change_shape", "") == "major:head":
                    exists = conn.execute(
                        "SELECT id FROM architecture_boundaries WHERE run_id = ? AND boundary_commit_topo_id = ?",
                        (run_id, topo_id)
                    ).fetchone()
                    if not exists:
                        conn.execute(
                            "INSERT INTO architecture_boundaries (run_id, boundary_commit_sig, boundary_commit_topo_id, boundary_commit_date, boundary_commit_subject, cause_tag, magnitude) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (run_id, commit_hash[:7], topo_id, date_str, subject, state.change_shape, "structural")
                        )
                conn.commit()

        with sqlite3.connect(db_path) as conn:
            snap_count = conn.execute("SELECT COUNT(*) FROM architecture_snapshots").fetchone()[0]
            bound_count = conn.execute("SELECT COUNT(*) FROM architecture_boundaries").fetchone()[0]
            commit_count = conn.execute("SELECT COUNT(*) FROM architecture_commits").fetchone()[0]

        print("\n" + "─" * 71, flush=True)
        print("✅ Oracle Initialization Confirmed (Phase 2 Complete)", flush=True)
        print(f"    Snapshots Generated │ {snap_count}", flush=True)
        print(f"    Boundaries Mapped   │ {bound_count}", flush=True)
        print(f"    Commits Linked      │ {commit_count}", flush=True)
        print("─" * 71 + "\n", flush=True)

    except Exception as e:
        print(f"❌ FATAL [prep-scoring]: Oracle bootstrap failed: {e}", file=sys.stderr)
        sys.exit(1)


def _resolve_db_arch_context(
    db_path: str,
    repo_label: str,
    topo_id: int,
) -> Tuple[Optional[str], Optional[str], Optional[int], Optional[str]]:
    """Resolve architecture context for scoring by reading the flat commit mapping directly."""
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()

        # Direct lookups from the flat architecture tracking tables
        cur.execute(
            """
            SELECT ac.snapshot_sig, ab.cause_tag, ab.magnitude, ac.run_id
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
            cur.execute("SELECT snapshot_sig, 'Stable Implementation Refinement', 'incremental', run_id FROM architecture_commits WHERE run_id = (SELECT run_id FROM architecture_runs ORDER BY run_id DESC LIMIT 1) AND snapshot_sig IS NOT NULL ORDER BY topo_id ASC LIMIT 1")
            row = cur.fetchone()
            if not row:
                return None, None, None, None

        dominant_snapshot_sig, cause_tag, magnitude, run_id = row
        if not cause_tag:
            cause_tag = "Stable Implementation Refinement"


        cur.execute(
            """
            SELECT COUNT(DISTINCT boundary_commit_topo_id)
            FROM architecture_boundaries
            WHERE boundary_commit_topo_id <= ? AND run_id = (SELECT run_id FROM architecture_runs ORDER BY run_id DESC LIMIT 1) AND run_id = (SELECT run_id FROM architecture_runs ORDER BY run_id DESC LIMIT 1)
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

        return arch_context, cause_tag, generation, dominant_snapshot_sig
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
    """Scoring-only prep function using range reads."""
    commit_sha = extract_commit_sha(commit_parts)

    arch_context, cause_tag, generation, snapshot_sig = _resolve_db_arch_context(
        db_path=db_path,
        repo_label=repo_label,
        topo_id=topo_id,
    )

    arch_meta = {
        "cause_tag": cause_tag,
        "generation": generation,
        "architecture_context": arch_context or "",
        "commit_sha": commit_sha,
        "topo_id": topo_id,
        "snapshot_sig": snapshot_sig,
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
