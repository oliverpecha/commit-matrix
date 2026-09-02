import os
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

def _latest_run_id(conn, repo_label: str, rubric_name: str = None):
    rubric_name = rubric_name or __import__("os").environ.get("RUBRIC_NAME", "unknown")
    """Return latest run_id for a repo_label, or None if none exist."""
    row = conn.execute(
        "SELECT run_id FROM architecture_runs WHERE repo_label = ? ORDER BY run_id DESC LIMIT 1",
        (repo_label,),
    ).fetchone()
    return row[0] if row else None




def _blueprint_hash(snapshot_sig: str, repo_label: str) -> str | None:
    prefix = snapshot_sig[:16]
    md_path = (Path("data") / (os.environ.get("HOST_REPO_OWNER") or "local") / repo_label) / "past_blueprints" / f"arch_snapshot-{prefix}.md"
    if md_path.exists():
        return hashlib.sha256(md_path.read_bytes()).hexdigest()
    return None


def _snapshot_path(snapshot_sig: str, repo_label: str) -> str:
    prefix = snapshot_sig[:16]
    return f"arch_snapshot-{prefix}.md"


def _extract_commits(entry: dict, run_id: int) -> list[tuple]:
    rows = []
    sig = entry["snapshot_sig"]

    trigger = entry.get("trigger")
    if trigger:
        rows.append((
            run_id, sig, trigger.get("topo_id"), trigger.get("commit_sig"),
            trigger.get("date"), trigger.get("subject"), "trigger", None
        ))

    for ref in entry.get("also_used_by", []):
        rows.append((
            run_id, sig, ref.get("topo_id"), ref.get("commit_sig"),
            ref.get("date"), ref.get("subject"), "successive", None
        ))

    for ref in entry.get("successive_used_by", []):
        rows.append((
            run_id, sig, ref.get("topo_id"), ref.get("commit_sig"),
            ref.get("date"), ref.get("subject"), "successive", None
        ))

    for run_idx, run_list in enumerate(entry.get("reappeared_runs", [])):
        for ref in run_list:
            rows.append((
                run_id, sig, ref.get("topo_id"), ref.get("commit_sig"),
                ref.get("date"), ref.get("subject"), "reappeared", run_idx
            ))

    return rows


