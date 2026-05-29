import os
import csv
import json
import subprocess
import asyncio
import codecs
import time
import logging
import litellm
from datetime import datetime
from fastapi import FastAPI, Request, Query
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# --- LITELM LOGGING SWITCH ---
if os.environ.get("MATRIX_DEBUG", "0") == "0":
    litellm.suppress_debug_info = True
    logging.getLogger("LiteLLM").setLevel(logging.ERROR)
else:
    litellm.suppress_debug_info = False
    logging.getLogger("LiteLLM").setLevel(logging.DEBUG)

app = FastAPI(title="CommitMatrix Core Engine")

# Mount Static assets
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

def fetch_ledger(repo):
    import csv, os
    p = f"/app/data/{repo}/{repo}_ledger_cirsd.csv"
    if not os.path.exists(p): return []
    out = []
    try:
        # utf-8-sig automatically strips hidden BOM characters from CSV headers
        with open(p, mode="r", encoding="utf-8-sig", errors="replace") as f:
            for idx, r in enumerate(csv.DictReader(f)):
                def s_int(k, d=0):
                    try: return int(str(r.get(k, d)).replace("+", "").replace("-", "").strip())
                    except: return d
                
                # Fallback to 'n' if '#' is missing due to weird Git encodings
                n_val = r.get("#") or r.get("n")
                
                out.append({
                    "n": int(n_val) if n_val and str(n_val).isdigit() else idx + 1,
                    "ts": 0, "date": r.get("Date", ""),
                    "type": r.get("Type", "commit"), "scope": r.get("Scope", ""),
                    "s": r.get("Subject", ""), "tier": str(r.get("Tier", "Routine")).capitalize(),
                    "C": s_int("C", 1), "I": s_int("I", 1), "R": s_int("R", 1),
                    "S": s_int("S", 1), "D": s_int("D", 1), "tot": s_int("Total", 5),
                    "lines_added": s_int("Additions", 0), "lines_deleted": s_int("Deletions", 0),
                    "h": r.get("Hash", "")
                })
    except Exception as e: 
        print(f"LEDGER FETCH ERROR: {e}", flush=True)
    return out

@app.get("/")
async def index(request: Request, repo: str = "commit-matrix"):
    return templates.TemplateResponse(request=request, name="matrix.html", context={
        "repo": repo, "commits_data": fetch_ledger(repo),
        "time_autoclose": int(os.environ.get("MATRIX_TIME_AUTOCLOSE", "5"))
    })

@app.get("/api/data")
async def get_data(repo: str = "commit-matrix", token: str = ""):
    return JSONResponse(content=fetch_ledger(repo))

@app.post("/api/engine/control")
async def control_engine(request: Request, action: str, repo: str = "commit-matrix"):
    import os
    c_name = "matrix-analyzer-singleton"
    if action == "pause":
        os.system(f"docker pause {c_name} > /dev/null 2>&1")
        return JSONResponse(content={"status": "paused", "action": action})
    elif action == "play":
        os.system(f"docker unpause {c_name} > /dev/null 2>&1")
        return JSONResponse(content={"status": "running", "action": action})
    return JSONResponse(content={"status": "acknowledged", "action": action})

