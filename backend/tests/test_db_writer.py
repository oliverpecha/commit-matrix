"""
SQLite writer round-trip tests — boundary-anchored persistence.

Validates schema creation, taxonomy sync, snapshot/commit/boundary insertion,
single-run semantics, computation versioning, offset queries, and coverage.
"""
import json
import sqlite3
import pytest

from backend.services.db.writer import write_architecture_run
from backend.services.db.schema import SCHEMA_VERSION
from backend.cli.arch_history.orchestrator import serialize_history_report_to_contract
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


# ── Factory ──────────────────────────────────────────────────────────────────

def _make_dominance(
    is_dominant=False, is_long_lived=False, is_short_lived=False,
) -> SnapshotDominanceMetrics:
    return SnapshotDominanceMetrics(
        effective_commits=10, share_of_generation=0.5,
        longest_streak=5, reappearance_commit_count=2,
        is_dominant=is_dominant, is_long_lived=is_long_lived,
        is_short_lived=is_short_lived,
    )


def _make_entry(
    is_current=False, is_dominant=False, is_long_lived=False, is_short_lived=False,
    gen=1, sig="aabbccdd11223344", topo_id=1,
) -> SnapshotEntry:
    return SnapshotEntry(
        generation=gen, generation_index=0,
        snapshot_sig=sig, shape="genesis",
        shape_label="Architecture Baseline Established",
        generator_version="archgen-v1", mode="programmatic",
        generated_at="2026-06-15 12:00:00", size_bytes=4096,
        selected_files=10, total_files=50,
        trigger=CommitRef(
            commit_sig="ff00ff00", subject="initial commit",
            topo_id=topo_id, date="2026-06-15",
        ),
        is_current=is_current,
        lifespan=SnapshotLifespanMetrics(
            total_commits=10, run_count=1,
            first_seen_topo_id=topo_id, last_seen_topo_id=topo_id + 9,
            first_seen_date="2026-06-01", last_seen_date="2026-06-15",
            longest_streak=10,
        ),
        composition=SnapshotCompositionMetrics(
            successive_commit_count=8, reappeared_commit_count=0,
            operational_commit_count=2, development_commit_count=8,
        ),
        dominance=_make_dominance(
            is_dominant=is_dominant, is_long_lived=is_long_lived,
            is_short_lived=is_short_lived,
        ),
    )


def _make_payload(two_gens=False):
    e1 = _make_entry(is_dominant=True, is_short_lived=True, gen=1, sig="sig_gen1_aaa", topo_id=1)
    entries = [e1]

    s1 = GenerationSummaryMetrics(
        generation=1, cause_tag="major:first-generation",
        cause_label="internal", generation_distinct_commit_count=1,
        snapshot_count=1, structural_count=1, incremental_count=0,
        dominant_snapshot_sig="sig_gen1_aaa",
        dominant_effective_commits=10, dominant_share_of_generation=1.0,
        repeated_treesig_count=0,
    )
    summaries = {1: s1}

    if two_gens:
        e2 = _make_entry(
            is_dominant=True, is_long_lived=True,
            gen=2, sig="sig_gen2_bbb", topo_id=11,
        )
        entries.append(e2)
        s2 = GenerationSummaryMetrics(
            generation=2, cause_tag="major:file-count",
            cause_label="internal", generation_distinct_commit_count=5,
            snapshot_count=1, structural_count=1, incremental_count=0,
            dominant_snapshot_sig="sig_gen2_bbb",
            dominant_effective_commits=10, dominant_share_of_generation=1.0,
            repeated_treesig_count=0,
        )
        summaries[2] = s2

    report = HistoryReport(
        repo_label="test-repo", repo_display="test/repo",
        total_commits=20, total_blueprints=len(entries),
        total_generations=len(summaries),
        current=CurrentBlueprint(
            snapshot_sig="sig_gen1_aaa", generated_at="2026-06-15",
            generator_version="1.0", mode="full", shape="genesis",
            total_files=50, selected_files=10,
        ),
        entries=entries, generation_summaries=summaries,
    )
    return serialize_history_report_to_contract(report)


# ── Tests ────────────────────────────────────────────────────────────────────

class TestWriteBasics:

    def test_write_returns_run_id(self, tmp_path):
        db = str(tmp_path / "test.db")
        run_id = write_architecture_run(db, _make_payload())
        assert isinstance(run_id, int)
        assert run_id >= 1

    def test_run_row_matches_payload(self, tmp_path):
        payload = _make_payload()
        db = str(tmp_path / "test.db")
        run_id = write_architecture_run(db, payload)
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM architecture_runs WHERE run_id = ?", (run_id,)).fetchone()
        assert row["repo_label"] == "test-repo"
        assert row["contract_version"] == payload["contract_version"]
        assert row["total_commits"] == 20
        conn.close()

    def test_schema_version_stored(self, tmp_path):
        db = str(tmp_path / "test.db")
        write_architecture_run(db, _make_payload())
        conn = sqlite3.connect(db)
        ver = conn.execute("SELECT value FROM schema_meta WHERE key = 'schema_version'").fetchone()[0]
        assert ver == str(SCHEMA_VERSION)
        conn.close()

    def test_idempotent_schema(self, tmp_path):
        db = str(tmp_path / "test.db")
        write_architecture_run(db, _make_payload())
        write_architecture_run(db, _make_payload())  # should not error


