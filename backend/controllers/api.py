import glob
from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse, JSONResponse

from backend.services.db.reader import get_repos_grouped_by_org, get_available_repos
from backend.services.ledger_reader import fetch_ledger
from backend.services.docker_runtime import (
    build_scan_docker_cmd,
    follow_container_logs,
    force_remove_container,
    inspect_container_exit_code,
    pause_container,
    remove_container,
    run_docker_detached,
    unpause_container,
)
from backend.utils.scan_outcome import (
    cleanup_race_success_eof,
    docker_invocation_failed,
    failure_eof,
    stream_exception_message,
    success_eof,
)

api_router = APIRouter(prefix="/api")


@api_router.get("/repos")
async def list_repos():
    return JSONResponse(content=get_repos_grouped_by_org())


@api_router.get("/rubrics")
async def list_rubrics(repo: str = None):
    import glob
    from pathlib import Path
    from backend.services.db.reader import get_available_repos
    
    if not repo:
        repos = get_available_repos()
        if repos:
            repo = repos[0]
            
    active_rubrics = set()
    if repo:
        for path in glob.glob(f"data/{repo}/db/{repo}_ledger_*.csv"):
            filename = Path(path).stem
            prefix = f"{repo}_ledger_"
            if filename.startswith(prefix):
                active_rubrics.add(filename[len(prefix):].lower())

    rubrics = []
    for path in glob.glob("rubrics/*.md"):
        name = Path(path).stem
        rubrics.append({
            "id": name, 
            "name": name.upper(),
            "has_data": name.lower() in active_rubrics
        })
        
    if not rubrics:
        rubrics = [{"id": "cirsd", "name": "CIRSD V1", "has_data": "cirsd" in active_rubrics}]

    # Bulletproof sorting using .get() to prevent ANY KeyError crashes
    rubrics.sort(key=lambda x: (not x.get("has_data", False), x.get("name", "")))
        
    from fastapi.responses import JSONResponse
    return JSONResponse(content={"rubrics": rubrics})


@api_router.get("/data")
async def get_data(repo: str = None, rubric: str = "cirsd", token: str = ""):
    available_repos = get_available_repos()
    if not repo or repo not in available_repos:
        return JSONResponse(content=[])
    return JSONResponse(content=fetch_ledger(repo, rubric))


@api_router.post("/engine/control")
async def control_engine(request: Request, action: str, repo: str = "commit-matrix", rubric: str = "cirsd"):
    if action == "pause":
        return JSONResponse(content=pause_container(repo))
    elif action == "play":
        return JSONResponse(content=unpause_container(repo))
    elif action == "stop":
        force_remove_container(repo, rubric)
        return JSONResponse(content={"status": "stopped", "action": "stop", "repo": repo})
    return JSONResponse(content={"status": "acknowledged", "action": action, "repo": repo})

@api_router.get("/engine/status")
async def get_engine_status(repo: str, rubric: str = "cirsd"):
    from backend.services.docker_runtime import get_container_name
    import subprocess
    c_name = get_container_name(repo, rubric)
    try:
        res = subprocess.check_output(f"docker ps -q -f name=^{c_name}$", shell=True).strip()
        return JSONResponse(content={"running": bool(res)})
    except Exception:
        return JSONResponse(content={"running": False})



@api_router.post("/scan")
async def stream_scan(request: Request, repo: str = "commit-matrix", rubric: str = "cirsd", token: str = ""):
    available_repos = get_available_repos()
    
    async def generate():
        if not repo or repo not in available_repos:
            yield f"⚠️ SCAN REJECTED: Repository '{repo}' is not registered or found in data directory.\n\n"
            yield failure_eof("INVALID_REPOSITORY")
            return

        yield "🤖 CONNECTED TO DOCKER ENGINE DAEMON.\n\n"
        
        force_remove_container(repo)
        docker_cmd = build_scan_docker_cmd(repo=repo, rubric=rubric)
        
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
            
            log_stream = await follow_container_logs(repo)
            
            while True:
                if await request.is_disconnected():
                    break
                    
                line = await log_stream.stdout.readline()
                if not line:
                    break
                yield line.decode(errors='ignore')
                
            await log_stream.wait()
            
            inspect_returncode, exit_code = await inspect_container_exit_code(repo)

            if inspect_returncode != 0 or "No such object" in exit_code:
                yield cleanup_race_success_eof()
            elif exit_code == "0":
                from backend.services.ledger_reader import _CACHE
                cache_key = f"{repo}_{rubric}"
                if cache_key in _CACHE:
                    del _CACHE[cache_key]
                yield success_eof()
            else:
                yield failure_eof(exit_code)

        except Exception as ex:
            yield stream_exception_message(ex)
        finally:
            remove_container(repo)

    return StreamingResponse(generate(), media_type="text/plain")


@api_router.get("/rubrics/guide")
async def get_rubric_guide():
    guide_path = Path("rubrics/RUBRIC_AUTHORING_GUIDE.md")
    if guide_path.exists():
        return JSONResponse(content={"title": "RUBRIC_AUTHORING_GUIDE.md", "content": guide_path.read_text(encoding="utf-8")})
    return JSONResponse(content={"title": "Rubric Guide", "content": "# Rubric Authoring Guide\n\nGuide file not found on disk."})


@api_router.get("/ledger")
async def get_ledger_paginated(repo: str, rubric: str = "cirsd", offset: int = 0, limit: int = 100):
    available_repos = get_available_repos()
    if not repo or repo not in available_repos:
        return JSONResponse(content=[])
    
    ledger = fetch_ledger(repo, rubric)
    paginated_chunk = ledger[offset : offset + limit]
    return JSONResponse(content=paginated_chunk)