def write_architecture_run(db_path: str, payload: dict, rubric_name: str = None) -> int:
    rubric_name = rubric_name or __import__("os").environ.get("RUBRIC_NAME", "unknown")
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
            (repo_label, rubric_name, repo_display, generated_at, contract_version,
             computation_version, last_recomputed_at,
             total_commits, total_blueprints, total_generations)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?)""",
            (
                repo_label, rubric_name, payload.get("repo_display"), now,
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

    entries = payload.get("entries", [])
    if entries:
        sample = entries[0]
        print(
            "[arch-db] payload entries="
            f"{len(entries)} sample_keys={sorted(sample.keys())} "
            f"has_trigger={bool(sample.get('trigger'))} "
            f"also_used_by={len(sample.get('also_used_by', []))} "
            f"successive_used_by={len(sample.get('successive_used_by', []))} "
            f"reappeared_runs={len(sample.get('reappeared_runs', []))}",
            file=sys.stderr,
            flush=True,
        )
    else:
        if str(__import__("os").environ.get("MATRIX_DEBUG", "")).lower() in ("1", "true", "yes", "on"):
            print("[arch-db] payload entries=0", file=sys.stderr, flush=True)

    for entry in entries:
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
            (run_id, snapshot_sig, topo_id, commit_sig, date, subject, role, run_index)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            commit_rows,
        )
        for row in commit_rows:
            if row[2] is not None:
                all_inserted_topos.add(row[2])

    # 🌟 NATIVE BOUNDARY GENERATION: Bypassing CLI payload completely 🌟
    from backend.services.architecture.taxonomy import get_boundary_magnitude
    
    # Fetch all commits for this run ordered reverse-chronologically to isolate the true structural triggers
    all_commits = conn.execute("""
        SELECT c.topo_id, c.commit_sig, c.date, c.subject, s.shape, s.total_files, c.snapshot_sig
        FROM architecture_commits c
        JOIN architecture_snapshots s ON c.snapshot_sig = s.snapshot_sig AND c.run_id = s.run_id
        WHERE c.run_id = ? AND c.topo_id IS NOT NULL
        ORDER BY c.topo_id DESC
    """, (run_id,)).fetchall()

    if all_commits:
        head_topo = all_commits[0][0]
        
        last_sig = None
        for r in all_commits:
            topo, sig, date, subj, shape, file_count, snapshot_sig = r
            
            is_new_sig = (snapshot_sig != last_sig)
            if is_new_sig:
                shape_str = str(shape).lower()
                is_macro = ("major:" in shape_str or "multi-dir:" in shape_str or "isolated" in shape_str or "genesis" in shape_str or "critical" in shape_str)
                if is_macro or topo == head_topo or topo == 1:
                    conn.execute(
                        """INSERT INTO architecture_boundaries
                        (run_id, boundary_commit_sig, boundary_commit_topo_id,
                         boundary_commit_date, boundary_commit_subject,
                         cause_tag, magnitude, scope_file_count, snapshot_count, structural_count, incremental_count, distinct_commit_count, dominant_effective_commits, dominant_share)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            run_id, sig, topo, date, subj,
                            shape if topo != head_topo else "head", 
                            "structural", file_count,
                            1, 1, 0, 1, 1, 1.0
                        ),
                    )
            last_sig = snapshot_sig

    # Unmapped commits from ledger
    ledger_path = (Path("data") / (os.environ.get("HOST_REPO_OWNER") or "local") / repo_label) / "db" / f"{repo_label}_ledger_{rubric_name}.csv"
    unmapped_count = 0
    if ledger_path.exists():
        print(
            f"[arch-db] inserted snapshot-linked topo count={len(all_inserted_topos)} min={min(all_inserted_topos) if all_inserted_topos else None} max={max(all_inserted_topos) if all_inserted_topos else None}",
            file=sys.stderr,
            flush=True,
        )
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


def write_snapshot_meta(repo_path: str, snapshot_sig: str, meta: dict, rubric_name: str = None) -> None:
    rubric_name = rubric_name or __import__("os").environ.get("RUBRIC_NAME", "unknown")
    """Write a single snapshot's metadata to the DB.

    Called by arch_builder.py after each architecture generation.
    This populates the DB incrementally so the orchestrator's reader
    can find metadata without sidecars.
    """
    from backend.services.architecture.arch_storage import repo_id_from_path
    repo_label = repo_id_from_path(repo_path)
    db = (Path("data") / (os.environ.get("HOST_REPO_OWNER") or "local") / repo_label) / "db" / f"{repo_label}.db"
    try:
        db.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
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
            (repo_label, rubric_name, generated_at, contract_version, computation_version,
             last_recomputed_at)
            VALUES (?, ?, ?, ?, 1, ?)""",
            (repo_label, rubric_name, now, "1.0", now),
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
        from backend.services.architecture.taxonomy import get_boundary_cause_label, normalize_cause_tag
        # Update shape and shape_label together to prevent UI desynchronization
        conn.execute(
            "UPDATE architecture_snapshots SET shape = ?, shape_label = ?, generator_mode = ? WHERE id = ?",
            (shape, get_boundary_cause_label(normalize_cause_tag(shape)), mode, exists[0]),
        )
    else:
        from backend.services.architecture.taxonomy import get_boundary_cause_label, normalize_cause_tag
        conn.execute(
            """INSERT INTO architecture_snapshots
            (run_id, snapshot_sig, snapshot_path, shape, shape_label,
             generator_version, generator_mode, blueprint_grade, blueprint_hash,
             size_bytes, selected_files, total_files,
             is_current, is_dominant, lifespan_class)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run_id, snapshot_sig,
                f"arch_snapshot-{prefix}.md",
                shape, get_boundary_cause_label(normalize_cause_tag(shape)),
                meta.get("generator_version", "unknown"),
                mode, "programmatic",
                _blueprint_hash(snapshot_sig, repo_label),
                0, change_summary.get("selected_files_count", 0),
                change_summary.get("total_files", 0),
                False, False, "standard",
            ),
        )

    # Also insert the trigger commit if we have commit_sha
    # Note: [arch-graph] (write_commit_relationships) will write this row during pipeline teardown.
    # This fallback only fires when called outside a full pipeline run (e.g. arch_builder standalone).
    commit_sha = meta.get("commit_sha", "")
    topo_id = meta.get("topo_id")
    if commit_sha:
        commit_exists = conn.execute(
            "SELECT id FROM architecture_commits WHERE run_id = ? AND commit_sig = ? AND snapshot_sig = ?",
            (run_id, commit_sha[:7], snapshot_sig),
        ).fetchone()
        if not commit_exists:
            # Minimal fallback row: commit_sig + topo_id with no date/subject.
            # Primary [arch-graph] writer (write_commit_relationships) will overwrite
            # this row with full date/subject/role information during teardown.
            conn.execute(
                """INSERT INTO architecture_commits
                (run_id, snapshot_sig, topo_id, commit_sig, date, subject, role)
                VALUES (?, ?, ?, ?, ?, ?, 'trigger')""",
                (run_id, snapshot_sig, topo_id, commit_sha[:7], None, None),
            )

    conn.commit()
    conn.close()


