"""
Populate the taxonomy vocabulary table from taxonomy.py maps.
Called on every DB write to keep vocabulary current.
"""


def sync_taxonomy(conn) -> None:
    """INSERT OR REPLACE all known taxonomy entries from taxonomy.py."""
    from backend.cli.arch_history.taxonomy import (
        BOUNDARY_CAUSE_TAG_MAP,
        BOUNDARY_CAUSE_LABEL_MAP,
        MAGNITUDE_BY_NORMALIZED_TAG,
        CANONICAL_TAXONOMY,
    )

    all_tags = set(BOUNDARY_CAUSE_TAG_MAP.values())
    for tag in all_tags:
        label = BOUNDARY_CAUSE_LABEL_MAP.get(tag, tag.replace("_", " ").title())
        magnitude = MAGNITUDE_BY_NORMALIZED_TAG.get(tag, "moderate")
        family = None
        for canon_key, meta in CANONICAL_TAXONOMY.items():
            if canon_key == tag:
                family = meta.get("family")
                break
        conn.execute(
            "INSERT OR REPLACE INTO taxonomy (tag, label, magnitude, family) "
            "VALUES (?, ?, ?, ?)",
            (tag, label, magnitude, family),
        )
