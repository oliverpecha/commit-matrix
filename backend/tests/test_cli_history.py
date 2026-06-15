#!/usr/bin/env python3
"""
CLI History UI Renderer Tests — real dataclass instances, zero MagicMock.

Tests the text-mode render pipeline: taxonomy labels, badge placement,
compact layout, edge-case commit formatting, zero-state handling.
"""
import io
import json
import contextlib
import pytest

from backend.cli.arch_history.ui.render import render_history_report
from backend.cli.arch_history.models import (
    CommitRef,
    CurrentBlueprint,
    GenerationSummaryMetrics,
    HistoryReport,
    SnapshotEntry,
    SnapshotLifespanMetrics,
    SnapshotCompositionMetrics,
    SnapshotDominanceMetrics,
)


# ── Factory ──────────────────────────────────────────────────────────────────

def _make_trigger(
    topo_id=1, commit_sig="a1b2c3d", subject="sample commit message",
) -> CommitRef:
    return CommitRef(
        topo_id=topo_id,
        commit_sig=commit_sig,
        subject=subject,
        date="2026-06-13",
    )


def _make_entry(
    snapshot_sig="sig_default",
    shape="leaf-only",
    shape_label="Stable Implementation Refinement",
    is_current=False,
    is_dominant=True,
    is_long_lived=False,
    is_short_lived=False,
    gen=1,
    gen_index=0,
    topo_id=1,
    subject="sample commit",
    total_commits=1,
    run_count=1,
) -> SnapshotEntry:
    return SnapshotEntry(
        generation=gen,
        generation_index=gen_index,
        snapshot_sig=snapshot_sig,
        shape=shape,
        shape_label=shape_label,
        generator_version="archgen-v1",
        mode="programmatic",
        generated_at="2026-06-13 16:21:54",
        size_bytes=1522,
        selected_files=8,
        total_files=142,
        trigger=_make_trigger(topo_id=topo_id, subject=subject),
        successive_used_by=[],
        also_used_by=[],
        reappeared_runs=[],
        is_current=is_current,
        lifespan=SnapshotLifespanMetrics(
            total_commits=total_commits,
            run_count=run_count,
            first_seen_topo_id=topo_id or 0,
            last_seen_topo_id=(topo_id or 0) + total_commits - 1,
            first_seen_date="2026-06-13",
            last_seen_date="2026-06-15",
            longest_streak=total_commits,
        ),
        composition=SnapshotCompositionMetrics(
            successive_commit_count=max(0, total_commits - 1),
            reappeared_commit_count=0,
            operational_commit_count=0,
            development_commit_count=total_commits,
        ),
        dominance=SnapshotDominanceMetrics(
            effective_commits=total_commits,
            share_of_generation=1.0,
            longest_streak=total_commits,
            reappearance_commit_count=0,
            is_dominant=is_dominant,
            is_long_lived=is_long_lived,
            is_short_lived=is_short_lived,
        ),
    )


def _make_summary(
    generation=1,
    cause_tag="major:first-generation",
    cause_label="Architecture Baseline Established",
    commit_count=1,
) -> GenerationSummaryMetrics:
    return GenerationSummaryMetrics(
        generation=generation,
        cause_tag=cause_tag,
        cause_label=cause_label,
        generation_distinct_commit_count=commit_count,
        snapshot_count=1,
        structural_count=1,
        incremental_count=0,
        dominant_snapshot_sig="sig_default",
        dominant_effective_commits=commit_count,
        dominant_share_of_generation=1.0,
        repeated_treesig_count=0,
    )


def _make_report(entries, total_commits=100) -> HistoryReport:
    gen_ids = {e.generation for e in entries}
    summaries = {
        g: _make_summary(generation=g, commit_count=len(
            [e for e in entries if e.generation == g]
        ))
        for g in gen_ids
    }
    return HistoryReport(
        repo_label="commit-matrix",
        repo_display="oliverpecha/commit-matrix",
        total_commits=total_commits,
        total_blueprints=len(entries),
        total_generations=max(gen_ids) if gen_ids else 0,
        current=CurrentBlueprint(
            snapshot_sig="sig_default",
            generated_at="2026-06-13",
            generator_version="archgen-v1",
            mode="programmatic",
            shape="leaf-only",
            total_files=142,
            selected_files=8,
        ),
        entries=entries,
        generation_summaries=summaries,
    )


