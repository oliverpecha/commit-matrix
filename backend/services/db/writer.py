"""
CommitMatrix SQLite writer — boundary-anchored architecture persistence.

Input: serialized contract dict from serialize_history_report_to_contract().
Output: run_id.

Single run per repo. DELETEs old data and INSERTs fresh on every call.
Increments computation_version. Full relational — no JSON blobs.
"""
import csv
import hashlib
import sqlite3
import sys
from datetime import datetime, UTC
from pathlib import Path

from backend.services.db.schema import SCHEMA_SQL, SCHEMA_VERSION
from backend.services.db.taxonomy_sync import sync_taxonomy


def _blueprint_hash(snapshot_sig: str, repo_label: str) -> str | None:
    prefix = snapshot_sig[:16]
    md_path = Path("data") / repo_label / "past_blueprints" / f"arch-{prefix}.md"
    if md_path.exists():
        return hashlib.sha256(md_path.read_bytes()).hexdigest()
    return None


def _snapshot_path(snapshot_sig: str, repo_label: str) -> str:
    prefix = snapshot_sig[:16]
    return f"data/{repo_label}/past_blueprints/arch-{prefix}.md"


def _extract_commits(entry: dict, run_id: int) -> list[tuple]:
    rows = []
    sig = entry["snapshot_sig"]

    trigger = entry.get("trigger")
    if trigger:
        rows.append((
            run_id, sig, trigger.get("topo_id"), trigger.get("commit_sig"),
            trigger.get("date"), trigger.get("subject"), "trigger",
        ))

    for ref in entry.get("also_used_by", []):
        rows.append((
            run_id, sig, ref.get("topo_id"), ref.get("commit_sig"),
            ref.get("date"), ref.get("subject"), "also_used_by",
        ))

    for ref in entry.get("successive_used_by", []):
        rows.append((
            run_id, sig, ref.get("topo_id"), ref.get("commit_sig"),
            ref.get("date"), ref.get("subject"), "successive",
        ))

    for run_list in entry.get("reappeared_runs", []):
        for ref in run_list:
            rows.append((
                run_id, sig, ref.get("topo_id"), ref.get("commit_sig"),
                ref.get("date"), ref.get("subject"), "reappeared",
            ))

    return rows


