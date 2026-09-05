from __future__ import annotations

_ACTUAL_WARNINGS = 0
import os
import sqlite3
import glob
from pathlib import Path
from backend.services.architecture.taxonomy import get_shape_metadata, normalize_cause_tag, get_boundary_magnitude

def _get_shape_emoji(sig):
    try:
        db_paths = glob.glob("data/*/*/db/{HOST_REPO_NAME}.db")
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
            db_paths = glob.glob("data/*/*/db/{HOST_REPO_NAME}.db")
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
        except (KeyboardInterrupt, SystemExit):
            raise
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
    db = Path(db_path) if db_path else Path((glob.glob(f"data/*/{repo_label}") + [f"data/local/{repo_label}"])[0]) / "db" / f"{repo_label}.db"
    try:
        db.parent.mkdir(parents=True, exist_ok=True)
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        pass
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

            print("\n🗺️  Architecture Boundary Map")
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
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        pass

def print_oracle_initialization(repo_label: str, db_path: str, is_genuine_warm_start: bool) -> None:
    import sqlite3
    try:
        db = Path(db_path)
        if not db.exists(): return
        with sqlite3.connect(str(db)) as _conn_b:
            _run_id = -1
            if _conn_b.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='architecture_runs'").fetchone():
                _r_row = _conn_b.execute("SELECT run_id FROM architecture_runs WHERE repo_label = ?", (repo_label,)).fetchone()
                if _r_row: _run_id = _r_row[0]
            
            _s_count = _conn_b.execute("SELECT COUNT(*) FROM architecture_snapshots WHERE run_id = ?", (_run_id,)).fetchone()[0] if _run_id != -1 and _conn_b.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='architecture_snapshots'").fetchone() else 0
            _b_count = _conn_b.execute("SELECT COUNT(*) FROM architecture_boundaries WHERE run_id = ?", (_run_id,)).fetchone()[0] if _run_id != -1 and _conn_b.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='architecture_boundaries'").fetchone() else 0
            _c_count = _conn_b.execute("SELECT COUNT(*) FROM architecture_commits WHERE run_id = ?", (_run_id,)).fetchone()[0] if _run_id != -1 and _conn_b.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='architecture_commits'").fetchone() else 0

        boot_type = "Ledger Linked (Warm Boot)" if is_genuine_warm_start else "Cold Boot"

        print('\n' + '─' * 71, flush=True)
        print('🏛️  Architecture Oracle Initialized', flush=True)
        print(f'    Boot Mode     │ {boot_type}', flush=True)
        print(f'    Snapshots     │ {_s_count}', flush=True)
        print(f'    Eras          │ {_b_count} Structural Eras', flush=True)
        print(f'    Commits       │ {_c_count}', flush=True)
        print(f'    Ledger Sync   │ SQLite WAL active ({db_path})', flush=True)
        print('─' * 71 + '\n', flush=True)
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        pass

def print_architecture_event(state, repo_label=None, db_path=None):
    if not getattr(state, 'available', True):
        print('─' * 71, flush=True)
        print('🏗️  Architecture unavailable', flush=True)
        return
    if not (getattr(state, 'established', False) or getattr(state, 'advanced', False)): return
    
    raw_shape = getattr(state, 'change_shape', '')
    meta = get_shape_metadata(raw_shape)
    cause = meta.get('label', raw_shape or 'unknown')
    icon = meta.get('icon', '🕰️')
    title = '📍 Current Architecture Head' if not getattr(state, 'advanced', False) else f'{icon}  Architecture Boundary (Gen {getattr(state, "gen", "?")})'
    
    print('\n' + '─' * 71, flush=True)
    print(title, flush=True)
    print(f'    Cause      │ {cause}', flush=True)
    print(f'    Mode       │ {getattr(state, "mode", "programmatic")}', flush=True)
    print('─' * 71 + '\n', flush=True)

