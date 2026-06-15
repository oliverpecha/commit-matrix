from __future__ import annotations

# Maps raw pipeline change_shape tokens to our flat canonical keys
SHAPE_ALIAS_MAP = {
    "major:first-generation": "genesis",
    "major:dirs": "local-dir-shift",
    "major:file-count": "local-file-spike",
    "major:selected-files": "critical-file-shift",
    "multi-dir:dirs": "global-dir-change",
    "multi-dir:coverage": "global-dir-change",
    "multi-dir:default": "fallback-shift",
    "multi-dirdefault": "fallback-shift",
    "leaf-only": "leaf-only",
}

CANONICAL_TAXONOMY = {
    "genesis": {
        "family": "genesis",
        "label": "Architecture Baseline Established",
        "icon": "🐣"
    },
    "local-dir-shift": {
        "family": "depth",
        "label": "Deep Local Directory Refactor",
        "icon": "🚧"
    },
    "local-file-spike": {
        "family": "depth",
        "label": "Isolated File Payload Spike",
        "icon": "🌋"
    },
    "critical-file-shift": {
        "family": "breadth",
        "label": "Critical Asset Tracking Realignment",
        "icon": "📌"
    },
    "global-dir-change": {
        "family": "breadth",
        "label": "Widespread Architectural Redesign",
        "icon": "🌐"
    },
    "fallback-shift": {
        "family": "breadth",
        "label": "Macro Wide-Area Baseline Shift",
        "icon": "🌊"
    },
    "leaf-only": {
        "family": "incremental",
        "label": "Stable Implementation Refinement",
        "icon": "🍃"
    }
}

def get_shape_metadata(raw_shape: str) -> dict:
    s = (raw_shape or "").strip()
    # Handle lowercase/case-insensitive checks smoothly
    canonical_key = SHAPE_ALIAS_MAP.get(s, SHAPE_ALIAS_MAP.get(s.lower(), s))
    
    if canonical_key in CANONICAL_TAXONOMY:
        return CANONICAL_TAXONOMY[canonical_key]
        
    return {"family": "incremental", "label": raw_shape or "Unknown Shift", "icon": "•"}


# ─── Boundary Contract: Generation Cause Tags ────────────────────────────────
#
# Governs translation of raw internal cause classifications into stable
# external API tokens.  This is the single boundary that decouples
# internal git-engineering shift detection from the C1 JSON contract.
#
# Adding a new internal cause?
#   1. Add its raw token -> normalized key in BOUNDARY_CAUSE_TAG_MAP.
#   2. Add the normalized key -> human label in BOUNDARY_CAUSE_LABEL_MAP.
#   3. The serializer picks it up automatically.  No orchestrator changes.
# ─────────────────────────────────────────────────────────────────────────────

BOUNDARY_CAUSE_TAG_MAP: dict[str, str] = {
    # raw internal token           -> stable API machine token
    "major:first-generation":       "genesis",
    "major:dirs":                   "major_dirs",
    "major:file-count":             "major_file_count",
    "major:selected-files":         "major_selected_files",
    "multi-dir:dirs":               "multi_dir_dirs",
    "multi-dir:coverage":           "multi_dir_coverage",
    "multi-dir:default":            "multi_dir_default",
    "multi-dirdefault":             "multi_dir_default",
    "leaf-only":                    "leaf_only",
}

BOUNDARY_CAUSE_LABEL_MAP: dict[str, str] = {
    # normalized API token          -> human-readable label
    "genesis":                      "Architecture Baseline Established",
    "major_dirs":                   "Major Structural Reorganization of Root Directories",
    "major_file_count":             "Significant File Count Threshold Breach",
    "major_selected_files":         "Critical Tracked File Set Realignment",
    "multi_dir_dirs":               "Widespread Multi-Directory Restructuring",
    "multi_dir_coverage":           "Multi-Directory Coverage Expansion",
    "multi_dir_default":            "Broad Baseline Architectural Shift",
    "leaf_only":                    "Stable Leaf-Level Implementation Refinement",
}


def normalize_cause_tag(raw_tag: str) -> str:
    """Normalize an internal cause tag to a stable C1 API token.

    Known tags are mapped explicitly via BOUNDARY_CAUSE_TAG_MAP.
    Unknown tags are sanitized: lowercase, colons/hyphens/spaces
    replaced with underscores.
    """
    tag = (raw_tag or "").strip()
    normalized = BOUNDARY_CAUSE_TAG_MAP.get(tag)
    if normalized is None:
        normalized = BOUNDARY_CAUSE_TAG_MAP.get(tag.lower())
    if normalized is not None:
        return normalized
    return (
        tag.lower()
        .replace(":", "_")
        .replace("-", "_")
        .replace(" ", "_")
    ) or "unknown"


def get_boundary_cause_label(normalized_tag: str) -> str:
    """Look up the human-readable label for a normalized cause tag.

    Falls back to title-casing the token if no explicit mapping exists.
    """
    label = BOUNDARY_CAUSE_LABEL_MAP.get(normalized_tag)
    if label is not None:
        return label
    return normalized_tag.replace("_", " ").title()


# ─── Boundary Magnitude ──────────────────────────────────────────────────────
#
# Maps taxonomy family to a magnitude bucket.  This avoids numeric
# thresholds entirely — the family classification already encodes
# structural breadth vs depth vs incremental, so we reuse it.
# ─────────────────────────────────────────────────────────────────────────────

MAGNITUDE_BY_NORMALIZED_TAG: dict[str, str] = {
    # Directly map each normalized API token to its magnitude bucket.
    # This avoids fragile reverse-lookups through SHAPE_ALIAS_MAP.
    #
    # major:  broad structural changes affecting directory layout or multi-area scope
    # moderate: single-area depth changes (file count spikes)
    # minor:  leaf-only / incremental refinements
    "genesis":              "major",
    "major_dirs":           "major",
    "major_selected_files": "major",
    "multi_dir_dirs":       "major",
    "multi_dir_coverage":   "major",
    "multi_dir_default":    "major",
    "major_file_count":     "moderate",
    "leaf_only":            "minor",
}


def get_boundary_magnitude(normalized_cause_tag: str) -> str:
    """Derive boundary magnitude bucket from normalized cause tag.

    Direct lookup — no reverse-mapping through SHAPE_ALIAS_MAP.
    Falls back to "moderate" for unknown tags (safe middle ground).
    """
    return MAGNITUDE_BY_NORMALIZED_TAG.get(normalized_cause_tag, "moderate")

