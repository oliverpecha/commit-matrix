"""
Telemetry progress renderer for architecture history builds.
Renders milestone updates to stderr. Throttled for building_entries.
"""
import sys
import time

_last_update_time: float = 0.0
_last_entry_count: int = 0
_THROTTLE_INTERVAL: float = 0.5
_THROTTLE_ENTRIES: int = 5

def _should_throttle(phase: str, data: dict) -> bool:
    global _last_update_time, _last_entry_count
    if phase != "building_entries":
        return False
    now = time.monotonic()
    current = data.get("current", 0)
    total = data.get("total", 0)
    if current >= total:
        return False
    if (now - _last_update_time) < _THROTTLE_INTERVAL:
        return True
    if (current - _last_entry_count) < _THROTTLE_ENTRIES:
        return True
    return False

def _format_bar(current: int, total: int, width: int = 20) -> str:
    if total <= 0:
        return chr(9617) * width
    filled = int(width * current / total)
    return chr(9608) * filled + chr(9617) * (width - filled)

def _fmt_date_short(iso_date):
    if not iso_date:
        return ""
    try:
        from datetime import datetime
        dt = datetime.strptime(iso_date[:10], "%Y-%m-%d")
        return dt.strftime("%b %d")
    except Exception:
        return ""

def render_progress(phase: str, data: dict) -> None:
    global _last_update_time, _last_entry_count
    
    # Skip progress output unless debug mode enabled
    import os
    if os.environ.get("MATRIX_DEBUG", "").lower() not in ("1", "true", "yes"):
        return
    
    if _should_throttle(phase, data):
        return
    _last_update_time = time.monotonic()
    if phase == "ledger_loaded":
        c = data.get("commit_count", "?")
        print(f"[arch-history] Loading ledger... {c} commits", file=sys.stderr, flush=True)
    elif phase == "eras_computed":
        s = data.get("unique_sigs", "?")
        print(f"[arch-history] Computing eras... {s} unique signatures", file=sys.stderr, flush=True)
    elif phase == "building_entries":
        current = data.get("current", 0)
        total = data.get("total", 0)
        _last_entry_count = current
        bar = _format_bar(current, total)
        print(f"\r[arch-history] Building entries... {current}/{total} {bar}",
              end="", file=sys.stderr, flush=True)
        if current >= total:
            print(file=sys.stderr, flush=True)
    elif phase == "computing_metrics":
        print("[arch-history] Computing metrics...", file=sys.stderr, flush=True)
    elif phase == "build_complete":
        b = data.get("boundaries", "?")
        sn = data.get("snapshots", "?")
        co = data.get("commits", "?")
        label = data.get("latest_boundary_label")
        date = data.get("latest_boundary_date")
        print(f"[arch-history] Ready: {b} boundaries \u00b7 {sn} snapshots \u00b7 {co} commits",
              file=sys.stderr, flush=True)
        if label:
            ds = f" ({_fmt_date_short(date)})" if date else ""
            print(f"[arch-history] Latest boundary: {label}{ds}", file=sys.stderr, flush=True)
    elif phase == "filter_applied":
        parts = []
        for key in ("since", "until", "generation", "snapshot", "commit"):
            val = data.get(key)
            if val:
                parts.append(f"{key}: {val}")
        if parts:
            sep = " \u00b7 "
            print(f"[arch-history] Scope: {sep.join(parts)}", file=sys.stderr, flush=True)
    else:
        print(f"[arch-history] {phase}: {data}", file=sys.stderr, flush=True)

def reset_throttle() -> None:
    global _last_update_time, _last_entry_count
    _last_update_time = 0.0
    _last_entry_count = 0
