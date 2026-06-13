#!/usr/bin/env python3
import json
import io
import contextlib
import pytest
from unittest.mock import MagicMock

from backend.cli.arch_history.ui.render import render_history_report

class StructuredDominance:
    def __init__(self, is_dominant=False, is_long_lived=False, is_short_lived=False):
        self.is_dominant = is_dominant
        self.is_long_lived = is_long_lived
        self.is_short_lived = is_short_lived

class StructuredLifespan:
    def __init__(self, total_commits=1, run_count=1, first_seen_date="May 25, '26", last_seen_date="May 27, '26"):
        self.total_commits = total_commits
        self.run_count = run_count
        self.first_seen_date = first_seen_date
        self.last_seen_date = last_seen_date

class StructuredTrigger:
    def __init__(self, topo_id=1, commit_sig="a1b2c3d", subject="sample commit message"):
        self.topo_id = topo_id
        self.commit_sig = commit_sig
        self.subject = subject
        self.date = "Jun 13, '26"

def create_rigid_entry(snapshot_sig, shape, shape_label, is_current=False, is_short_lived=False, gen_index=0, topo_id=1, subject="sample commit"):
    """Rigid Factory Helper: Simulates concrete, fully-populated SnapshotEntry specs to prevent silent mock passing"""
    entry = MagicMock()
    entry.snapshot_sig = snapshot_sig
    entry.shape = shape
    entry.shape_label = shape_label
    entry.is_current = is_current
    entry.generation = "1"
    entry.generation_index = gen_index
    entry.date = "Jun 13, '26"
    
    entry.dominance = StructuredDominance(is_dominant=True, is_short_lived=is_short_lived)
    entry.lifespan = StructuredLifespan()
    entry.trigger = StructuredTrigger(topo_id=topo_id, commit_sig="a1b2c3d", subject=subject)
    
    entry.successive_used_by = []
    entry.generator_version = "archgen-v1"
    entry.mode = "programmatic"
    entry.selected_files = 8
    entry.total_files = 142
    entry.size_bytes = 1522
    entry.generated_at = "2026-06-13 16:21:54"
    return entry

def build_rigid_report(total_commits=100, blueprint_count=3):
    """Generates deterministic global states containing formal mathematical generation summaries"""
    report = MagicMock()
    report.repo_display = "oliverpecha/commit-matrix"
    report.total_blueprints = blueprint_count
    report.total_commits = total_commits
    report.total_generations = 1
    report.repeated_treesig_count = 0
    
    summary = MagicMock()
    summary.cause_label = "Architecture Baseline Established"
    summary.snapshot_count = 1
    summary.span_commits = 1
    summary.repo_share = 0.02
    summary.incremental_count = 0
    summary.structural_count = 1
    summary.dominant_snapshot_sig = "a1b2c3d"
    summary.dominant_effective_commits = 1
    summary.dominant_share_of_generation = 1.0
    summary.repeated_treesig_count = 0
    summary.generation_distinct_commit_count = 1
    
    report.generation_summaries = {"1": summary}
    return report

# ==============================================================================
#  PRESENTATION LOOP & TAXONOMY VALIDATIONS
# ==============================================================================

def test_taxonomy_emoji_mapping():
    """Verify that flat taxonomy tags map to correct visual emojis without breaking"""
    report = build_rigid_report()
    e1 = create_rigid_entry("sig1", "major:first-generation", "Architecture Baseline Established", gen_index=0)
    e2 = create_rigid_entry("sig2", "isolated-payload-spike", "Isolated File Payload Spike", gen_index=1)
    report.entries = [e1, e2]

    f = io.StringIO()
    with contextlib.redirect_stdout(f):
        render_history_report(report, compact=False, show_operational=True)
    output = f.getvalue()

    assert "Architecture Baseline" in output
    assert "Isolated File Payload Spike" in output

