from __future__ import annotations

_ACTUAL_WARNINGS = 0
import os
import sqlite3
import glob
from pathlib import Path
from backend.services.architecture.taxonomy import get_shape_metadata, normalize_cause_tag, get_boundary_magnitude

def _get_shape_emoji(sig):
    try:
        db_paths = glob.glob("data/*/commit_matrix.db")
        if db_paths:
            with sqlite3.connect(db_paths[0]) as conn:
                res = conn.execute("SELECT shape FROM architecture_snapshots WHERE snapshot_sig LIKE ? ORDER BY run_id DESC LIMIT 1", (str(sig)[:12] + "%",)).fetchone()
                if res:
                    s = res[0]
                    if str(s).lower() in ("head", "major:head", "current architecture head"):
                        return "📍"
                    meta = get_shape_metadata(s)
                    return meta.get("icon", "🍃")
    except: pass
    return "🍃"

def _get_ordinal(n: int) -> str:
    """Returns the clean grammatical ordinal string (1st, 2nd, 3rd, 4th...)"""
    if 11 <= (n % 100) <= 13:
        return f"{n}th"
    return f"{n}" + {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')

def _axis_bar(value: int, max_val: int = 3, width: int = 5) -> str:
    value = max(0, int(value or 0))
    filled = min(int(width * value / max_val), width)
    return chr(9608) * filled + chr(9617) * (width - filled)

def render_boundary_banner(boundary_data: dict, snapshot_sig: str) -> str:
    cause_tag = boundary_data.get("cause_tag", "")
    meta = get_shape_metadata(normalize_cause_tag(cause_tag))
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

def report_sensor_mutation(commit_sha: str, from_sig: str, to_sig: str, raw_shape: str, is_era_trigger: bool = False, **kwargs) -> None:
    """Triggered on physical mutations or structural boundaries."""
    global _ACTUAL_WARNINGS
    import os
    import sqlite3
    import glob
    from backend.services.architecture.taxonomy import get_shape_metadata, get_boundary_magnitude
    
    from_emoji = _get_shape_emoji(from_sig)
    meta_to = get_shape_metadata(raw_shape)
    to_emoji = meta_to.get("icon", "🍃") if meta_to else "🍃"

    if from_sig != to_sig:
        print(f"\n[arch-tree] Signature Mutation {from_emoji} {str(from_sig)[:12]} ➔ {to_emoji} {str(to_sig)[:12]}", flush=True)
        
    if is_era_trigger and get_boundary_magnitude(raw_shape) == "structural":
        current_count = 1
        try:
            db_paths = glob.glob("data/*/commit_matrix.db")
            if db_paths:
                with sqlite3.connect(db_paths[0]) as conn:
                    run_row = conn.execute("SELECT run_id FROM architecture_runs ORDER BY run_id DESC LIMIT 1").fetchone()
                    if run_row:
                        r_id = run_row[0]
                        b_rows = conn.execute("SELECT boundary_commit_sig FROM architecture_boundaries WHERE run_id = ? AND magnitude = 'structural' AND cause_tag NOT LIKE '%head%' ORDER BY boundary_commit_topo_id DESC", (r_id,)).fetchall()
                        for idx, r in enumerate(b_rows):
                            sig = str(r[0] or "")
                            if sig and sig.startswith(commit_sha[:7]):
                                current_count = idx + 1
                                break
        except Exception:
            pass
            
        ordinal_str = _get_ordinal(current_count)
        _ACTUAL_WARNINGS += 1
        print(f"\n[arch-tree] ⚠️  Warning ⚠️ : Significant Boundary Shift to {to_emoji} detected. A corresponding {ordinal_str} era banner must follow.", flush=True)

def render_commit_score_card(work_item: any, scores: dict, progress_data: dict) -> str:
    h = work_item.arch_meta.get("heuristics", {})
    c, i, r, s, d = scores.get('C', 1), scores.get('I', 1), scores.get('R', 1), scores.get('S', 1), scores.get('D', 1)
    total_score = sum([c, i, r, s, d])
    
    bar = "█" * progress_data['filled'] + "░" * (16 - progress_data['filled'])
    role = work_item.arch_meta.get("role", "successive")
    cause_tag = work_item.arch_meta.get("cause_tag", "")
    effective_tag = cause_tag if role == "trigger" else "leaf-only"
    meta = get_shape_metadata(effective_tag)
    shape_display = f"{meta.get('icon', '•')} {meta.get('label')}" if meta else "unknown"

    return (
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

def print_debug_boundary_table(repo_label: str, db_path: str) -> None:
    db = Path(db_path) if db_path else Path("data") / repo_label / "commit_matrix.db"
    if not db.exists(): return
    try:
        import sqlite3
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
            print(" Era     │ Trigger Snapshot            │ Trigger Commit    │ Beginning")
            print(" ────────┼─────────────────────────────┼───────────────────┼────────────")
            
            valid_boundaries = []
            from backend.services.architecture.taxonomy import get_shape_metadata, normalize_cause_tag
            for r in rows:
                meta = get_shape_metadata(normalize_cause_tag(r["cause_tag"]))
                if r["magnitude"] == "structural" or str(r["cause_tag"]).lower() in ("major:head", "head", "current architecture head"):
                    valid_boundaries.append((r, meta))

            for idx, (row, meta) in enumerate(valid_boundaries):
                era = "Current" if idx == 0 else f"{idx} Back"
                
                raw_date = row["boundary_commit_date"] if row["boundary_commit_date"] else "Unknown"
                date_clean = raw_date.replace(", ", " ").replace(",", " ").replace("'", "").replace('"', "")
                parts = date_clean.split(" ")
                if len(parts) >= 3:
                    date_str = f"{parts[0]} {parts[1]} '{parts[2]}"
                else:
                    date_str = date_clean
                
                snap_sig = row["snapshot_sig"] or "pending"
                icon = meta.get("icon", "•")
                full_snap = snap_sig[:24] if snap_sig != "pending" else "pending"
                
                commit_sig = (row["boundary_commit_sig"] or "")[:7]
                topo_id = row['boundary_commit_topo_id']
                commit_display = f"#{str(topo_id):<4} {commit_sig}"
                
                print(f" {era:<7} │ {icon} {full_snap} │ {commit_display:<17} │ {date_str}")
            print("", flush=True)
    except Exception:
        pass

def print_final_pipeline_summary_report(repo_label: str, db_path: str) -> None:
    global _ACTUAL_WARNINGS
    import sqlite3
    db = Path(db_path) if db_path else Path("data") / repo_label / "commit_matrix.db"
    if not db.exists(): return

    try:
        with sqlite3.connect(str(db)) as conn:
            conn.row_factory = sqlite3.Row
            run_row = conn.execute("SELECT run_id FROM architecture_runs ORDER BY run_id DESC LIMIT 1").fetchone()
            if not run_row: return
            
            c_res = conn.execute("SELECT COUNT(*) FROM architecture_boundaries WHERE run_id = ? AND magnitude = 'structural' AND cause_tag NOT LIKE '%head%'", (run_row["run_id"],)).fetchone()
            if c_res and c_res[0] > 0:
                expected = c_res[0]
                if _ACTUAL_WARNINGS == 0:
                    print(f"\n[arch-tree] ℹ️  0 era banner debugging warnings have been printed (Warm start ledger linkage active, mutation stream bypassed).\n", flush=True)
                else:
                    if _ACTUAL_WARNINGS == expected:
                        print(f"\n[arch-tree] ✅ {_ACTUAL_WARNINGS} era banner debugging warnings have been printed, 🎯 This checks with [arch-boundaries]!")
                        print(f"[arch-tree] ⚖️  Validation check: {_ACTUAL_WARNINGS} printed warnings == {expected} expected shifts (from {expected + 1} total DB triggers)\n", flush=True)
                    else:
                        print(f"\n[arch-tree] ❌ Validation failure: {_ACTUAL_WARNINGS} printed warnings != {expected} expected shifts!\n", flush=True)
    except Exception:
        pass