def write_commit_relationships(db_path, run_id, snapshot_commits):
    # Write all commit->snapshot relationships accumulated during a pipeline scan.
    # snapshot_commits keys are (snapshot_sig, gen) tuples.
    # Each value is a list of dicts:
    #   {topo_id: int, commit_hash: str, reappeared: bool}
    # Returns count of rows inserted/updated.
    import sqlite3
    import sys as _sys
    written = 0
    with sqlite3.connect(db_path) as conn:
        conn.execute('PRAGMA journal_mode=WAL')
        # [arch-graph] owns the full commit graph — wipe all prior rows for this run
        # (write_snapshot_meta may have inserted partial trigger rows during scan)
        conn.execute(
            "DELETE FROM architecture_commits WHERE run_id=?",
            (run_id,),
        )
        _role_counts = {"trigger": 0, "successive": 0, "reappeared": 0}
        # Flatten and sort all commits from all buckets reverse-chronologically to safely mark triggers
        all_flat_commits = []
        for (snapshot_sig, gen), commits in snapshot_commits.items():
            for c in commits:
                c['_snapshot_sig'] = snapshot_sig
                all_flat_commits.append(c)
                
        all_flat_commits.sort(key=lambda x: x.get('topo_id') or -1, reverse=False)
        
        last_seen_sig = None
        for entry in all_flat_commits:
            snapshot_sig = entry['_snapshot_sig']
            topo_id = entry.get('topo_id')
            commit_sig = (entry.get('commit_hash') or '')[:7]
            is_reappeared = bool(entry.get('reappeared', False))
            
            if snapshot_sig != last_seen_sig:
                role = 'trigger'
                last_seen_sig = snapshot_sig
            elif is_reappeared:
                role = 'reappeared'
            else:
                role = 'successive'
                
            _role_counts[role] += 1
            commit_date = entry.get('date')
            commit_subject = entry.get('subject')

            existing = conn.execute(
                'SELECT id FROM architecture_commits '
                'WHERE run_id=? AND commit_sig=? AND snapshot_sig=?',
                (run_id, commit_sig, snapshot_sig),
            ).fetchone()
            if existing:
                conn.execute(
                    'UPDATE architecture_commits '
                    'SET role=?, topo_id=?, date=?, subject=? WHERE id=?',
                    (role, topo_id, commit_date, commit_subject, existing[0]),
                )
            else:
                conn.execute(
                    'INSERT INTO architecture_commits '
                    '(run_id, snapshot_sig, topo_id, commit_sig, date, subject, role) '
                    'VALUES (?,?,?,?,?,?,?)',
                    (run_id, snapshot_sig, topo_id, commit_sig, commit_date, commit_subject, role),
                )
            written += 1
        conn.commit()
        if False:  # Skip old inner loop block
            print(
                f"[arch-db] relationship bucket sig={snapshot_sig[:12]} gen={gen} size={len(ordered)}",
                file=_sys.stderr,
            )
            for idx, entry in enumerate(ordered):
                topo_id = entry.get('topo_id')
                commit_sig = (entry.get('commit_hash') or '')[:7]
                is_reappeared = bool(entry.get('reappeared', False))
                if idx == 0:
                    role = 'trigger'
                elif is_reappeared:
                    role = 'reappeared'
                else:
                    role = 'successive'
                _role_counts[role] += 1

                # Optional metadata: commit_date / commit_subject may be provided
                # by the pipeline; fall back to NULLs when absent.
                commit_date = entry.get('date')
                commit_subject = entry.get('subject')

                existing = conn.execute(
                    'SELECT id FROM architecture_commits '
                    'WHERE run_id=? AND commit_sig=? AND snapshot_sig=?',
                    (run_id, commit_sig, snapshot_sig),
                ).fetchone()
                if existing:
                    conn.execute(
                        'UPDATE architecture_commits '
                        'SET role=?, topo_id=?, date=?, subject=? WHERE id=?',
                        (role, topo_id, commit_date, commit_subject, existing[0]),
                    )
                else:
                    conn.execute(
                        'INSERT INTO architecture_commits '
                        '(run_id, snapshot_sig, topo_id, commit_sig, date, subject, role) '
                        'VALUES (?,?,?,?,?,?,?)',
                        (run_id, snapshot_sig, topo_id, commit_sig, commit_date, commit_subject, role),
                    )
                written += 1
        conn.commit()
        if str(__import__("os").environ.get("MATRIX_DEBUG", "")).lower() in ("1", "true", "yes", "on"):
            print(f"[arch-db] relationship role counts: {_role_counts}", file=_sys.stderr)
    return written


