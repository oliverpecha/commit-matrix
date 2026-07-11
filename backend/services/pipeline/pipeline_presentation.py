from __future__ import annotations
import os
import sqlite3
from pathlib import Path
from backend.cli.arch_history.taxonomy import get_shape_metadata, normalize_cause_tag, get_boundary_magnitude

def _axis_bar(value: int, max_val: int = 3, width: int = 5) -> str:
    value = max(0, int(value or 0))
    filled = min(int(width * value / max_val), width)
    return chr(9608) * filled + chr(9617) * (width - filled)

def render_boundary_banner(boundary_data: dict, snapshot_sig: str) -> str:
    """
    Renders an architecture boundary banner using DB schedule data without re-evaluating taxonomy.
    """
    cause_tag = boundary_data.get("cause_tag", "")
    meta = get_shape_metadata(cause_tag)
    icon = meta.get("icon", "•")
    label = meta.get("label", cause_tag or "Architecture Shift")
    
    is_head = str(cause_tag).lower() in ("major:head", "head", "current architecture head")

    gen_id = int(boundary_data.get("gen_id", 1))
    offset = gen_id - 1
    
    magnitude = boundary_data.get("magnitude") or get_boundary_magnitude(cause_tag)
    commit_sig = boundary_data.get("commit_sig") or ""
    subject = (boundary_data.get("subject") or "")[:60]
    
    if is_head or offset == 0:
        title = "📍 Current Architecture Head"
    elif offset == 1:
        title = f"{icon}  1 Boundary back"
    else:
        title = f"{icon}  {offset} Boundaries back"

    return (
        "───────────────────────────────────────────────────────────────────────\n"
        f"{title}\n"
        f"    Cause      │ {label}\n"
        f"    Magnitude  │ {magnitude}\n"
        f"    Trigger    │ {commit_sig[:7]} - {subject}\n"
        f"    Blueprint  │ {snapshot_sig}\n"
        "───────────────────────────────────────────────────────────────────────\n"
    )


def report_sensor_mutation(commit_sha: str, old_sig: str, new_sig: str, raw_shape: str) -> None:
    """Triggered on physical mutations of the repository tree configuration."""
    if str(os.environ.get("MATRIX_DEBUG", "false")).strip().lower() in ("1", "true", "yes", "on"):
        print(f"[arch-tree] Signature Mutation {old_sig[:12]} ➔ {new_sig[:12]}", flush=True)
        print("", flush=True)
        print("", flush=True)

def render_commit_score_card(work_item: any, scores: dict, progress_data: dict) -> str:
    """Assembles a unified presentation layout card out of precalculated properties and scores."""
    h = work_item.arch_meta.get("heuristics", {})
    c, i, r, s, d = scores.get('C', 1), scores.get('I', 1), scores.get('R', 1), scores.get('S', 1), scores.get('D', 1)
    total_score = sum([c, i, r, s, d])
    
    bar = "█" * progress_data['filled'] + "░" * (16 - progress_data['filled'])
    
    meta = get_shape_metadata(work_item.arch_meta.get("cause_tag", ""))
    shape_display = f"{meta.get('icon', '•')} {meta.get('label')}" if meta else "unknown"

    ui_block = (
        "─────────────────────────────────────────────────────────────────────────\n"
        f"🧬 Commit #{work_item.topo_id} • {work_item.arch_meta['commit_sha'][:7]} __TOPO:{work_item.topo_id}__\n"
        "─────────────────────────────────────────────────────────────────────────\n"
        f"Date      │ {work_item.commit_parts[1]}\n"
        f"Subject   │ {work_item.commit_parts[3][:60]}...\n"
        f"Tier      │ {scores.get('tier', '🟢 ROUTINE')} (Score: {total_score})\n"
        f"Scope     │ {h.get('tags', 'None')}\n"
        f"Impact    │ C {_axis_bar(c)}  I {_axis_bar(i)}  R {_axis_bar(r)}  S {_axis_bar(s)}  D {_axis_bar(d)}\n"
        f"Snapshot  │ {(work_item.arch_tree_signature or 'N/A')[:24]} ({shape_display})\n"
        "─────────────────────────────────────────────────────────────────────────\n"
        f"🚀 [{bar}] {progress_data['pct']}% • {progress_data['remaining']} commits remaining\n"
    )
    return ui_block

def print_debug_boundary_table(repo_label: str, db_path: str) -> None:
    """Prints a tabular summary of architectural boundaries for debugging."""
    import os
    import sqlite3
    from backend.cli.arch_history.taxonomy import get_shape_metadata
    
    if str(os.environ.get("MATRIX_DEBUG", "false")).strip().lower() not in ("1", "true", "yes", "on"):
        return

    from pathlib import Path
    db = Path(db_path) if db_path else Path("data") / repo_label / "commit_matrix.db"
    if not db.exists(): return

    try:
        with sqlite3.connect(str(db)) as conn:
            conn.row_factory = sqlite3.Row
            run_row = conn.execute("SELECT run_id FROM architecture_runs ORDER BY run_id DESC LIMIT 1").fetchone()
            if not run_row: return
            
            rows = conn.execute("""
                SELECT b.boundary_commit_topo_id, b.boundary_commit_date, b.cause_tag, b.magnitude, 
                       b.boundary_commit_sig, c.snapshot_sig
                FROM architecture_boundaries b
                LEFT JOIN architecture_commits c ON b.run_id = c.run_id AND b.boundary_commit_topo_id = c.topo_id
                WHERE b.run_id = ?
                ORDER BY b.boundary_commit_topo_id DESC
            """, (run_row["run_id"],)).fetchall()
            
            if not rows: return

            print("\n[arch-boundaries] 🗺️  Architecture Boundary Map")
            print("[arch-boundaries] Era,Beginning (Head),Structural Trigger (Snapshot),Commit Sig,ID")
            
            valid_boundaries = []
            for r in rows:
                meta = get_shape_metadata(r["cause_tag"])
                if r["magnitude"] == "structural" or str(r["cause_tag"]).lower() in ("major:head", "head", "current architecture head"):
                    valid_boundaries.append((r, meta))

            for idx, (row, meta) in enumerate(valid_boundaries):
                era = "Current" if idx == 0 else f"{idx} Back"
                date_str = f'"{row["boundary_commit_date"]}"' if row["boundary_commit_date"] else '"Unknown"'
                
                snap_sig = row["snapshot_sig"] or "pending"
                icon = meta.get("icon", "•")
                snap_display = f"{snap_sig[:8]}... ({icon})"
                
                commit_sig = (row["boundary_commit_sig"] or "")[:7]
                topo_id = f"#{row['boundary_commit_topo_id']}"
                
                print(f"[arch-boundaries] {era},{date_str},{snap_display},{commit_sig},{topo_id}")
            print("", flush=True)
    except Exception as e:
        print(f"[arch-boundaries] ⚠️ Could not render boundary table: {e}", flush=True)