def write_architecture_run(db_path: str, payload: dict) -> int:
    """Write a complete architecture history run to SQLite.

    Single run per repo. On subsequent calls for the same repo_label,
    old snapshot/commit/boundary rows are deleted and fresh data inserted.
    computation_version increments on every rewrite.
    """
    db = Path(db_path)
    db.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA_SQL)

    conn.execute(
        "INSERT OR REPLACE INTO schema_meta (key, value) VALUES (?, ?)",
        ("schema_version", str(SCHEMA_VERSION)),
    )

    sync_taxonomy(conn)

    repo_label = payload["repo_label"]
    now = datetime.now(UTC).isoformat()

    existing = conn.execute(
        "SELECT run_id FROM architecture_runs WHERE repo_label = ? LIMIT 1",
        (repo_label,),
    ).fetchone()

    if existing:
        run_id = existing[0]
        conn.execute("DELETE FROM architecture_snapshots WHERE run_id = ?", (run_id,))
        conn.execute("DELETE FROM architecture_commits WHERE run_id = ?", (run_id,))
        conn.execute("DELETE FROM architecture_boundaries WHERE run_id = ?", (run_id,))
        conn.execute(
            """UPDATE architecture_runs SET
                repo_display=?, generated_at=?, contract_version=?,
                computation_version = computation_version + 1,
                last_recomputed_at=?,
                total_commits=?, total_blueprints=?, total_generations=?
            WHERE run_id=?""",
            (
                payload.get("repo_display"), now,
                payload.get("contract_version"), now,
                payload.get("total_commits"),
                payload.get("total_blueprints"),
                payload.get("total_generations"),
                run_id,
            ),
        )
    else:
        cur = conn.execute(
            """INSERT INTO architecture_runs
            (repo_label, repo_display, generated_at, contract_version,
             computation_version, last_recomputed_at,
             total_commits, total_blueprints, total_generations)
            VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?)""",
            (
                repo_label, payload.get("repo_display"), now,
                payload.get("contract_version"), now,
                payload.get("total_commits"),
                payload.get("total_blueprints"),
                payload.get("total_generations"),
            ),
        )
        run_id = cur.lastrowid

    # Build boundary_commit_sig lookup from generation summaries
    gen_to_boundary_sig: dict[int, str] = {}
    for gen_key, summary in payload.get("generation_summaries", {}).items():
        boundary = summary.get("boundary")
        if boundary and boundary.get("commit"):
            gen_to_boundary_sig[int(gen_key)] = boundary["commit"]["commit_sig"]

    # Insert snapshots + commits
    all_inserted_topos: set[int] = set()

    for entry in payload.get("entries", []):
        flags = entry.get("flags", {})
        dom = entry.get("dominance_metrics") or {}
        life = entry.get("lifespan_metrics") or {}
        comp = entry.get("composition_metrics") or {}
        sig = entry["snapshot_sig"]
        gen = entry.get("generation")
        boundary_sig = gen_to_boundary_sig.get(gen)

        conn.execute(
            """INSERT INTO architecture_snapshots
            (run_id, boundary_commit_sig, snapshot_sig, snapshot_path,
             shape, shape_label, generator_version, generator_mode, generator_model,
             blueprint_grade, blueprint_hash, size_bytes, selected_files, total_files,
             is_current, is_dominant, lifespan_class,
             total_commits, run_count,
             first_seen_topo_id, last_seen_topo_id, first_seen_date, last_seen_date,
             longest_streak,
             successive_commit_count, reappeared_commit_count,
             operational_commit_count, development_commit_count,
             effective_commits, share_of_generation)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                run_id, boundary_sig, sig,
                _snapshot_path(sig, repo_label),
                entry.get("shape"), entry.get("shape_label"),
                entry.get("generator_version"), entry.get("mode"), None,
                "programmatic", _blueprint_hash(sig, repo_label),
                entry.get("size_bytes"), entry.get("selected_files"), entry.get("total_files"),
                flags.get("is_current", False), flags.get("is_dominant", False),
                flags.get("lifespan_class", "standard"),
                life.get("total_commits"), life.get("run_count"),
                life.get("first_seen_topo_id"), life.get("last_seen_topo_id"),
                life.get("first_seen_date"), life.get("last_seen_date"),
                life.get("longest_streak"),
                comp.get("successive_commit_count"), comp.get("reappeared_commit_count"),
                comp.get("operational_commit_count"), comp.get("development_commit_count"),
                dom.get("effective_commits"), dom.get("share_of_generation"),
            ),
        )

        commit_rows = _extract_commits(entry, run_id)
        conn.executemany(
            """INSERT INTO architecture_commits
            (run_id, snapshot_sig, topo_id, commit_sig, date, subject, role)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            commit_rows,
        )
        for row in commit_rows:
            if row[2] is not None:
                all_inserted_topos.add(row[2])

    # Insert boundaries
    for gen_key, summary in payload.get("generation_summaries", {}).items():
        boundary = summary.get("boundary") or {}
        commit = boundary.get("commit") or {}
        scope = boundary.get("scope") or {}
        displaced = boundary.get("displaced") or {}

        conn.execute(
            """INSERT INTO architecture_boundaries
            (run_id, boundary_commit_sig, boundary_commit_topo_id,
             boundary_commit_date, boundary_commit_subject,
             cause_tag, magnitude, scope_dirs, scope_file_count,
             snapshot_count, structural_count, incremental_count,
             dominant_snapshot_sig, dominant_effective_commits, dominant_share,
             repeated_treesig_count, distinct_commit_count,
             displaced_snapshot_sig, displaced_lifespan_class, displaced_was_dominant)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                run_id,
                commit.get("commit_sig"), commit.get("topo_id"),
                commit.get("date"), commit.get("subject"),
                summary.get("cause_tag"), boundary.get("magnitude"),
                ",".join(scope.get("top_level_dirs", [])),
                scope.get("file_count"),
                summary.get("snapshot_count"), summary.get("structural_count"),
                summary.get("incremental_count"),
                summary.get("dominant_snapshot_sig"),
                summary.get("dominant_effective_commits"),
                summary.get("dominant_share_of_generation"),
                summary.get("repeated_treesig_count"),
                summary.get("generation_distinct_commit_count"),
                displaced.get("snapshot_sig"), displaced.get("lifespan_class"),
                displaced.get("was_dominant"),
            ),
        )

    # Unmapped commits from ledger
    ledger_path = Path("data") / repo_label / f"{repo_label}_ledger_cirsd.csv"
    unmapped_count = 0
    if ledger_path.exists():
        with open(ledger_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                topo_str = (row.get("#") or row.get("\ufeff#") or "").strip()
                if not topo_str.isdigit():
                    continue
                topo = int(topo_str)
                if topo not in all_inserted_topos:
                    conn.execute(
                        """INSERT INTO architecture_commits
                        (run_id, snapshot_sig, topo_id, commit_sig, date, subject, role)
                        VALUES (?, NULL, ?, ?, ?, ?, 'unmapped')""",
                        (run_id, topo, row.get("Hash", ""), row.get("Date", ""), row.get("Subject", "")),
                    )
                    unmapped_count += 1

    if unmapped_count:
        print(
            f"[arch-history] {unmapped_count} commits unmapped (no matching snapshot)",
            file=sys.stderr, flush=True,
        )

    # Topo range + full scan detection
    topo_range = conn.execute(
        "SELECT MIN(topo_id), MAX(topo_id) FROM architecture_commits "
        "WHERE run_id = ? AND topo_id IS NOT NULL",
        (run_id,),
    ).fetchone()
    if topo_range and topo_range[0] is not None:
        is_full = topo_range[0] <= 1
        conn.execute(
            "UPDATE architecture_runs SET first_topo_id=?, last_topo_id=?, is_full_scan=? WHERE run_id=?",
            (topo_range[0], topo_range[1], is_full, run_id),
        )

    conn.commit()

    comp_ver = conn.execute(
        "SELECT computation_version FROM architecture_runs WHERE run_id = ?",
        (run_id,),
    ).fetchone()[0]
    print(
        f"[arch-history] Indexed run #{run_id} (v{comp_ver}) \u2192 {db_path}",
        file=sys.stderr, flush=True,
    )

    conn.close()
    return run_id


def write_snapshot_meta(repo_path: str, snapshot_sig: str, meta: dict) -> None:
    """Write a single snapshot's metadata to the DB.

    Called by arch_builder.py after each architecture generation.
    This populates the DB incrementally so the orchestrator's reader
    can find metadata without sidecars.
    """
    from backend.services.architecture.arch_storage import repo_id_from_path
    repo_label = repo_id_from_path(repo_path)
    db = Path("data") / repo_label / "commit_matrix.db"
    db.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA_SQL)

    conn.execute(
        "INSERT OR REPLACE INTO schema_meta (key, value) VALUES (?, ?)",
        ("schema_version", str(SCHEMA_VERSION)),
    )
    sync_taxonomy(conn)

    # Ensure run exists
    existing = conn.execute(
        "SELECT run_id FROM architecture_runs WHERE repo_label = ? LIMIT 1",
        (repo_label,),
    ).fetchone()

    if existing:
        run_id = existing[0]
    else:
        from datetime import datetime, UTC
        now = datetime.now(UTC).isoformat()
        cur = conn.execute(
            """INSERT INTO architecture_runs
            (repo_label, generated_at, contract_version, computation_version,
             last_recomputed_at)
            VALUES (?, ?, ?, 1, ?)""",
            (repo_label, now, "1.0", now),
        )
        run_id = cur.lastrowid

    prefix = snapshot_sig[:16]
    change_summary = meta.get("change_summary") or {}
    shape = change_summary.get("change_shape", "unknown")
    mode = change_summary.get("mode", "unknown")

    # Check if this snapshot already exists
    exists = conn.execute(
        "SELECT id FROM architecture_snapshots WHERE run_id = ? AND snapshot_sig = ?",
        (run_id, snapshot_sig),
    ).fetchone()

    if exists:
        # Update shape if it was classified
        conn.execute(
            "UPDATE architecture_snapshots SET shape = ?, generator_mode = ? WHERE id = ?",
            (shape, mode, exists[0]),
        )
    else:
        from backend.cli.arch_history.data.loader import human_shape_label
        conn.execute(
            """INSERT INTO architecture_snapshots
            (run_id, snapshot_sig, snapshot_path, shape, shape_label,
             generator_version, generator_mode, blueprint_grade, blueprint_hash,
             size_bytes, selected_files, total_files,
             is_current, is_dominant, lifespan_class)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run_id, snapshot_sig,
                f"data/{repo_label}/past_blueprints/arch-{prefix}.md",
                shape, human_shape_label(shape),
                meta.get("generator_version", "unknown"),
                mode, "programmatic",
                _blueprint_hash(snapshot_sig, repo_label),
                0, change_summary.get("selected_files_count", 0),
                change_summary.get("total_files", 0),
                False, False, "standard",
            ),
        )

    # Also insert the trigger commit if we have commit_sha
    commit_sha = meta.get("commit_sha", "")
    topo_id = meta.get("topo_id")
    if commit_sha:
        commit_exists = conn.execute(
            "SELECT id FROM architecture_commits WHERE run_id = ? AND commit_sig = ? AND snapshot_sig = ?",
            (run_id, commit_sha[:7], snapshot_sig),
        ).fetchone()
        if not commit_exists:
            conn.execute(
                """INSERT INTO architecture_commits
                (run_id, snapshot_sig, topo_id, commit_sig, role)
                VALUES (?, ?, ?, ?, 'trigger')""",
                (run_id, snapshot_sig, topo_id, commit_sha[:7]),
            )

    conn.commit()
    conn.close()


