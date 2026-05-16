import os
import csv
import json
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="CommitMatrix Telemetry")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

METRICS_KEY = os.environ.get("MATRIX_TOKEN", "mochi")

def safe_int(val, fallback=0):
    try: return int(float(val))
    except: return fallback

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, token: str = None):
    if token != METRICS_KEY:
        return HTMLResponse("<h1>Unauthorized.</h1>", status_code=401)
    
    commits = []
    csv_path = "/app/data/commit_pulse/beo_git_commits_clean.csv"
            
    if not os.path.exists(csv_path):
        print(f"MATRIX SYSTEM WARNING: {csv_path} not found.")
    else:
        try:
            with open(csv_path, "r", encoding="utf-8-sig", errors="replace") as f:
                reader = csv.DictReader(f)
                for idx, row in enumerate(reader):
                    if row.get("map_type") == "dropped" or not row.get("hash_new"):
                        continue
                    date_str = (row.get("author_date") or "").strip()
                    ts = 0
                    if date_str:
                        for fmt in ["%Y-%m-%d %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S%z"]:
                            try:
                                ts = int(datetime.strptime(date_str, fmt).timestamp())
                                break
                            except ValueError: continue

                    h = row.get("hash_new") or row.get("hash_short") or ""
                    s = row.get("subject_v2") or row.get("subject_v1") or ""
                    tier_raw = (row.get("tier") or "Routine").strip()
                    tier = tier_raw.split(" ")[-1] if " " in tier_raw else tier_raw
                    
                    commits.append({
                        "n": safe_int(row.get("new_order", idx + 1)),
                        "h": h.strip()[:7],
                        "s": s.strip(),
                        "fc": safe_int(row.get("files_changed_exact")),
                        "la": safe_int(row.get("lines_added_exact")),
                        "ld": safe_int(row.get("lines_deleted_exact")),
                        "C": safe_int(row.get("C_complexity")),
                        "I": safe_int(row.get("I_impact")),
                        "R": safe_int(row.get("R_risk")),
                        "S": safe_int(row.get("S_scope")),
                        "D": safe_int(row.get("D_doc_quality")),
                        "tot": safe_int(row.get("total_score")),
                        "tier": tier,
                        "ts": ts,
                        "t_proxy": row.get("touches_proxy") == "True",
                        "t_scripts": row.get("touches_scripts") == "True",
                        "t_config": row.get("touches_config") == "True",
                        "t_dashboard": row.get("touches_dashboard") == "True",
                        "t_docs": row.get("touches_docs") == "True",
                        "t_tests": row.get("touches_tests") == "True",
                        "t_preflight": row.get("touches_preflight") == "True",
                        "t_metrics": row.get("touches_metrics") == "True",
                        "t_core": row.get("touches_critical") == "True"
                    })
        except Exception as e:
            print(f"MATRIX SYSTEM ERROR: {e}")
        
    return templates.TemplateResponse("matrix.html", {"request": request, "token": token, "commits_data": json.dumps(commits)})