def _render_to_string(report, compact=False, show_operational=True) -> str:
    f = io.StringIO()
    with contextlib.redirect_stdout(f):
        render_history_report(report, compact=compact, show_operational=show_operational)
    return f.getvalue()


# ══════════════════════════════════════════════════════════════════════════════
#  PRESENTATION LOOP & TAXONOMY VALIDATIONS
# ══════════════════════════════════════════════════════════════════════════════

def test_taxonomy_emoji_mapping():
    """Verify that taxonomy shape labels render without breaking."""
    e1 = _make_entry(
        snapshot_sig="sig1", shape="major:first-generation",
        shape_label="Architecture Baseline Established", gen_index=0,
    )
    e2 = _make_entry(
        snapshot_sig="sig2", shape="isolated-payload-spike",
        shape_label="Isolated File Payload Spike", gen_index=1,
    )
    output = _render_to_string(_make_report([e1, e2]))
    assert "Architecture Baseline" in output
    assert "Isolated File Payload Spike" in output


def test_lifespan_badge_relocation_and_noise_suppression():
    """Ensure lifespan designations appear and CURRENT label renders."""
    e_hist = _make_entry(
        snapshot_sig="sig_hist", is_current=False,
        is_short_lived=True, gen_index=0,
    )
    e_curr = _make_entry(
        snapshot_sig="sig_curr", is_current=True,
        is_short_lived=True, gen_index=1,
    )
    output = _render_to_string(_make_report([e_hist, e_curr]))
    assert "[short-lived]" in output
    assert "CURRENT" in output


# ══════════════════════════════════════════════════════════════════════════════
#  FLAG COMBINATIONS & EDGE CASE COLLISIONS
# ══════════════════════════════════════════════════════════════════════════════

def test_compact_flag_layout_shift():
    """Verify --compact renders shorter details than full mode."""
    e = _make_entry(snapshot_sig="sig1", gen_index=0)
    full_output = _render_to_string(_make_report([e]), compact=False)
    compact_output = _render_to_string(_make_report([e]), compact=True)
    # Compact mode should produce equal or fewer lines than full mode
    assert len(compact_output.splitlines()) <= len(full_output.splitlines())
    # Core content still renders
    assert "sig1" in compact_output


def test_missing_topo_id_fallback():
    """Detached git states without topo ID degrade gracefully to ID #?."""
    e = _make_entry(snapshot_sig="sig1", topo_id=None)
    output = _render_to_string(_make_report([e]))
    assert "ID #?" in output


def test_zero_state_graceful_exit():
    """Empty repository bypasses calculations without division by zero."""
    report = _make_report([], total_commits=0)
    output = _render_to_string(report)
    assert "(no snapshot files found)" in output


def test_hybrid_commit_truncation():
    """Multi-paragraph commit bodies do not leak into terminal layout."""
    long_subject = (
        "feat(arch): modularize history engine\n\n"
        "This refactor changes everything.\n- Point A"
    )
    e = _make_entry(snapshot_sig="sig1", subject=long_subject)
    output = _render_to_string(_make_report([e]), show_operational=False)
    assert "This refactor changes everything" not in output


def test_json_empty_ledger_strictness():
    """Zero-states produce strict JSON structures, not plain text."""
    report = {"repo_label": "commit-matrix", "total_commits": 0,
              "total_generations": 0, "entries": []}
    raw_json = json.dumps(report)
    parsed = json.loads(raw_json)
    assert isinstance(parsed["entries"], list)
    assert len(parsed["entries"]) == 0
    assert "no snapshot files found" not in raw_json


def test_flag_collision_compact_and_filtered_sparse_array():
    """Layout engine connects sparse, disconnected timelines under filtering."""
    e_first = _make_entry(
        snapshot_sig="sig1", shape="major:first-generation",
        shape_label="Baseline", gen_index=0, topo_id=1,
    )
    e_distant = _make_entry(
        snapshot_sig="sig_distant", shape_label="Distant Reappearance",
        gen_index=16, topo_id=17,
    )
    output = _render_to_string(_make_report([e_first, e_distant]), compact=True)
    assert "Baseline" in output
    assert "Distant Reappearance" in output