class TestSingleRunSemantics:

    def test_single_run_per_repo(self, tmp_path):
        db = str(tmp_path / "test.db")
        r1 = write_architecture_run(db, _make_payload())
        r2 = write_architecture_run(db, _make_payload())
        assert r1 == r2

    def test_computation_version_increments(self, tmp_path):
        db = str(tmp_path / "test.db")
        write_architecture_run(db, _make_payload())
        write_architecture_run(db, _make_payload())
        conn = sqlite3.connect(db)
        ver = conn.execute("SELECT computation_version FROM architecture_runs").fetchone()[0]
        assert ver == 2
        conn.close()

    def test_recompute_clears_old_data(self, tmp_path):
        db = str(tmp_path / "test.db")
        write_architecture_run(db, _make_payload())
        write_architecture_run(db, _make_payload(two_gens=True))
        conn = sqlite3.connect(db)
        count = conn.execute("SELECT COUNT(*) FROM architecture_snapshots").fetchone()[0]
        assert count == 2  # fresh data, not accumulated (1 + 2)
        conn.close()

    def test_last_recomputed_at_updated(self, tmp_path):
        db = str(tmp_path / "test.db")
        write_architecture_run(db, _make_payload())
        conn = sqlite3.connect(db)
        ts1 = conn.execute("SELECT last_recomputed_at FROM architecture_runs").fetchone()[0]
        conn.close()
        import time; time.sleep(0.05)
        write_architecture_run(db, _make_payload())
        conn = sqlite3.connect(db)
        ts2 = conn.execute("SELECT last_recomputed_at FROM architecture_runs").fetchone()[0]
        conn.close()
        assert ts2 > ts1


class TestSnapshots:

    def test_snapshot_count_matches(self, tmp_path):
        payload = _make_payload(two_gens=True)
        db = str(tmp_path / "test.db")
        run_id = write_architecture_run(db, payload)
        conn = sqlite3.connect(db)
        count = conn.execute(
            "SELECT COUNT(*) FROM architecture_snapshots WHERE run_id = ?", (run_id,)
        ).fetchone()[0]
        assert count == len(payload["entries"])
        conn.close()

    def test_all_snapshot_columns_populated(self, tmp_path):
        db = str(tmp_path / "test.db")
        run_id = write_architecture_run(db, _make_payload())
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM architecture_snapshots WHERE run_id = ?", (run_id,)
        ).fetchone()
        assert row["snapshot_sig"] is not None
        assert row["shape"] is not None
        assert row["generator_version"] is not None
        assert row["lifespan_class"] is not None
        assert row["effective_commits"] is not None
        conn.close()

    def test_dominant_queryable(self, tmp_path):
        db = str(tmp_path / "test.db")
        run_id = write_architecture_run(db, _make_payload())
        conn = sqlite3.connect(db)
        rows = conn.execute(
            "SELECT snapshot_sig FROM architecture_snapshots WHERE run_id = ? AND is_dominant = 1",
            (run_id,)
        ).fetchall()
        assert len(rows) >= 1
        conn.close()

    def test_lifespan_class_queryable(self, tmp_path):
        db = str(tmp_path / "test.db")
        run_id = write_architecture_run(db, _make_payload())
        conn = sqlite3.connect(db)
        rows = conn.execute(
            "SELECT snapshot_sig FROM architecture_snapshots WHERE run_id = ? AND lifespan_class = 'short'",
            (run_id,)
        ).fetchall()
        assert len(rows) >= 1
        conn.close()

    def test_generator_fields_stored(self, tmp_path):
        db = str(tmp_path / "test.db")
        run_id = write_architecture_run(db, _make_payload())
        conn = sqlite3.connect(db)
        row = conn.execute(
            "SELECT generator_version, generator_mode FROM architecture_snapshots WHERE run_id = ?",
            (run_id,)
        ).fetchone()
        assert row[0] is not None  # generator_version
        conn.close()

    def test_blueprint_grade_stored(self, tmp_path):
        db = str(tmp_path / "test.db")
        run_id = write_architecture_run(db, _make_payload())
        conn = sqlite3.connect(db)
        row = conn.execute(
            "SELECT blueprint_grade FROM architecture_snapshots WHERE run_id = ?",
            (run_id,)
        ).fetchone()
        assert row[0] == "programmatic"
        conn.close()

    def test_snapshot_path_computed(self, tmp_path):
        db = str(tmp_path / "test.db")
        run_id = write_architecture_run(db, _make_payload())
        conn = sqlite3.connect(db)
        row = conn.execute(
            "SELECT snapshot_path FROM architecture_snapshots WHERE run_id = ?",
            (run_id,)
        ).fetchone()
        assert "arch-" in row[0]
        assert row[0].endswith(".md")
        conn.close()


