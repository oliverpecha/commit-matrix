import csv
import os
from datetime import datetime

def parse_date_to_timestamp(date_str):
    """Convert 'May 30, \'26' format to Unix timestamp"""
    try:
        cleaned = date_str.replace("'", "20")
        dt = datetime.strptime(cleaned, "%b %d, %Y")
        return int(dt.timestamp())
    except:
        return 0

def fetch_ledger(repo):
    p = f"/app/data/{repo}/{repo}_ledger_cirsd.csv"
    if not os.path.exists(p):
        return []
    out = []
    try:
        with open(p, mode="r", encoding="utf-8-sig", errors="replace") as f:
            for idx, r in enumerate(csv.DictReader(f)):
                def s_int(k, d=0):
                    try:
                        return int(str(r.get(k, d)).replace("+", "").replace("-", "").strip())
                    except Exception:
                        return d
                n_val = r.get("#") or r.get("n")
                date_str = r.get("Date", "")
                out.append({
                    "n": int(n_val) if n_val and str(n_val).isdigit() else idx + 1,
                    "ts": parse_date_to_timestamp(date_str),
                    "date": date_str,
                    "type": r.get("Type", "commit"),
                    "scope": r.get("Scope", ""),
                    "s": r.get("Subject", ""),
                    "tier": str(r.get("Tier", "Routine")).capitalize(),
                    "C": s_int("C", 1),
                    "I": s_int("I", 1),
                    "R": s_int("R", 1),
                    "S": s_int("S", 1),
                    "D": s_int("D", 1),
                    "tot": s_int("Total", 5),
                    "lines_added": s_int("Additions", 0),
                    "lines_deleted": s_int("Deletions", 0),
                    "h": r.get("Hash", "")
                })
    except Exception as e:
        print(f"LEDGER FETCH ERROR: {e}", flush=True)
    return out
