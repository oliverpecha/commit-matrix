"""
Serialization Contract Tests — flags/badges derivation + taxonomy boundary.

Asserts that badges is always a deterministic, non-authoritative
projection of flags.  If this file breaks, the canonical-state +
derived-view contract has drifted.
"""
from __future__ import annotations

import pytest

from backend.cli.arch_history.orchestrator import (
    CONTRACT_VERSION,
    derive_badges,
    _build_snapshot_flags,
    _serialize_snapshot_entry,
    serialize_history_report_to_contract,
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
from backend.cli.arch_history.taxonomy import (
    normalize_cause_tag,
    get_boundary_cause_label,
    BOUNDARY_CAUSE_TAG_MAP,
    BOUNDARY_CAUSE_LABEL_MAP,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_dominance(
    *,
    is_dominant: bool = False,
    is_long_lived: bool = False,
    is_short_lived: bool = False,
) -> SnapshotDominanceMetrics:
    return SnapshotDominanceMetrics(
        effective_commits=10,
        share_of_generation=0.5,
        longest_streak=5,
        reappearance_commit_count=2,
        is_dominant=is_dominant,
        is_long_lived=is_long_lived,
        is_short_lived=is_short_lived,
    )


def _make_entry(
    *,
    is_current: bool = False,
    is_dominant: bool = False,
    is_long_lived: bool = False,
    is_short_lived: bool = False,
) -> SnapshotEntry:
    return SnapshotEntry(
        generation=1,
        generation_index=0,
        snapshot_sig="aabbccdd11223344",
        shape="genesis",
        generator_version="1.0",
        mode="full",
        generated_at="2026-06-15 12:00:00",
        size_bytes=4096,
        selected_files=10,
        total_files=50,
        trigger=CommitRef(
            commit_sig="ff00ff00",
            date="Jun 15, '26",
            subject="initial commit",
            topo_id=1,
            date_iso="2026-06-15",
        ),
        is_current=is_current,
        lifespan=SnapshotLifespanMetrics(
            total_commits=10, run_count=1,
            first_seen_topo_id=1, last_seen_topo_id=10,
            first_seen_date="2026-06-01", last_seen_date="2026-06-15",
            longest_streak=10,
        ),
        composition=SnapshotCompositionMetrics(
            successive_commit_count=8, reappeared_commit_count=0,
            operational_commit_count=2, development_commit_count=8,
        ),
        dominance=_make_dominance(
            is_dominant=is_dominant,
            is_long_lived=is_long_lived,
            is_short_lived=is_short_lived,
        ),
    )


# ── derive_badges ────────────────────────────────────────────────────────────

class TestDeriveBadges:

    def test_all_false_standard(self):
        flags = {"is_current": False, "is_dominant": False, "lifespan_class": "standard"}
        assert derive_badges(flags) == []

    def test_single_dominant(self):
        flags = {"is_current": False, "is_dominant": True, "lifespan_class": "standard"}
        assert derive_badges(flags) == ["dominant"]

    def test_long_lived(self):
        flags = {"is_current": False, "is_dominant": True, "lifespan_class": "long"}
        assert derive_badges(flags) == ["dominant", "long_lived"]

    def test_short_lived(self):
        flags = {"is_current": True, "is_dominant": True, "lifespan_class": "short"}
        assert derive_badges(flags) == ["current", "dominant", "short_lived"]

    def test_standard_no_lifespan_badge(self):
        flags = {"is_current": True, "is_dominant": False, "lifespan_class": "standard"}
        assert derive_badges(flags) == ["current"]

    def test_empty_dict(self):
        assert derive_badges({}) == []

    def test_missing_lifespan_defaults_no_badge(self):
        assert derive_badges({"is_dominant": True}) == ["dominant"]

    def test_order_booleans_before_lifespan(self):
        flags = {"is_current": True, "is_dominant": False, "lifespan_class": "short"}
        assert derive_badges(flags) == ["current", "short_lived"]


# ── Serialized snapshot invariant ────────────────────────────────────────────

class TestSnapshotContractInvariant:

    @pytest.mark.parametrize(
        "is_current, is_dominant, is_long_lived, is_short_lived, expected_lc",
        [
            (False, False, False, False, "standard"),
            (True,  False, False, False, "standard"),
            (False, True,  False, False, "standard"),
            (False, True,  True,  False, "long"),
            (False, False, False, True,  "short"),
            (True,  True,  True,  False, "long"),
            (True,  True,  False, True,  "short"),
        ],
    )
    def test_badges_equals_derive_badges_of_flags(
        self, is_current, is_dominant, is_long_lived, is_short_lived, expected_lc
    ):
        entry = _make_entry(
            is_current=is_current, is_dominant=is_dominant,
            is_long_lived=is_long_lived, is_short_lived=is_short_lived,
        )
        serialized = _serialize_snapshot_entry(entry)
        assert serialized["flags"]["lifespan_class"] == expected_lc
        assert serialized["badges"] == derive_badges(serialized["flags"])

    def test_flags_contains_expected_keys(self):
        entry = _make_entry()
        serialized = _serialize_snapshot_entry(entry)
        expected = {"is_current", "is_dominant", "lifespan_class"}
        assert set(serialized["flags"].keys()) == expected

    def test_no_separate_long_short_in_flags(self):
        entry = _make_entry(is_long_lived=True)
        serialized = _serialize_snapshot_entry(entry)
        assert "is_long_lived" not in serialized["flags"]
        assert "is_short_lived" not in serialized["flags"]

    def test_dominance_metrics_contains_only_unique_fields(self):
        """dominance_metrics must not duplicate fields from lifespan or composition."""
        entry = _make_entry(is_dominant=True, is_long_lived=True)
        serialized = _serialize_snapshot_entry(entry)
        dom = serialized["dominance_metrics"]
        # Booleans live in flags
        assert "is_dominant" not in dom
        assert "is_long_lived" not in dom
        assert "is_short_lived" not in dom
        # longest_streak lives in lifespan_metrics
        assert "longest_streak" not in dom
        # reappearance count lives in composition_metrics
        assert "reappearance_commit_count" not in dom
        # Only these two are unique to dominance
        assert set(dom.keys()) == {"effective_commits", "share_of_generation"}

    def test_contract_version_present(self):
        report = HistoryReport(
            repo_label="test-repo", repo_display="test-repo",
            total_commits=10, total_blueprints=1, total_generations=1,
            current=CurrentBlueprint(
                snapshot_sig="aabb", generated_at="2026-06-15",
                generator_version="1.0", mode="full", shape="genesis",
                total_files=50, selected_files=10,
            ),
            entries=[_make_entry(is_dominant=True)],
        )
        payload = serialize_history_report_to_contract(report)
        assert payload["contract_version"] == CONTRACT_VERSION
        assert payload["entries"][0]["badges"] == derive_badges(
            payload["entries"][0]["flags"]
        )


# ── Taxonomy boundary ────────────────────────────────────────────────────────

class TestTaxonomyBoundary:

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("major:dirs",             "major_dirs"),
            ("major:first-generation", "genesis"),
            ("multi-dir:dirs",         "multi_dir_dirs"),
            ("multi-dir:default",      "multi_dir_default"),
            ("multi-dirdefault",       "multi_dir_default"),
            ("leaf-only",              "leaf_only"),
            ("major:file-count",       "major_file_count"),
            ("major:selected-files",   "major_selected_files"),
            ("multi-dir:coverage",     "multi_dir_coverage"),
        ],
    )
    def test_known_tags_normalize(self, raw, expected):
        assert normalize_cause_tag(raw) == expected

    def test_unknown_tag_sanitized(self):
        result = normalize_cause_tag("experimental:new-thing")
        assert result == "experimental_new_thing"

    def test_case_insensitive(self):
        assert normalize_cause_tag("MAJOR:DIRS") == "major_dirs"

    def test_empty_and_whitespace(self):
        assert normalize_cause_tag("") == "unknown"
        assert normalize_cause_tag("   ") == "unknown"

    def test_every_tag_has_a_label(self):
        for token in set(BOUNDARY_CAUSE_TAG_MAP.values()):
            assert token in BOUNDARY_CAUSE_LABEL_MAP, (
                f"token {token!r} missing from BOUNDARY_CAUSE_LABEL_MAP"
            )

    def test_unknown_label_degrades_gracefully(self):
        assert get_boundary_cause_label("experimental_new") == "Experimental New"

    def test_known_label(self):
        assert get_boundary_cause_label("major_dirs") == (
            "Major Structural Reorganization of Root Directories"
        )


