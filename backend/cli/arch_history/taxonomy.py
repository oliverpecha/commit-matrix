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