class TestCommits:

    def test_commits_have_roles(self, tmp_path):
        db = str(tmp_path / "test.db")
        run_id = write_architecture_run(db, _make_payload())
        conn = sqlite3.connect(db)
        triggers = conn.execute(
            "SELECT COUNT(*) FROM architecture_commits WHERE run_id = ? AND role = 'trigger'",
            (run_id,)
        ).fetchone()[0]
        assert triggers >= 1
        conn.close()


class TestBoundaries:

    def test_boundaries_exist(self, tmp_path):
        db = str(tmp_path / "test.db")
        run_id = write_architecture_run(db, _make_payload())
        conn = sqlite3.connect(db)
        count = conn.execute(
            "SELECT COUNT(*) FROM architecture_boundaries WHERE run_id = ?",
            (run_id,)
        ).fetchone()[0]
        assert count >= 1
        conn.close()

    def test_boundary_magnitude_populated(self, tmp_path):
        payload = _make_payload(two_gens=True)
        db = str(tmp_path / "test.db")
        run_id = write_architecture_run(db, payload)
        conn = sqlite3.connect(db)
        rows = conn.execute(
            "SELECT magnitude FROM architecture_boundaries WHERE run_id = ? AND magnitude IS NOT NULL",
            (run_id,)
        ).fetchall()
        assert len(rows) >= 1
        conn.close()

    def test_boundary_displaced_chain(self, tmp_path):
        payload = _make_payload(two_gens=True)
        db = str(tmp_path / "test.db")
        run_id = write_architecture_run(db, payload)
        conn = sqlite3.connect(db)
        displaced = conn.execute(
            "SELECT displaced_snapshot_sig FROM architecture_boundaries "
            "WHERE run_id = ? AND displaced_snapshot_sig IS NOT NULL",
            (run_id,)
        ).fetchall()
        # Gen 2 should displace gen 1
        assert len(displaced) >= 1
        conn.close()

    def test_offset_query_works(self, tmp_path):
        payload = _make_payload(two_gens=True)
        db = str(tmp_path / "test.db")
        run_id = write_architecture_run(db, payload)
        conn = sqlite3.connect(db)
        rows = conn.execute("""
            SELECT ROW_NUMBER() OVER (ORDER BY boundary_commit_topo_id DESC) as offset,
                   boundary_commit_sig, cause_tag
            FROM architecture_boundaries WHERE run_id = ?
            ORDER BY boundary_commit_topo_id DESC
        """, (run_id,)).fetchall()
        assert len(rows) >= 1
        assert rows[0][0] == 1  # offset 1 = most recent
        conn.close()


class TestTaxonomy:

    def test_taxonomy_populated(self, tmp_path):
        db = str(tmp_path / "test.db")
        write_architecture_run(db, _make_payload())
        conn = sqlite3.connect(db)
        count = conn.execute("SELECT COUNT(*) FROM taxonomy").fetchone()[0]
        assert count >= 5
        conn.close()

    def test_taxonomy_joinable(self, tmp_path):
        payload = _make_payload(two_gens=True)
        db = str(tmp_path / "test.db")
        run_id = write_architecture_run(db, payload)
        conn = sqlite3.connect(db)
        rows = conn.execute("""
            SELECT b.cause_tag, t.label, t.magnitude
            FROM architecture_boundaries b
            JOIN taxonomy t ON b.cause_tag = t.tag
            WHERE b.run_id = ?
        """, (run_id,)).fetchall()
        assert len(rows) >= 1
        assert rows[0][1] is not None  # label
        assert rows[0][2] is not None  # magnitude
        conn.close()


class TestCoverage:

    def test_topo_range_computed(self, tmp_path):
        db = str(tmp_path / "test.db")
        run_id = write_architecture_run(db, _make_payload())
        conn = sqlite3.connect(db)
        row = conn.execute(
            "SELECT first_topo_id, last_topo_id FROM architecture_runs WHERE run_id = ?",
            (run_id,)
        ).fetchone()
        assert row[0] is not None
        assert row[1] is not None
        assert row[0] <= row[1]
        conn.close()

    def test_is_full_scan_derived(self, tmp_path):
        db = str(tmp_path / "test.db")
        run_id = write_architecture_run(db, _make_payload())
        conn = sqlite3.connect(db)
        row = conn.execute(
            "SELECT is_full_scan, first_topo_id FROM architecture_runs WHERE run_id = ?",
            (run_id,)
        ).fetchone()
        # topo_id=1 in test data, so is_full_scan should be true
        assert row[0] == 1  # SQLite stores bool as int
        assert row[1] <= 1
        conn.close()
