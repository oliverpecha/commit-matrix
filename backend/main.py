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
async def dashboard_home(request: Request, repo: str = "commit-matrix", token: str = None, rubric: str = "cirsd"):
    if token != METRICS_KEY:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Unauthorized")
    
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
    
    return templates.TemplateResponse(request=request, name="matrix.html", context={"token": token, "commits_data": commits, "rubric": rubric, "version": VERSION, "layout": os.environ.get("MATRIX_LAYOUT", "toast").lower(), "time_autoclose": int(os.environ.get("MATRIX_TIME_AUTOCLOSE", 5))})

from fastapi.responses import StreamingResponse
import subprocess

from fastapi.responses import JSONResponse
@app.get("/api/data")
async def get_live_data(repo: str = "commit-matrix", token: str = None, rubric: str = "cirsd"):
    import os, csv
    from datetime import datetime
    from fastapi.responses import JSONResponse
    commits = []
    csv_path = f"/app/data/{repo}/{repo}_ledger_{rubric}.csv"
    if os.path.exists(csv_path):
        try:
            with open(csv_path, "r", encoding="utf-8-sig", errors="replace") as f:
                reader = csv.DictReader(f)
                for idx, row in enumerate(reader):
                    if not row.get("hash_short"): continue
                    c_data = {}
                    for key, val in row.items():
                        if val == "True": c_data[key] = True
                        elif val == "False": c_data[key] = False
                        else:
                            try: c_data[key] = int(float(val))
                            except: c_data[key] = val.strip() if val else ""
                    c_data["n"] = idx + 1
                    c_data["h"] = c_data.get("hash_short", "")
                    c_data["s"] = c_data.get("subject", "")
                    c_data["tot"] = sum([int(c_data.get(k,0)) for k in ['C','I','R','S','D'] if str(c_data.get(k,0)).isdigit()])
                    if "tier" not in c_data or not c_data["tier"]: c_data["tier"] = "Routine"
                    
                    date_str = c_data.get("author_date", "")
                    ts = 0
                    if date_str:
                        for fmt in ["%Y-%m-%d %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S%z"]:
                            try: ts = int(datetime.strptime(date_str, fmt).timestamp()); break
                            except: continue
                    c_data["ts"] = ts
                    commits.append(c_data)
        except Exception as e: print(f"API DATA ERROR: {e}")
    return JSONResponse(commits)

@app.post("/api/scan")
async def stream_scan(request: Request, repo: str = "commit-matrix", token: str = None):
    import asyncio
    from fastapi.responses import HTMLResponse, StreamingResponse
    import time
    
    if token != METRICS_KEY:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    async def generate():
        yield "🤖 CONNECTED TO DOCKER ENGINE DAEMON.\n\n"
        os.system("docker ps -q --filter name=matrix-analyzer- | xargs -r docker rm -f > /dev/null 2>&1")
        gemini_key = os.environ.get("GEMINI_API_KEY", "")
        max_w = os.environ.get("MATRIX_MAX_WORKERS", "32")
        model_name = os.environ.get("MATRIX_MODEL")
        if not model_name:
            yield "❌ ERROR: 🛑 CRITICAL: MATRIX_MODEL is not defined in .env. Engine aborted.\n\n"
            return
        c_name = f"matrix-analyzer-{int(time.time())}"
        
        cmd = ["docker", "run", "--rm", "--name", c_name, "-v", "/root/commit-matrix:/target_repo", "-v", "/root/commit-matrix/data:/app/data", "-v", "/root/commit-matrix/rubrics:/app/rubrics", "-v", "/root/commit-matrix/backend:/app/backend", "-e", f"GEMINI_API_KEY={gemini_key}", "-e", f"MATRIX_MAX_WORKERS={max_w}", "-e", f"MODEL_NAME={model_name}", "-e", f"HOST_REPO_NAME={repo}", "commit-matrix-core:latest", "python", "-u", "/app/backend/parser.py", "--repo", "/target_repo"]
        
        c_disp = cmd.copy()
        for i, val in enumerate(c_disp):
            if val.startswith("GEMINI_API_KEY="): c_disp[i] = "GEMINI_API_KEY=********"
                
        yield f"🔗 Executing nested container command:\n   <span style='color:#555'>{' '.join(c_disp)}</span>\n\n"
        yield f"🧬 INITIATING AI SCORING MATRIX ANALYSIS ON REPOSITORY: [{repo}]\n\n"

        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
            import codecs
            # The incremental decoder safely buffers shattered emojis until they are whole
            decoder = codecs.getincrementaldecoder('utf-8')()
            while True:
                if await request.is_disconnected(): break
                try:
                    chunk = await asyncio.wait_for(proc.stdout.read(1024), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                if not chunk: break
                text = decoder.decode(chunk)
                if text: yield text
        except asyncio.CancelledError: pass
        except Exception as e: yield f"❌ ERROR: {e}\n\n"
        finally:
            if proc:
                try: proc.terminate()
                except: pass
            os.system(f"docker rm -f {c_name} > /dev/null 2>&1")

    return StreamingResponse(generate(), media_type="text/plain")