# ── Generation summaries serialization ───────────────────────────────────────

class TestGenerationSummaries:

    def test_keys_are_strings_and_cause_routed(self):
        summary = GenerationSummaryMetrics(
            generation=3, cause_tag="major:dirs",
            cause_label="(internal -- should be overridden)",
            generation_distinct_commit_count=12,
            snapshot_count=2, structural_count=1, incremental_count=1,
            dominant_snapshot_sig="aabb1122",
            dominant_effective_commits=10,
            dominant_share_of_generation=0.83,
            repeated_treesig_count=0,
        )
        report = HistoryReport(
            repo_label="test-repo", repo_display="test-repo",
            total_commits=20, total_blueprints=2, total_generations=3,
            current=CurrentBlueprint(
                snapshot_sig="aabb", generated_at="2026-06-15",
                generator_version="1.0", mode="full", shape="genesis",
                total_files=50, selected_files=10,
            ),
            entries=[_make_entry(is_dominant=True)],
            generation_summaries={3: summary},
        )
        payload = serialize_history_report_to_contract(report)
        summaries = payload["generation_summaries"]
        assert "3" in summaries
        assert 3 not in summaries
        assert summaries["3"]["cause_tag"] == "major_dirs"
        assert summaries["3"]["cause_label"] == (
            "Major Structural Reorganization of Root Directories"
        )


