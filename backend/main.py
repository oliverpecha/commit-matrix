import os, csv, json
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

import os
try:
    with open('/app/VERSION', 'r') as vf:
        VERSION = vf.read().strip()
except Exception:
    VERSION = "v1.0"

from fastapi.staticfiles import StaticFiles

app = FastAPI(title="CommitMatrix Telemetry")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

METRICS_KEY = os.environ.get("MATRIX_TOKEN", "mochi")

@app.get("/", response_class=HTMLResponse)
async def dashboard_home(request: Request, repo: str = "example-repo", token: str = None, rubric: str = "cirsd"):
    if token != METRICS_KEY: return HTMLResponse("<h1>Unauthorized.</h1>", status_code=401)
    
    commits = []
    csv_path = f"/app/data/{repo}/{repo}_ledger_{rubric}.csv"
            
    if not os.path.exists(csv_path): print(f"MATRIX WARNING: {csv_path} not found.")
    else:
        try:
            with open(csv_path, "r", encoding="utf-8-sig", errors="replace") as f:
                reader = csv.DictReader(f)
                for idx, row in enumerate(reader):
                    if not row.get("hash_short"): continue
                    commit_data = {}
                    for key, val in row.items():
                        if val == "True": commit_data[key] = True
                        elif val == "False": commit_data[key] = False
                        else:
                            try: commit_data[key] = int(float(val))
                            except: commit_data[key] = val.strip() if val else ""
                    commit_data["n"] = idx + 1
                    commit_data["h"] = commit_data.get("hash_short", "")
                    commit_data["s"] = commit_data.get("subject", "")
                    date_str = commit_data.get("author_date", "")
                    ts = 0
                    if date_str:
                        for fmt in ["%Y-%m-%d %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S%z"]:
                            try: ts = int(datetime.strptime(date_str, fmt).timestamp()); break
                            except: continue
                    commit_data["ts"] = ts
                    commits.append(commit_data)
        except Exception as e: print(f"MATRIX PARSER ERROR: {e}")
    
    return templates.TemplateResponse(request=request, name="matrix.html", context={"token": token, "commits_data": commits, "rubric": rubric, "version": VERSION})

from fastapi.responses import StreamingResponse
import subprocess

@app.post("/api/scan")
async def stream_scan(request: Request, repo: str = "example-repo", token: str = None):
    from fastapi.responses import HTMLResponse, StreamingResponse
    import subprocess
    
    if token != METRICS_KEY:
        return HTMLResponse("<h1>Unauthorized.</h1>", status_code=401)
        
    def generate():
        yield "🤖 CONNECTED TO DOCKER ENGINE DAEMON.\n\n"
        
        gemini_key = os.environ.get("GEMINI_API_KEY", "")
        cmd = [
            "docker", "run", "--rm",
            "-v", "/root/commit-matrix:/target_repo",
            "-v", "/root/commit-matrix/data:/app/data",
            "-v", "/root/commit-matrix/rubrics:/app/rubrics",
            "-v", "/root/commit-matrix/backend:/app/backend",
            "-e", f"GEMINI_API_KEY={gemini_key}",
            "-e", "MODEL_NAME=gemini-1.5-flash",
            "-e", f"HOST_REPO_NAME={repo}",
            "commit-matrix-core:latest",
            "python", "-u", "/app/backend/parser.py", "--repo", "/target_repo"
        ]
        
        cmd_display = cmd.copy()
        for i, val in enumerate(cmd_display):
            if val.startswith("GEMINI_API_KEY="):
                cmd_display[i] = "GEMINI_API_KEY=********"
                
        yield f"🔗 Executing nested container command:\n   <span style='color:#555'>{' '.join(cmd_display)}</span>\n\n"
        yield f"🧬 INITIATING AI SCORING MATRIX ANALYSIS ON REPOSITORY: [{repo}]\n\n"
        yield "⏳ Booting isolated analyzer environment (this takes ~3-5 seconds)...\n\n"

        process = None
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            # Character-streaming logic for live dots
            while True:
                char = process.stdout.read(1)
                if not char and process.poll() is not None:
                    break
                if char:
                    yield char
            process.wait()
        except Exception as e:
            yield f"❌ ERROR: {e}\n\n"
        finally:
            # The Zombie Killer: Violently terminate the nested process on disconnect
            if process and process.poll() is None:
                process.terminate()
                process.kill()

    return StreamingResponse(generate(), media_type="text/plain")