def test_lifespan_badge_relocation_and_noise_suppression():
    """Ensure lifespan designations are appended to descriptive rows and muted on CURRENT branches"""
    report = build_rigid_report()
    e_hist = create_rigid_entry("sig_hist", "stable-refinement", "Stable Refinement", is_current=False, is_short_lived=True, gen_index=0)
    e_curr = create_rigid_entry("sig_curr", "stable-refinement", "Stable Refinement", is_current=True, is_short_lived=True, gen_index=1)
    report.entries = [e_hist, e_curr]

    f = io.StringIO()
    with contextlib.redirect_stdout(f):
        render_history_report(report, compact=False, show_operational=True)
    output = f.getvalue()

    assert "[short-lived]" in output
    assert "← [CURRENT]" in output

# ==============================================================================
#  FLAG COMBINATIONS & EDGE CASE COLLISIONS
# ==============================================================================

def test_compact_flag_layout_shift():
    """Verify that using the --compact flag suppresses verbose generation summaries"""
    report = build_rigid_report()
    report.entries = [create_rigid_entry("sig1", "stable-refinement", "Stable Refinement", gen_index=0)]

    f = io.StringIO()
    with contextlib.redirect_stdout(f):
        render_history_report(report, compact=True, show_operational=False)
    output = f.getvalue()

    assert "Generation Summary" not in output
    assert "Structural mix" not in output

def test_missing_topo_id_fallback():
    """Ensure detached git states without a topological ID degrade gracefully to ID #?"""
    report = build_rigid_report()
    e1 = create_rigid_entry("sig1", "stable-refinement", "Detached State", topo_id=None)
    report.entries = [e1]

    f = io.StringIO()
    with contextlib.redirect_stdout(f):
        render_history_report(report, compact=False, show_operational=True)
    output = f.getvalue()

    assert "ID #?" in output

def test_zero_state_graceful_exit():
    """Verify an empty repository ledger bypasses calculations without dividing by zero"""
    report = build_rigid_report(total_commits=0, blueprint_count=0)
    report.entries = [] 

    f = io.StringIO()
    with contextlib.redirect_stdout(f):
        render_history_report(report, compact=False, show_operational=True)
    output = f.getvalue()

    assert "(no snapshot files found)" in output

def test_hybrid_commit_truncation():
    """Verify multi-paragraph hybrid commit bodies do not leak down the terminal layout"""
    report = build_rigid_report()
    massive_prose = "feat(arch): modularize history engine\n\nThis refactor changes everything.\n- Point A"
    e1 = create_rigid_entry("sig1", "stable-refinement", "Stable Refinement", subject=massive_prose)
    report.entries = [e1]

    f = io.StringIO()
    with contextlib.redirect_stdout(f):
        render_history_report(report, compact=False, show_operational=False)
    output = f.getvalue()

    assert "This refactor changes everything" not in output

def test_json_empty_ledger_strictness():
    """Ensure zero-states output strict JSON structures, not plain text fallbacks"""
    report = {"repo_label": "commit-matrix", "total_commits": 0, "total_generations": 0, "entries": []}
    raw_json = json.dumps(report)
    parsed = json.loads(raw_json)
    
    assert isinstance(parsed["entries"], list)
    assert len(parsed["entries"]) == 0
    assert "no snapshot files found" not in raw_json

def test_flag_collision_compact_and_filtered_sparse_array():
    """Ensure the layout engine connects sparse, disconnected timelines when heavy filtering is applied"""
    report = build_rigid_report()
    e_first = create_rigid_entry("sig1", "major:first-generation", "Baseline", gen_index=0, topo_id=1)
    e_distant = create_rigid_entry("sig_distant", "stable-refinement", "Distant Reappearance", gen_index=16, topo_id=17)
    report.entries = [e_first, e_distant]

    f = io.StringIO()
    with contextlib.redirect_stdout(f):
        render_history_report(report, compact=True, show_operational=False)
    output = f.getvalue()

    assert "Baseline" in output
    assert "Distant Reappearance" in output
