import glob
import csv
import os
import time
from datetime import datetime

_CACHE = {}
CACHE_TTL = 60  # Cache ledger reads for 60 seconds

def parse_date_to_timestamp(date_str):
    """Convert 'May 30, \'26' format to Unix timestamp"""
    try:
        cleaned = date_str.replace("'", "20")
        dt = datetime.strptime(cleaned, "%b %d, %Y")
        return int(dt.timestamp())
    except:
        return 0

def fetch_ledger_raw(repo, rubric=None, owner=None):
    rubric = rubric or __import__("os").environ.get("RUBRIC_NAME", "unknown")
    
    candidates = []
    if owner and owner != "local":
        candidates.extend([
            f"/app/data/{owner}/{repo}/db/{repo}_ledger_{rubric}.csv",
            f"data/{owner}/{repo}/db/{repo}_ledger_{rubric}.csv"
        ])
        
    candidates.extend(glob.glob(f"/app/data/*/{repo}/db/{repo}_ledger_{rubric}.csv"))
    candidates.extend(glob.glob(f"data/*/{repo}/db/{repo}_ledger_{rubric}.csv"))

    p = next((candidate for candidate in candidates if os.path.exists(candidate)), None)
    if not p:
        return []
    out = []
    try:
        with open(p, mode="r", encoding="utf-8-sig", errors="replace") as f:
            for idx, r in enumerate(csv.DictReader(f)):
                def s_int(k, d=0):
                    try:
                        return int(str(r.get(k, d)).replace("+", "").replace("-", "").strip())
                    except (KeyboardInterrupt, SystemExit):
                        raise
                    except Exception:
                        return d
                n_val = r.get("#") or r.get("n")
                date_str = r.get("Date", "")
                
                s_val = r.get("Subject") or r.get("subject", "")
                type_val = r.get("Type") or r.get("type")
                scope_val = r.get("Scope") or r.get("scope", "")
                
                if type_val in (None, "", "commit"):
                    import re
                    m = re.match(r"^([a-zA-Z]+)(?:\(([^)]+)\))?:", s_val)
                    if m:
                        type_val = m.group(1).lower()
                        scope_val = m.group(2) or scope_val
                    else:
                        type_val = "commit"

                out.append({
                    "n": int(n_val) if n_val and str(n_val).isdigit() else idx + 1,
                    "ts": parse_date_to_timestamp(date_str),
                    "date": date_str,
                    "type": type_val,
                    "scope": scope_val,
                    "s": s_val,
                    "tier": str(r.get("Tier", "Routine")).capitalize(),
                    "C": s_int("C", 1),
                    "I": s_int("I", 1),
                    "R": s_int("R", 1),
                    "S": s_int("S", 1),
                    "D": s_int("D", 1),
                    "tot": s_int("Total", 5),
                    "lines_added": s_int("Additions", 0),
                    "lines_deleted": s_int("Deletions", 0),
                    "h": r.get("Hash") or r.get("hash", ""),
                    "t_metrics": str(r.get("touches_metrics", "")).lower() == "true",
                    "t_preflight": str(r.get("touches_preflight", "")).lower() == "true",
                    "t_tests": str(r.get("touches_tests", "")).lower() == "true",
                    "t_docs": str(r.get("touches_docs", "")).lower() == "true",
                    "t_dashboard": str(r.get("touches_dashboard", "")).lower() == "true",
                    "t_config": str(r.get("touches_config", "")).lower() == "true",
                    "t_scripts": str(r.get("touches_scripts", "")).lower() == "true",
                    "t_proxy": str(r.get("touches_proxy", "")).lower() == "true",
                    "t_core": str(r.get("touches_core", "")).lower() == "true"
                })
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as e:
        print(f"LEDGER FETCH ERROR: {e}", flush=True)
    return out

def fetch_ledger(repo, rubric=None, owner=None, force=False):
    import glob, os, time
    rubric = rubric or os.environ.get("RUBRIC_NAME", "unknown")
    cache_key = f"{repo}_{rubric}"
    now = time.time()
    
    cached = _CACHE.get(cache_key, {})
    cached_path = cached.get('path')
    
    # 1. Fast-path mtime check if we already know the exact file path
    if cached_path and os.path.exists(cached_path):
        current_mtime = os.path.getmtime(cached_path)
        if not force and (now - cached.get('ts', 0) < CACHE_TTL) and (cached.get('mtime', 0) == current_mtime):
            return cached['data']
            
    # 2. Slow-path: path discovery (only runs on pure cache miss or file deletion)
    candidates = []
    if owner and owner != "local":
        candidates.extend([f"/app/data/{owner}/{repo}/db/{repo}_ledger_{rubric}.csv", f"data/{owner}/{repo}/db/{repo}_ledger_{rubric}.csv"])
    candidates.extend(glob.glob(f"/app/data/*/{repo}/db/{repo}_ledger_{rubric}.csv") + glob.glob(f"data/*/{repo}/db/{repo}_ledger_{rubric}.csv"))
    
    p = next((c for c in candidates if os.path.exists(c)), None)
    if not p:
        return []
        
    current_mtime = os.path.getmtime(p)
    data = fetch_ledger_raw(repo, rubric, owner)
    if data:
        _CACHE[cache_key] = {'ts': now, 'mtime': current_mtime, 'path': p, 'data': data}
    elif cache_key in _CACHE:
        del _CACHE[cache_key]
    return data

