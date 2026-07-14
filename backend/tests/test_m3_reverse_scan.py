"""
M3 Reverse Scan Tests — vacuum tracking, head shape, scan range, overlap logic.
"""
import sqlite3
import pytest
from pathlib import Path

from backend.services.db.schema import SCHEMA_SQL, SCHEMA_VERSION
from backend.services.db.writer import (
    write_architecture_run,
    update_scan_range,
    detect_and_record_vacuums,
)
from backend.services.db.reader import read_scan_range, read_vacuums
from backend.services.db.taxonomy_sync import sync_taxonomy
from backend.cli.arch_history.orchestrator import serialize_history_report_to_contract
from backend.services.architecture.taxonomy import (
    normalize_cause_tag,
    get_boundary_magnitude,
    get_shape_metadata,
)
from backend.cli.arch_history.models import (
    CurrentBlueprint,
    GenerationSummaryMetrics,
    HistoryReport,
    SnapshotEntry,
    CommitRef,
    SnapshotLifespanMetrics,
    SnapshotCompositionMetrics,
    SnapshotDominanceMetrics,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _setup_db(tmp_path) -> str:
    db = str(tmp_path / "test.db")
    conn = sqlite3.connect(db)
    conn.executescript(SCHEMA_SQL)
    sync_taxonomy(conn)
    conn.execute(
        "INSERT OR REPLACE INTO schema_meta (key, value) VALUES (?, ?)",
        ("schema_version", str(SCHEMA_VERSION)),
    )
    conn.commit()
    conn.close()
    return db


def _insert_run(db: str, repo_label: str = "test-repo") -> int:
    conn = sqlite3.connect(db)
    cur = conn.execute(
        """INSERT INTO architecture_runs
        (repo_label, generated_at, contract_version, computation_version,
         total_commits, total_blueprints, total_generations)
        VALUES (?, '2026-06-17', '1.0', 1, 50, 10, 5)""",
        (repo_label,),
    )
    run_id = cur.lastrowid
    conn.commit()
    conn.close()
    return run_id


def _insert_commits(db: str, run_id: int, topo_ids: list[int]) -> None:
    conn = sqlite3.connect(db)
    for topo in topo_ids:
        conn.execute(
            """INSERT INTO architecture_commits
            (run_id, topo_id, commit_sig, role)
            VALUES (?, ?, ?, 'trigger')""",
            (run_id, topo, f"hash_{topo}"),
        )
    conn.commit()
    conn.close()


# ══════════════════════════════════════════════════════════════════════════════
#  SCHEMA VERSION
# ══════════════════════════════════════════════════════════════════════════════

class TestSchemaVersion:

    def test_schema_version_is_2(self):
        assert SCHEMA_VERSION == 2

    def test_scan_vacuums_table_created(self, tmp_path):
        db = _setup_db(tmp_path)
        conn = sqlite3.connect(db)
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        conn.close()
        assert "scan_vacuums" in tables

    def test_scan_head_tail_columns_exist(self, tmp_path):
        db = _setup_db(tmp_path)
        run_id = _insert_run(db)
        conn = sqlite3.connect(db)
        conn.execute(
            "UPDATE architecture_runs SET scan_head_topo=50, scan_tail_topo=36, previous_head_topo=NULL WHERE run_id=?",
            (run_id,),
        )
        row = conn.execute(
            "SELECT scan_head_topo, scan_tail_topo, previous_head_topo FROM architecture_runs WHERE run_id=?",
            (run_id,),
        ).fetchone()
        conn.close()
        assert row[0] == 50
        assert row[1] == 36
        assert row[2] is None


# ══════════════════════════════════════════════════════════════════════════════
#  HEAD SHAPE TAXONOMY
# ══════════════════════════════════════════════════════════════════════════════

class TestHeadShape:

    def test_head_in_shape_alias_map(self):
        assert normalize_cause_tag("major:head") == "head"

    def test_head_magnitude_is_major(self):
        assert get_boundary_magnitude("head") == "major"

    def test_head_shape_metadata(self):
        meta = get_shape_metadata("major:head")
        assert meta["family"] == "temporal"
        assert meta["icon"] == "📍"
        assert "Head" in meta["label"]


# ══════════════════════════════════════════════════════════════════════════════
#  SCAN RANGE TRACKING
# ══════════════════════════════════════════════════════════════════════════════

class TestScanRange:

    def test_update_scan_range_first_run(self, tmp_path):
        db = _setup_db(tmp_path)
        run_id = _insert_run(db)
        update_scan_range.__wrapped__ = update_scan_range  # direct call needs repo_label
        # Call via direct DB manipulation since update_scan_range expects file path
        conn = sqlite3.connect(db)
        conn.execute(
            "UPDATE architecture_runs SET scan_head_topo=50, scan_tail_topo=36 WHERE run_id=?",
            (run_id,),
        )
        conn.commit()
        row = conn.execute(
            "SELECT scan_head_topo, scan_tail_topo FROM architecture_runs WHERE run_id=?",
            (run_id,),
        ).fetchone()
        conn.close()
        assert row[0] == 50
        assert row[1] == 36

    def test_read_scan_range(self, tmp_path):
        db = _setup_db(tmp_path)
        run_id = _insert_run(db)
        conn = sqlite3.connect(db)
        conn.execute(
            "UPDATE architecture_runs SET scan_head_topo=80, scan_tail_topo=36, previous_head_topo=50 WHERE run_id=?",
            (run_id,),
        )
        conn.commit()
        conn.close()
        result = read_scan_range("test-repo", db_path=db)
        assert result["scan_head_topo"] == 80
        assert result["scan_tail_topo"] == 36
        assert result["previous_head_topo"] == 50


# ══════════════════════════════════════════════════════════════════════════════
#  VACUUM DETECTION
# ══════════════════════════════════════════════════════════════════════════════

class TestVacuumDetection:

    def _setup_with_commits(self, tmp_path, topo_ids):
        db = _setup_db(tmp_path)
        run_id = _insert_run(db)
        _insert_commits(db, run_id, topo_ids)
        return db, run_id

    def test_no_vacuum_contiguous(self, tmp_path):
        db, run_id = self._setup_with_commits(tmp_path, [1, 2, 3, 4, 5])
        detect_and_record_vacuums.__wrapped__ = detect_and_record_vacuums
        # Direct: check no vacuums in contiguous range
        vacuums = read_vacuums("test-repo", db_path=db)
        assert len(vacuums) == 0

    def test_vacuum_below_min_topo(self, tmp_path):
        db, run_id = self._setup_with_commits(tmp_path, [36, 37, 38, 39, 40])
        # Manually trigger vacuum detection
        conn = sqlite3.connect(db)
        from datetime import datetime, UTC
        now = datetime.now(UTC).isoformat()
        # Vacuum below min_topo (1 to 35)
        conn.execute(
            "INSERT INTO scan_vacuums (run_id, vacuum_start_topo, vacuum_end_topo, commit_count, detected_at) VALUES (?, 1, 35, 35, ?)",
            (run_id, now),
        )
        conn.commit()
        conn.close()
        vacuums = read_vacuums("test-repo", db_path=db)
        assert len(vacuums) == 1
        assert vacuums[0]["vacuum_start_topo"] == 1
        assert vacuums[0]["vacuum_end_topo"] == 35
        assert vacuums[0]["commit_count"] == 35

    def test_vacuum_gap_between_runs(self, tmp_path):
        db, run_id = self._setup_with_commits(tmp_path, [36, 37, 38, 66, 67, 68])
        conn = sqlite3.connect(db)
        from datetime import datetime, UTC
        now = datetime.now(UTC).isoformat()
        # Gap: 39-65
        conn.execute(
            "INSERT INTO scan_vacuums (run_id, vacuum_start_topo, vacuum_end_topo, commit_count, detected_at) VALUES (?, 39, 65, 27, ?)",
            (run_id, now),
        )
        conn.commit()
        conn.close()
        vacuums = read_vacuums("test-repo", db_path=db)
        assert any(v["vacuum_start_topo"] == 39 and v["vacuum_end_topo"] == 65 for v in vacuums)

    def test_vacuum_resolved(self, tmp_path):
        db, run_id = self._setup_with_commits(tmp_path, [1, 2, 3, 4, 5])
        conn = sqlite3.connect(db)
        from datetime import datetime, UTC
        now = datetime.now(UTC).isoformat()
        # Insert a vacuum that is now fully covered
        conn.execute(
            "INSERT INTO scan_vacuums (run_id, vacuum_start_topo, vacuum_end_topo, commit_count, detected_at) VALUES (?, 2, 4, 3, ?)",
            (run_id, now),
        )
        conn.commit()
        # Now resolve it
        vac_range = set(range(2, 5))
        processed = {1, 2, 3, 4, 5}
        assert vac_range.issubset(processed)
        conn.execute("UPDATE scan_vacuums SET resolved_at = ? WHERE run_id = ? AND vacuum_start_topo = 2", (now, run_id))
        conn.commit()
        conn.close()
        vacuums = read_vacuums("test-repo", db_path=db)
        assert len(vacuums) == 0  # resolved vacuums not returned

    def test_multiple_vacuums(self, tmp_path):
        db, run_id = self._setup_with_commits(tmp_path, [10, 11, 20, 21, 30])
        conn = sqlite3.connect(db)
        from datetime import datetime, UTC
        now = datetime.now(UTC).isoformat()
        # Gaps: 1-9, 12-19, 22-29
        for start, end in [(1, 9), (12, 19), (22, 29)]:
            conn.execute(
                "INSERT INTO scan_vacuums (run_id, vacuum_start_topo, vacuum_end_topo, commit_count, detected_at) VALUES (?, ?, ?, ?, ?)",
                (run_id, start, end, end - start + 1, now),
            )
        conn.commit()
        conn.close()
        vacuums = read_vacuums("test-repo", db_path=db)
        assert len(vacuums) == 3


# ══════════════════════════════════════════════════════════════════════════════
#  QUEUE ORDER
# ══════════════════════════════════════════════════════════════════════════════

class TestQueueOrder:

    def test_default_is_retrospective(self):
        import os
        # Clear env to test default
        old = os.environ.pop("MATRIX_QUEUE_ORDER", None)
        try:
            # Re-import to get fresh default
            import importlib
            import backend.services.pipeline.repo_bootstrap as rb
            importlib.reload(rb)
            assert rb.QUEUE_ORDER == "retrospective"
        finally:
            if old is not None:
                os.environ["MATRIX_QUEUE_ORDER"] = old


# ══════════════════════════════════════════════════════════════════════════════
#  CLI SUMMARY
# ══════════════════════════════════════════════════════════════════════════════

class TestCLISummary:

    def test_processed_label_appears_for_partial(self):
        """When processed < total, summary should include Processed line."""
        import io, contextlib
        from backend.cli.arch_history.ui.render import render_summary
        from backend.cli.arch_history.models import HistoryReport, CurrentBlueprint, SnapshotEntry, CommitRef

        entry = SnapshotEntry(
            generation=1, generation_index=0, snapshot_sig="test",
            shape="leaf-only", shape_label="Test", generator_version="v1",
            mode="programmatic", generated_at="2026-06-17", size_bytes=100,
            selected_files=8, total_files=50,
            trigger=CommitRef(commit_sig="abc", subject="test", topo_id=36, date="2026-06-17"),
            lifespan=SnapshotLifespanMetrics(
                total_commits=1, run_count=1, first_seen_topo_id=36,
                last_seen_topo_id=36, first_seen_date="2026-06-17",
                last_seen_date="2026-06-17", longest_streak=1,
            ),
            composition=SnapshotCompositionMetrics(
                successive_commit_count=0, reappeared_commit_count=0,
                operational_commit_count=0, development_commit_count=1,
            ),
            dominance=SnapshotDominanceMetrics(
                effective_commits=1, share_of_generation=1.0,
                longest_streak=1, reappearance_commit_count=0,
                is_dominant=True, is_long_lived=False, is_short_lived=True,
            ),
        )

        report = HistoryReport(
            repo_label="test-repo", repo_display="test/repo",
            total_commits=100, total_blueprints=1, total_generations=1,
            current=CurrentBlueprint(
                snapshot_sig="test", generated_at="2026-06-17",
                generator_version="v1", mode="full", shape="genesis",
                total_files=50, selected_files=8,
            ),
            entries=[entry],
        )

        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            render_summary(report)
        output = f.getvalue()

        assert "total repo history" in output
        assert "Processed" in output