def print_final_pipeline_summary_report(repo_label: str, db_path: str, commits_with_ids: list = None) -> None:
    global _ACTUAL_WARNINGS
    import sqlite3
    db = Path(db_path) if db_path else Path((glob.glob(f"data/*/{repo_label}") + [f"data/local/{repo_label}"])[0]) / "db" / f"{repo_label}.db"
    try:
        db.parent.mkdir(parents=True, exist_ok=True)
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        pass
    if not db.exists(): return

    try:
        from backend.services.db.reader import read_scan_range, read_vacuums
        scan = read_scan_range(repo_label)
        vacuums = read_vacuums(repo_label)
        
        print('─' * 71, flush=True)
        run_head = commits_with_ids[0][0] if commits_with_ids and len(commits_with_ids) > 0 else 0
        run_tail = commits_with_ids[-1][0] if commits_with_ids and len(commits_with_ids) > 0 else 0
        
        with sqlite3.connect(str(db)) as _c:
            _t_exists = _c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='architecture_boundaries'").fetchone()
            _r_row = _c.execute("SELECT run_id FROM architecture_runs WHERE repo_label = ?", (repo_label,)).fetchone() if _t_exists else None
            _run_id = _r_row[0] if _r_row else -1
            b_count = _c.execute("SELECT COUNT(*) FROM architecture_boundaries WHERE run_id = ?", (_run_id,)).fetchone()[0] if _run_id != -1 and _t_exists else 0
            
        print(f"    Commits       │ processed (#{run_head} to #{run_tail})", flush=True)
        print(f"    Boundaries    │ {b_count} structural era triggers", flush=True)
        if vacuums:
            total_vac = sum(v.get("commit_count", 0) for v in vacuums)
            print(f"    Vacuums       │ {total_vac} unscanned", flush=True)
        print('─' * 71 + '\n', flush=True)
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        pass

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


def render_bootstrap_banner(repo_path, repo_label, log_path=None):
    import os
    import sys
    
    # Read contextual triggers
    trigger_source = os.environ.get("MATRIX_TRIGGER_SOURCE", "").lower()
    is_browser = "browser" in trigger_source or "frontend" in trigger_source or "web" in trigger_source
    context_str = "🌐 BROWSER / FRONTEND" if is_browser else "🐚 NATIVE TERMINAL"
    
    # 1. Resolve True Execution Mode Options
    is_random = str(os.environ.get("RANDOM_SCORE", "false")).strip().lower() in ("1", "true", "yes", "on")
    mode_str = "🎲 RANDOM SCORING ENABLED" if is_random else "🤖 LLM SCORING MODE"
    
    # 2. Extract and match runtime keys cleanly
    # Check both potential environment keys used across local layouts
    model_name = os.environ.get("MATRIX_MODEL", os.environ.get("MATRIX_MODEL_NAME", "gemini/gemini-2.5-flash-lite"))
    
    is_debug = str(os.environ.get("MATRIX_DEBUG", "false")).strip().lower() in ("1", "true", "yes", "on")
    debug_status = "🐞 ACTIVE (VERBOSE)" if is_debug else "⚪ DISABLED"
    
    stress_status = "🔴 ACTIVE" if str(os.environ.get("MATRIX_STRESS_TEST", "0")) in ("1", "true", "yes", "on") else "⚪ INACTIVE"
    workers = os.environ.get("MATRIX_MAX_WORKERS", "32")

    banner = [
        "═" * 71,
        "🚀 COMMIT-MATRIX PIPELINE ENGINE INITIALIZED",
        f"   Target Repository │ {repo_label}",
        f"   Trigger Context   │ {context_str}",
        f"   Execution Mode    │ {mode_str}",
        f"   Primary Model     │ {model_name}",
        f"   Debug Telemetry   │ {debug_status}",
        f"   Stress Test Mode  │ {stress_status}",
        f"   Max Worker Units  │ {workers}"
    ]
    if log_path:
        banner.append(f"   Persistent Log    │ {log_path}")
    banner.append("═" * 71 + chr(10))
    return chr(10).join(banner)