@app.post("/api/scan")
async def stream_scan(request: Request, repo: str = "commit-matrix", rubric: str = "cirsd", token: str = ""):
    c_name = "matrix-analyzer-singleton"
    
    async def generate():
        yield "🤖 CONNECTED TO DOCKER ENGINE DAEMON.\n\n"
        
        # Backend natively protected by Singleton Architecture.
        
        # Kill any identically named collision container block
        os.system(f"docker rm -f {c_name} > /dev/null 2>&1")
        
        gemini_key = os.environ.get("GEMINI_API_KEY", "")
        max_w = os.environ.get("MATRIX_MAX_WORKERS", "32")
        max_commits = os.environ.get("MATRIX_MAX_COMMITS", "0")
        
        # Setup clean absolute directory execution paths mapping across host mounts
        target_volume = f"/root/commit-matrix" if repo == "commit-matrix" else f"/root/commit-matrix/data/{repo}/src"
        data_volume = "/root/commit-matrix/data"

        rpm_limit = os.environ.get("MATRIX_RPM_LIMIT", "15")
        model_name = os.environ.get("MATRIX_MODEL", "gemini/gemini-2.5-flash-lite")
        stress_test = os.environ.get("MATRIX_STRESS_TEST", "0")
        crash_rate = os.environ.get("MATRIX_CRASH_RATE", "0.4")
        
        docker_cmd = [
            "docker", "run", "-d", "--name", c_name,
            "-v", "/var/run/docker.sock:/var/run/docker.sock",
            "-v", f"{target_volume}:/target_repo",
            "-v", f"{data_volume}:/app/data",
            "-v", "/root/commit-matrix/rubrics:/app/rubrics",
            "-v", "/root/commit-matrix/backend:/app/backend",
            "-e", f"GEMINI_API_KEY={gemini_key}",
            "-e", f"MATRIX_MAX_WORKERS={max_w}",
            "-e", f"MATRIX_MAX_COMMITS={max_commits}",
            "-e", f"MATRIX_RPM_LIMIT={rpm_limit}",
            "-e", f"MATRIX_MODEL={model_name}",
            "-e", f"MATRIX_STRESS_TEST={stress_test}",
            "-e", f"MATRIX_CRASH_RATE={crash_rate}",
            "-e", "LITELLM_LOG=ERROR",
            "-e", "SUPPRESS_LITELLM_LOGS=True",
            "-e", f"HOST_REPO_NAME={repo}",
            "-e", f"RUBRIC_NAME={rubric}",
            "commit-matrix-core:latest",
            "python", "-u", "/app/backend/parser.py", "--repo", "/target_repo"
        ]
        
        try:
            process = await asyncio.create_subprocess_exec(
                *docker_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                yield f"❌ DOCKER INVOCATION FAILED: {stderr.decode(errors='ignore')}\n"
                return
                
            container_id = stdout.decode().strip()
            yield f"🐳 ENGINE INITIALIZED CONTAINER CONTAINER_ID: {container_id[:12]}\n\n"
            
            # Follow log streams natively in real-time chunk cycles
            log_stream = await asyncio.create_subprocess_exec(
                "docker", "logs", "-f", c_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )
            
            while True:
                if await request.is_disconnected():
                    break
                    
                line = await log_stream.stdout.readline()
                if not line:
                    break
                yield line.decode(errors='ignore')
                
            await log_stream.wait()
            
            # Pull check execution codes out of the dead runner container
            inspect = await asyncio.create_subprocess_exec(
                "docker", "inspect", "-f", "{{.State.ExitCode}}", c_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )
            i_out, _ = await inspect.communicate()
            exit_code = i_out.decode(errors="ignore").strip()

            if inspect.returncode != 0 or "No such object" in exit_code:
                yield "\n\n⚠️ Engine cleanup race detected while resolving final container state. Stream output above is authoritative.\n[__MATRIX_EOF_SUCCESS__]"
            elif exit_code == "0":
                yield "\n\n[__MATRIX_EOF_SUCCESS__]"
            else:
                yield f"\n\n❌ FATAL ENGINE CRASH (Exit Code {exit_code}). See traceback above.\n[__MATRIX_EOF_FAIL_CODE_{exit_code}__]"

        except Exception as ex:
            yield f"\n⚠️ INTERNAL STREAM STREAM EXCEPTION ERROR: {str(ex)}\n"
        finally:
            # Complete execution isolation. Kills runtime thread context on disconnect/exit
            os.system(f"docker rm -f {c_name} > /dev/null 2>&1")

    return StreamingResponse(generate(), media_type="text/plain")