def write_state_pointer(repo_path: str, meta: dict) -> None:
    """Store the current blueprint state pointer in the DB.

    Called by arch_builder after each snapshot generation. This replaces
    the root-level _arch_blueprint.meta.json file. The next pipeline run
    reads this to determine change_shape by comparing against the previous state.
    """
    import json as _json
    from backend.services.architecture.arch_storage import repo_id_from_path
    repo_label = repo_id_from_path(repo_path)
    db = Path("data") / repo_label / "commit_matrix.db"
    db.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA_SQL)

    conn.execute(
        "INSERT OR REPLACE INTO schema_meta (key, value) VALUES (?, ?)",
        ("current_blueprint_meta", _json.dumps(meta)),
    )
    conn.commit()
    conn.close()


def read_state_pointer(repo_path: str) -> dict | None:
    """Read the current blueprint state pointer from the DB.

    Returns the meta dict stored by the last pipeline run, or None if
    no state pointer exists (cold start).
    """
    import json as _json
    from backend.services.architecture.arch_storage import repo_id_from_path
    repo_label = repo_id_from_path(repo_path)
    db = Path("data") / repo_label / "commit_matrix.db"

    if not db.exists():
        return None

    conn = sqlite3.connect(str(db))
    row = conn.execute(
        "SELECT value FROM schema_meta WHERE key = 'current_blueprint_meta'"
    ).fetchone()
    conn.close()

    if row and row[0]:
        return _json.loads(row[0])
    return None

