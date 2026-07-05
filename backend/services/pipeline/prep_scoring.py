from __future__ import annotations
import sqlite3
import sys
from pathlib import Path
from typing import Tuple, Optional
from backend.services.pipeline.work_item import CommitWorkItem

def ensure_architecture_oracle(repo_path: str, db_path: str) -> None:
    """
    Defensive bootstrapper for cold starts.
    If the database or boundaries are missing, this transparently generates 
    the .md blueprints and compiles the relational schema before scoring starts.
    """
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

    print("\n[prep-scoring] 🏗️  Cold start detected. Preparing architecture oracle...", flush=True)
    
    try:
        from backend.services.pipeline.repo_bootstrap import build_commit_queue
        from backend.utils.csv_writer import load_existing_hashes, ensure_csv_exists
        from backend.services.pipeline.pipeline_config import CSV_PATH
        from backend.services.architecture.arch_resolver import ArchitectureResolver
        
        existing_hashes = load_existing_hashes(CSV_PATH)
        ensure_csv_exists(CSV_PATH)
        bootstrap_res = build_commit_queue(repo_path, existing_hashes)
        commits_with_ids = bootstrap_res.get("commits_with_ids", [])

        tracker = ArchitectureResolver(repo_path=repo_path)
        for topo_id, commit_parts in commits_with_ids:
            tracker.resolve_for_commit(str(commit_parts[0]).strip(), topo_id=topo_id)

        print("[prep-scoring] 💾 Populating relational schema...", flush=True)
        import subprocess, os
        env = os.environ.copy()
        env["PYTHONPATH"] = "."
        subprocess.run(
            [sys.executable, "backend/cli/arch_history/main.py", "--repo", repo_path],
            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        print("[prep-scoring] ✅ Oracle synchronization complete.\n", flush=True)
    except Exception as e:
        print(f"⚠️ [prep-scoring warning] Oracle bootstrap failed: {e}", file=sys.stderr)


def _resolve_db_arch_context(
    db_path: str,
    repo_label: str,
    topo_id: int,
) -> Tuple[Optional[str], Optional[str], Optional[int]]:
    """Resolve architecture context for scoring using range boundaries."""
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()

        # Bind to active run_id context natively
        cur.execute(
            """
            SELECT cause_tag,
                   magnitude,
                   dominant_snapshot_sig
            FROM architecture_boundaries
            WHERE boundary_commit_topo_id <= ? AND run_id = 1
            ORDER BY boundary_commit_topo_id DESC
            LIMIT 1
            """,
            (topo_id,),
        )
        row = cur.fetchone()
        if not row:
            return None, None, None

        cause_tag, magnitude, dominant_snapshot_sig = row

        cur.execute(
            """
            SELECT COUNT(DISTINCT boundary_commit_topo_id)
            FROM architecture_boundaries
            WHERE boundary_commit_topo_id <= ?
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

        return arch_context, cause_tag, generation
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

    arch_context, cause_tag, generation = _resolve_db_arch_context(
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
        arch_tree_signature=None,
        arch_gen=generation,
        arch_meta=arch_meta,
    )

    return work_item, arch_meta


def extract_commit_sha(commit_parts: tuple) -> str:
    return str(commit_parts[0]).strip()
