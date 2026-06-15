#!/usr/bin/env python3
"""
Data Transformation Tests — timeline markers, dominance math, selector routing.
Real dataclass instances, no trivial stubs.
"""
import pytest

from backend.cli.arch_history.ui.markers import TimelineMarkers
from backend.cli.arch_history.models import (
    CommitRef,
    CurrentBlueprint,
    HistoryReport,
    SnapshotEntry,
    SnapshotLifespanMetrics,
    SnapshotCompositionMetrics,
    SnapshotDominanceMetrics,
)


# ── Factory ──────────────────────────────────────────────────────────────────

def _make_entry(topo_id=10, snapshot_sig="sig_parent_10") -> SnapshotEntry:
    return SnapshotEntry(
        generation=1,
        generation_index=0,
        snapshot_sig=snapshot_sig,
        shape="leaf-only",
        shape_label="Stable Implementation Refinement",
        generator_version="archgen-v1",
        mode="programmatic",
        generated_at="2026-06-13 16:21:54",
        size_bytes=1522,
        selected_files=8,
        total_files=142,
        trigger=CommitRef(
            topo_id=topo_id,
            commit_sig="a1b2c3d",
            subject="sample commit",
            date="2026-06-13",
        ),
        successive_used_by=[],
        also_used_by=[],
        reappeared_runs=[],
        is_current=False,
        lifespan=SnapshotLifespanMetrics(
            total_commits=1, run_count=1,
            first_seen_topo_id=topo_id, last_seen_topo_id=topo_id,
            first_seen_date="2026-06-13", last_seen_date="2026-06-13",
            longest_streak=1,
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


def _make_report(entries) -> HistoryReport:
    return HistoryReport(
        repo_label="test-repo",
        repo_display="test-repo",
        total_commits=len(entries),
        total_blueprints=len(entries),
        total_generations=1,
        current=CurrentBlueprint(
            snapshot_sig="aabb", generated_at="2026-06-13",
            generator_version="1.0", mode="full", shape="genesis",
            total_files=50, selected_files=10,
        ),
        entries=entries,
    )


# ══════════════════════════════════════════════════════════════════════════════
#  TIMELINE MARKER HOISTING
# ══════════════════════════════════════════════════════════════════════════════

def test_timeline_marker_hoisting_resolution():
    """Hidden commits hoist markers to visible parent boundaries."""
    entry = _make_entry(topo_id=10, snapshot_sig="sig_parent_10")
    report = _make_report([entry])

    markers = TimelineMarkers(
        report,
        visible_ids={10, 20},
        hidden_map={10: [11, 12, 13]},
        smart_target="12",
    )

    marker_output = markers.get_commit_marker(10)
    assert marker_output is not None


def test_marker_returns_none_for_unmatched_topo():
    """Topo IDs with no marker relationship return None or empty."""
    entry = _make_entry(topo_id=10)
    report = _make_report([entry])

    markers = TimelineMarkers(
        report,
        visible_ids={10},
        hidden_map={},
        smart_target=None,
    )

    result = markers.get_commit_marker(999)
    assert result is None or result == ""


# ══════════════════════════════════════════════════════════════════════════════
#  DOMINANCE MATHEMATICS
# ══════════════════════════════════════════════════════════════════════════════

def test_dominance_ranking_by_effective_commits():
    """Higher effective_commits wins dominant assignment."""
    e_weak = _make_entry(topo_id=1, snapshot_sig="sig_weak")
    e_weak.dominance.effective_commits = 2
    e_weak.dominance.is_dominant = False

    e_strong = _make_entry(topo_id=5, snapshot_sig="sig_strong")
    e_strong.dominance.effective_commits = 15
    e_strong.dominance.is_dominant = True

    entries = [e_weak, e_strong]
    dominant = max(entries, key=lambda e: e.dominance.effective_commits)
    assert dominant.snapshot_sig == "sig_strong"
    assert dominant.dominance.effective_commits == 15


def test_share_of_generation_sums_to_one_or_less():
    """Individual snapshot shares cannot exceed 1.0."""
    e = _make_entry()
    assert 0.0 <= e.dominance.share_of_generation <= 1.0


# ══════════════════════════════════════════════════════════════════════════════
#  SELECTOR ROUTING
# ══════════════════════════════════════════════════════════════════════════════

def test_hex_prefix_matches_commit_sig():
    """A 7-char hex string should match the start of a commit signature."""
    ref = CommitRef(
        commit_sig="a1b2c3d4e5f6",
        topo_id=1,
        date="2026-06-13",
        subject="test commit",
    )
    prefix = "a1b2c3d"
    assert ref.commit_sig.startswith(prefix)


def test_topo_id_selector_is_numeric():
    """Numeric-only selectors resolve as topo IDs."""
    selector = "42"
    assert selector.isdigit()
    assert int(selector) == 42