def update_generation_summary(db_path, run_id, gen_stats, snapshot_commits, gen_boundaries):
    # Update architecture_boundaries with real Phase 2B metrics keyed by boundary_commit_topo_id.
    import sqlite3
    with sqlite3.connect(db_path) as conn:
        for gen, stats in gen_stats.items():
            boundary_topo = gen_boundaries.get(gen)
            if boundary_topo is None:
                continue

            structural_count = stats.get("structural_count", 0)
            incremental_count = stats.get("incremental_count", 0)
            snapshot_count = len(stats.get("snapshot_sigs", set()))
            dominant_snapshot_sig = None
            dominant_count = -1

            for (sig, sig_gen), commits in snapshot_commits.items():
                if sig_gen != gen:
                    continue
                commit_count = len(commits)
                if commit_count > dominant_count:
                    dominant_count = commit_count
                    dominant_snapshot_sig = sig

            cur = conn.execute(
                """UPDATE architecture_boundaries
                   SET structural_count = ?,
                       incremental_count = ?,
                       snapshot_count = ?,
                       dominant_snapshot_sig = ?,
                       distinct_commit_count = ?
                   WHERE run_id = ? AND boundary_commit_topo_id = ?""",
                (
                    structural_count,
                    incremental_count,
                    snapshot_count,
                    dominant_snapshot_sig,
                    structural_count + incremental_count,
                    run_id,
                    boundary_topo,
                ),
            )
            import sys as _sys
            print(
                f"[arch] generation summary update gen={gen} topo={boundary_topo} rows={cur.rowcount}",
                file=_sys.stderr,
            )
        conn.commit()