# ── --fields filtering ───────────────────────────────────────────────────────

class TestFieldsFiltering:
    """Verify --fields entry-level key filtering logic."""

    def _make_payload(self):
        report = HistoryReport(
            repo_label="test-repo", repo_display="test-repo",
            total_commits=10, total_blueprints=1, total_generations=1,
            current=CurrentBlueprint(
                snapshot_sig="aabb", generated_at="2026-06-15",
                generator_version="1.0", mode="full", shape="genesis",
                total_files=50, selected_files=10,
            ),
            entries=[_make_entry(is_dominant=True)],
        )
        return serialize_history_report_to_contract(report)

    def test_no_fields_returns_all_keys(self):
        payload = self._make_payload()
        entry = payload["entries"][0]
        assert "flags" in entry
        assert "badges" in entry
        assert "lifespan_metrics" in entry
        assert "dominance_metrics" in entry

    def test_fields_filters_entry_keys(self):
        payload = self._make_payload()
        allowed = {"flags", "badges", "generation", "snapshot_sig"}
        payload["entries"] = [
            {k: v for k, v in e.items() if k in allowed}
            for e in payload["entries"]
        ]
        entry = payload["entries"][0]
        assert set(entry.keys()) == allowed
        assert "lifespan_metrics" not in entry

    def test_structural_keys_always_present(self):
        payload = self._make_payload()
        allowed = {"flags"} | {"generation", "snapshot_sig"}
        payload["entries"] = [
            {k: v for k, v in e.items() if k in allowed}
            for e in payload["entries"]
        ]
        entry = payload["entries"][0]
        assert "generation" in entry
        assert "snapshot_sig" in entry

    def test_top_level_metadata_unaffected(self):
        payload = self._make_payload()
        allowed = {"flags", "generation", "snapshot_sig"}
        payload["entries"] = [
            {k: v for k, v in e.items() if k in allowed}
            for e in payload["entries"]
        ]
        assert "contract_version" in payload
        assert "repo_label" in payload
        assert "generation_summaries" in payload

