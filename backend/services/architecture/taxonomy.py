from __future__ import annotations

# 1. Map raw pipeline tokens to our flat canonical keys
RAW_TO_CANONICAL = {
    "major:first-generation": "genesis",
    "major:dirs": "local-dir-shift",
    "major:file-count": "local-file-spike",
    "isolated-payload-spike": "local-file-spike",
    "major:selected-files": "critical-file-shift",
    "multi-dir:dirs": "global-dir-change",
    "multi-dir:coverage": "global-dir-change",
    "multi-dir:default": "fallback-shift",
    "multi-dirdefault": "fallback-shift",
    "leaf-only": "leaf-only",
    "major:head": "head",
    "major:detached-root": "detached-root",
}

# 2. SSOT: Single mapping for Label, Icon, and Magnitude
TAXONOMY_DEF = {
    "genesis": {"family": "genesis", "label": "Architecture Baseline Established", "icon": "🐣", "magnitude": "structural"},
    "local-dir-shift": {"family": "depth", "label": "Deep Local Directory Refactor", "icon": "🚧", "magnitude": "structural"},
    "local-file-spike": {"family": "depth", "label": "Isolated File Payload Spike", "icon": "🌋", "magnitude": "structural"},
    "critical-file-shift": {"family": "breadth", "label": "Critical Asset Tracking Realignment", "icon": "💎", "magnitude": "structural"},
    "global-dir-change": {"family": "breadth", "label": "Widespread Architectural Redesign", "icon": "🌐", "magnitude": "structural"},
    "fallback-shift": {"family": "breadth", "label": "Macro Wide-Area Baseline Shift", "icon": "🌊", "magnitude": "structural"},
    "leaf-only": {"family": "incremental", "label": "Stable Implementation Refinement", "icon": "🍃", "magnitude": "minor"},
    "head": {"family": "temporal", "label": "Current Architecture Head", "icon": "📍", "magnitude": "structural"},
    "detached-root": {"family": "genesis", "label": "Detached Root Branch Initialized", "icon": "🌱", "magnitude": "structural"}
}

# --- Backward Compatibility for taxonomy_sync.py and legacy imports ---
BOUNDARY_CAUSE_LABEL_MAP = {k: v["label"] for k, v in TAXONOMY_DEF.items()}
BOUNDARY_CAUSE_TAG_MAP = RAW_TO_CANONICAL
CANONICAL_TAXONOMY = TAXONOMY_DEF
SHAPE_ALIAS_MAP = RAW_TO_CANONICAL

def normalize_cause_tag(raw_shape: str) -> str:
    """Normalize raw arch_builder string to a canonical token."""
    s = (raw_shape or "").strip().lower()
    return RAW_TO_CANONICAL.get(s, s)

def get_shape_metadata(raw_shape: str) -> dict:
    """SSOT for all UI and pipeline queries."""
    canon = normalize_cause_tag(raw_shape)
    if canon in TAXONOMY_DEF:
        return TAXONOMY_DEF[canon]
    # Fallback for unrecognized LLM hallucinations: assume it's structural so we don't lose it
    return {"family": "incremental", "label": raw_shape or "Unknown Shift", "icon": "•", "magnitude": "structural"}

def get_boundary_magnitude(raw_shape: str) -> str:
    return get_shape_metadata(raw_shape).get("magnitude", "structural")

def get_boundary_cause_label(raw_shape: str) -> str:
    return get_shape_metadata(raw_shape).get("label", "Unknown Shift")