def write_state_pointer(repo_path: str, meta: dict) -> None:
    """Store the current blueprint state pointer in the DB.

    Called by arch_builder after each snapshot generation. This replaces
    the root-level _arch_blueprint.meta.json file. The next pipeline run
    reads this to determine change_shape by comparing against the previous state.
    """
    import json as _json
    from backend.services.architecture.arch_storage import repo_id_from_path
    repo_label = repo_id_from_path(repo_path)
    db = (Path("data") / (os.environ.get("HOST_REPO_OWNER") or "local") / repo_label) / "db" / f"{repo_label}.db"
    try:
        db.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
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
    db = (Path("data") / (os.environ.get("HOST_REPO_OWNER") or "local") / repo_label) / "db" / f"{repo_label}.db"
    try:
        db.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

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


def update_scan_range(repo_label: str, scan_head: int, scan_tail: int, rubric_name: str = None) -> None:
    rubric_name = rubric_name or __import__("os").environ.get("RUBRIC_NAME", "unknown")
    """Update scan head/tail and track previous head for reclassification."""
    db = (Path("data") / (os.environ.get("HOST_REPO_OWNER") or "local") / repo_label) / "db" / f"{repo_label}.db"
    try:
        db.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    if not db.exists():
        return

    conn = sqlite3.connect(str(db))

    current = conn.execute(
        "SELECT scan_head_topo FROM architecture_runs WHERE repo_label = ?",
        (repo_label,),
    ).fetchone()

    previous_head = current[0] if current and current[0] else None

    # Expand tail to min of existing and new
    conn.execute("""
        UPDATE architecture_runs SET
            scan_head_topo = ?,
            scan_tail_topo = CASE
                WHEN scan_tail_topo IS NULL THEN ?
                WHEN ? < scan_tail_topo THEN ?
                ELSE scan_tail_topo
            END,
            previous_head_topo = ?
        WHERE repo_label = ?
    """, (scan_head, scan_tail, scan_tail, scan_tail, previous_head, repo_label))

    conn.commit()
    conn.close()


def detect_and_record_vacuums(repo_label: str, scan_head: int, scan_tail: int, rubric_name: str = None) -> None:
    rubric_name = rubric_name or __import__("os").environ.get("RUBRIC_NAME", "unknown")
    """Detect gaps in commit coverage and record as vacuums."""
    db = (Path("data") / (os.environ.get("HOST_REPO_OWNER") or "local") / repo_label) / "db" / f"{repo_label}.db"
    try:
        db.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    if not db.exists():
        return

    conn = sqlite3.connect(str(db))

    run_row = conn.execute(
        "SELECT run_id FROM architecture_runs WHERE repo_label = ?",
        (repo_label,),
    ).fetchone()
    if not run_row:
        conn.close()
        return
    run_id = run_row[0]

    processed = set(
        row[0] for row in conn.execute(
            "SELECT DISTINCT topo_id FROM architecture_commits "
            "WHERE run_id = ? AND topo_id IS NOT NULL",
            (run_id,),
        ).fetchall()
    )

    if not processed:
        conn.close()
        return

    min_topo = min(processed)
    max_topo = max(processed)

    # Gaps within the processed range
    all_expected = set(range(min_topo, max_topo + 1))
    missing = sorted(all_expected - processed)

    vacuums: list[tuple[int, int]] = []
    if missing:
        start = missing[0]
        prev = missing[0]
        for topo in missing[1:]:
            if topo == prev + 1:
                prev = topo
            else:
                vacuums.append((start, prev))
                start = topo
                prev = topo
        vacuums.append((start, prev))

    # Vacuum below min_topo if min_topo > 1
    if min_topo > 1:
        vacuums.append((1, min_topo - 1))

    from datetime import datetime, UTC
    now = datetime.now(UTC).isoformat()

    # Resolve existing vacuums that are now covered
    existing = conn.execute(
        "SELECT id, vacuum_start_topo, vacuum_end_topo FROM scan_vacuums "
        "WHERE run_id = ? AND resolved_at IS NULL",
        (run_id,),
    ).fetchall()

    for vac_id, vac_start, vac_end in existing:
        vac_range = set(range(vac_start, vac_end + 1))
        if vac_range.issubset(processed):
            conn.execute(
                "UPDATE scan_vacuums SET resolved_at = ? WHERE id = ?",
                (now, vac_id),
            )

    # Record new vacuums
    for vac_start, vac_end in vacuums:
        already = conn.execute(
            "SELECT id FROM scan_vacuums "
            "WHERE run_id = ? AND vacuum_start_topo = ? AND vacuum_end_topo = ? "
            "AND resolved_at IS NULL",
            (run_id, vac_start, vac_end),
        ).fetchone()

        if not already:
            conn.execute(
                """INSERT INTO scan_vacuums
                (run_id, vacuum_start_topo, vacuum_end_topo, commit_count, detected_at)
                VALUES (?, ?, ?, ?, ?)""",
                (run_id, vac_start, vac_end, vac_end - vac_start + 1, now),
            )

    conn.commit()
    conn.close()



