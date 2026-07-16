"""
Populate the taxonomy vocabulary table from taxonomy.py maps.
Called on every DB write to keep vocabulary current.
"""


def sync_taxonomy(conn) -> None:
    """INSERT OR REPLACE all known taxonomy entries from the TAXONOMY_DEF SSOT."""
    import sys
    import traceback
    try:
        from backend.services.architecture.taxonomy import TAXONOMY_DEF
        
        for canon_key, meta in TAXONOMY_DEF.items():
            label = meta.get("label", canon_key.replace("-", " ").title())
            magnitude = meta.get("magnitude", "moderate")
            family = meta.get("family", "incremental")
            
            conn.execute(
                "INSERT OR REPLACE INTO taxonomy (tag, label, magnitude, family) "
                "VALUES (?, ?, ?, ?)",
                (canon_key, label, magnitude, family),
            )
    except Exception as e:
        # Force a loud exit on stderr since background futures swallow exceptions natively
        print(f"\n[arch-oracle] ❌ FATAL ERROR in sync_taxonomy: {e}", file=sys.stderr, flush=True)
        traceback.print_exc(file=sys.stderr)
        raise
