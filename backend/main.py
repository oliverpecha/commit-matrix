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
from backend.services.ledger_reader import fetch_ledger
from backend.services.docker_runtime import (
    CONTAINER_NAME,
    build_scan_docker_cmd,
    follow_container_logs,
    force_remove_container,
    inspect_container_exit_code,
    pause_container,
    remove_container,
    run_docker_detached,
    unpause_container,
)
from backend.services.scan_outcome import (
    cleanup_race_success_eof,
    docker_invocation_failed,
    failure_eof,
    stream_exception_message,
    success_eof,
)

# --- LITELM LOGGING SWITCH ---
if str(os.environ.get("MATRIX_DEBUG", "false")).strip().lower() in ("1", "true", "yes", "on"):
    litellm.suppress_debug_info = False
    logging.getLogger("LiteLLM").setLevel(logging.DEBUG)
else:
    litellm.suppress_debug_info = True
    logging.getLogger("LiteLLM").setLevel(logging.ERROR)

app = FastAPI(title="CommitMatrix Core Engine")

# Mount Static assets
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

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
    if action == "pause":
        return JSONResponse(content=pause_container(CONTAINER_NAME))
    elif action == "play":
        return JSONResponse(content=unpause_container(CONTAINER_NAME))
    return JSONResponse(content={"status": "acknowledged", "action": action})

@app.post("/api/scan")
async def stream_scan(request: Request, repo: str = "commit-matrix", rubric: str = "cirsd", token: str = ""):
    async def generate():
        yield "🤖 CONNECTED TO DOCKER ENGINE DAEMON.\n\n"
        
        # Backend natively protected by Singleton Architecture.
        
        # Kill any identically named collision container block
        force_remove_container(CONTAINER_NAME)
        docker_cmd = build_scan_docker_cmd(repo=repo, rubric=rubric, container_name=CONTAINER_NAME)
        
        try:
            returncode, stdout, stderr = await run_docker_detached(docker_cmd)

            if returncode != 0:
                stdout_text = stdout.decode(errors='ignore') if stdout else ""
                stderr_text = stderr.decode(errors='ignore') if stderr else ""
                yield docker_invocation_failed(stdout_text, stderr_text)
                return
                
            container_id = (stdout.decode(errors='ignore') if stdout else "").strip()
            yield f"🐳 ENGINE INITIALIZED CONTAINER CONTAINER_ID: {container_id[:12]}\n\n"
            yield "🔌 ATTACHING TO CONTAINER LOG STREAM...\n\n"
            
            # Follow log streams natively in real-time chunk cycles
            log_stream = await follow_container_logs(CONTAINER_NAME)
            
            while True:
                if await request.is_disconnected():
                    break
                    
                line = await log_stream.stdout.readline()
                if not line:
                    break
                yield line.decode(errors='ignore')
                
            await log_stream.wait()
            
            # Pull check execution codes out of the dead runner container
            inspect_returncode, exit_code = await inspect_container_exit_code(CONTAINER_NAME)

            if inspect_returncode != 0 or "No such object" in exit_code:
                yield cleanup_race_success_eof()
            elif exit_code == "0":
                yield success_eof()
            else:
                yield failure_eof(exit_code)

        except Exception as ex:
            yield stream_exception_message(ex)
        finally:
            # Complete execution isolation. Kills runtime thread context on disconnect/exit
            remove_container(CONTAINER_NAME)

    return StreamingResponse(generate(), media_type="text/plain")