def incremental_sync_commit_states(repo_label: str, db_path: str, resolved_states: list) -> None:
    db = Path(db_path)
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA journal_mode=WAL")
    
    _rubric = __import__("os").environ.get("RUBRIC_NAME", "unknown")
    run_row = conn.execute("SELECT run_id FROM architecture_runs WHERE repo_label = ? ORDER BY run_id DESC LIMIT 1", (repo_label,)).fetchone()
    if not run_row: 
        conn.close()
        return
    run_id = run_row[0]
    
    last_sig = None
    for item in resolved_states:
        current_sig = item["current_sig"]
        is_new_sig = (current_sig != last_sig)
        last_sig = current_sig
        
        is_trigger = (is_new_sig and not item.get("is_merge", False)) or item["is_head_fallback"]
        role = "trigger" if is_trigger else "successive"
        
        conn.execute(
            "UPDATE architecture_commits SET date = ?, subject = ?, role = ? WHERE run_id = ? AND topo_id = ?",
            (item["date_str"], item["subject"], role, run_id, item["topo_id"])
        )

        if is_trigger:
            if item["is_head_fallback"]:
                official_shape = "head"
                conn.execute("UPDATE architecture_snapshots SET shape = 'head', shape_label = 'Current Architecture Head' WHERE snapshot_sig = ?", (current_sig,))
            else:
                snap_row = conn.execute("SELECT shape FROM architecture_snapshots WHERE snapshot_sig = ?", (current_sig,)).fetchone()
                official_shape = snap_row[0] if snap_row else item.get("shape", "leaf-only")
                if official_shape == "head":
                    official_shape = "leaf-only"
            
            shape_str = str(official_shape).lower()
            is_macro = ("major:" in shape_str or "multi-dir:" in shape_str or "isolated" in shape_str or "genesis" in shape_str or "critical" in shape_str)
            
            if is_macro or item["is_head_fallback"]:
                exists = conn.execute("SELECT id FROM architecture_boundaries WHERE run_id = ? AND boundary_commit_topo_id = ?", (run_id, item["topo_id"])).fetchone()
                if not exists:
                    from backend.services.architecture.taxonomy import normalize_cause_tag
                    if item["is_head_fallback"]:
                        conn.execute("DELETE FROM architecture_boundaries WHERE run_id = ? AND cause_tag IN ('head', 'major:head', 'current architecture head', 'Stable Implementation Refinement', 'leaf-only')", (run_id,))
                    conn.execute(
                        "INSERT INTO architecture_boundaries (run_id, boundary_commit_sig, boundary_commit_topo_id, boundary_commit_date, boundary_commit_subject, cause_tag, magnitude) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (run_id, item["commit_hash"][:7], item["topo_id"], item["date_str"], item["subject"], normalize_cause_tag(official_shape), "structural")
                    )
    conn.commit()
    conn.close()
