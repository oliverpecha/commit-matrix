import glob
import os
import sqlite3
from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse, JSONResponse

from backend.services.db.reader import get_repos_grouped_by_owner, get_available_repos
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
    return JSONResponse(content=get_repos_grouped_by_owner())


@api_router.get("/rubrics")
async def list_rubrics(repo: str = None, owner: str = None):
    from backend.services.db.reader import get_available_repos
    
    if not repo:
        repos = get_available_repos()
        if repos:
            repo = repos[0]
            
    active_rubrics = set()
    if repo:
        for path in (glob.glob(f"data/{owner}/{repo}/db/{repo}_ledger_*.csv") + glob.glob(f"data/*/{repo}/db/{repo}_ledger_*.csv") + glob.glob(f"data/{repo}/db/{repo}_ledger_*.csv")):
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
        
    # Hardcoded cirsd fallback removed

    # Bulletproof sorting using .get() to prevent ANY KeyError crashes
    rubrics.sort(key=lambda x: (not x.get("has_data", False), x.get("name", "")))
        
    from fastapi.responses import JSONResponse
    return JSONResponse(content={"rubrics": rubrics})


@api_router.get("/data")
async def get_data(repo: str = None, rubric: str = None, token: str = "", owner: str = None, force: bool = False):
    available_repos = get_available_repos()
    if not repo or repo not in available_repos:
        return JSONResponse(content=[])
    
    if not owner:
        db_paths = glob.glob(f"data/*/{repo}/db/{repo}.db")
        owner = Path(db_paths[0]).parts[1] if db_paths else None
        
    return JSONResponse(content=fetch_ledger(repo, rubric, owner, force=force))


@api_router.post("/engine/control")
async def control_engine(request: Request, action: str, repo: str = "commit-matrix", rubric: str = None, owner: str = None):
    if action == "pause":
        return JSONResponse(content=pause_container(repo, rubric, owner))
    elif action == "play":
        return JSONResponse(content=unpause_container(repo, rubric, owner))
    elif action == "stop":
        force_remove_container(repo, rubric, owner)
        return JSONResponse(content={"status": "stopped", "action": "stop", "repo": repo})
    return JSONResponse(content={"status": "acknowledged", "action": action, "repo": repo})


def _registry_path():
    return "/app/data/registry.db" if os.path.exists("/.dockerenv") else "data/registry.db"

def _native_heartbeat(repo: str, rubric: str = None, owner: str = None):
    conn = None
    try:
        conn = sqlite3.connect(_registry_path(), timeout=5.0)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(repositories)").fetchall()}
        if "exec_mode" not in cols:
            return None
        row = conn.execute(
            "SELECT active_log_path, exec_mode FROM repositories WHERE repo_name=?",
            (repo,),
        ).fetchone()
        if not row or row[1] != "native" or not row[0]:
            return None
        log_path = row[0]
        if not os.path.exists(log_path):
            conn.execute(
                "UPDATE repositories SET active_container_id=NULL, active_log_path=NULL, exec_mode=NULL WHERE repo_name=?",
                (repo,),
            )
            conn.commit()
            return None
        return {"log_path": log_path}
    except Exception:
        return None
    finally:
        if conn:
            conn.close()

@api_router.get("/engine/status")
async def get_engine_status(repo: str, rubric: str = None, owner: str = None):
    from backend.services.docker_runtime import is_container_running
    if is_container_running(repo, rubric, owner):
        return JSONResponse(content={"running": True, "mode": "docker"})

    native = _native_heartbeat(repo, rubric, owner)
    if native:
        return JSONResponse(content={"running": True, "mode": "native", "log_path": native["log_path"]})

    return JSONResponse(content={"running": False})

@api_router.post("/engine/tail")
@api_router.get("/engine/tail")
async def tail_native_log(request: Request, repo: str, rubric: str = None, owner: str = None):
    native = _native_heartbeat(repo, rubric, owner)
    if not native or not native.get("log_path") or not os.path.exists(native["log_path"]):
        async def empty(): yield "💥 NO ACTIVE NATIVE RUN DETECTED.\n[__MATRIX_EOF_FAIL__]"
        return StreamingResponse(empty(), media_type="text/plain")

    async def generate():
        import asyncio, os
        yield "🐚 ATTACHED TO NATIVE TERMINAL\n\n"
        log_path = native["log_path"]
        with open(log_path, 'r') as f:
            while True:
                if await request.is_disconnected(): break
                line = f.readline()
                if line: yield line
                else:
                    if not _native_heartbeat(repo, rubric, owner):
                        yield "\n[__MATRIX_EOF_SUCCESS__]"
                        break
                    await asyncio.sleep(0.5)
    return StreamingResponse(generate(), media_type="text/plain")



@api_router.post("/scan")
async def stream_scan(request: Request, repo: str = "commit-matrix", rubric: str = None, token: str = "", owner: str = None):
    available_repos = get_available_repos()

    async def generate():
        if not repo:
            yield f"⚠️ SCAN REJECTED: Repository '{repo}' is not registered or found in data directory.\n\n"
            yield failure_eof("INVALID_REPOSITORY")
            return

        yield "🤖 CONNECTED TO DOCKER ENGINE DAEMON.\n\n"

        from backend.services.docker_runtime import is_container_running
        is_running = is_container_running(repo, rubric, owner)
        should_cleanup = True

        if is_running:
            yield "🐳 ACTIVE CONTAINER DETECTED. ATTACHING TO EXISTING LOG STREAM...\n\n"
            should_cleanup = False
        else:
            force_remove_container(repo, rubric, owner)
            docker_cmd = build_scan_docker_cmd(repo=repo, rubric=rubric, owner=owner)

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
                
                import asyncio, os
                await asyncio.sleep(0.5)
                if not is_container_running(repo, rubric, owner):
                    try:
                        import subprocess
                        crash_logs = subprocess.check_output(['docker', 'logs', container_id], stderr=subprocess.STDOUT, timeout=3).decode(errors='ignore')
                        yield f"💥 CONTAINER CRASHED BEFORE ATTACH. LAST LOGS:\n{crash_logs}\n"
                    except Exception:
                        yield "💥 CONTAINER EXITED IMMEDIATELY. NO LOGS FOUND.\n"
                    yield failure_eof("EARLY_CRASH")
                    return
            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception as ex:
                yield stream_exception_message(ex)
                return

        try:
            log_stream = await follow_container_logs(repo, rubric, owner)

            while True:
                if await request.is_disconnected():
                    should_cleanup = False
                    break

                line = await log_stream.stdout.readline()
                if not line:
                    break
                yield line.decode(errors='ignore')

            if not await request.is_disconnected():
                await log_stream.wait()
                inspect_returncode, exit_code = await inspect_container_exit_code(repo, rubric, owner)

                if inspect_returncode != 0 or "No such object" in exit_code:
                    yield cleanup_race_success_eof()
                elif str(exit_code) in ("130", "137", "143"):
                    yield "\n🛑 Scan gracefully halted by user.\n[__MATRIX_EOF_FAIL__]"
                elif exit_code == "0":
                    from backend.services.ledger_reader import _CACHE
                    cache_key = f"{repo}_{rubric}"
                    if cache_key in _CACHE:
                        del _CACHE[cache_key]
                    yield success_eof()
                else:
                    yield failure_eof(exit_code)

        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as ex:
            yield stream_exception_message(ex)
        finally:
            if should_cleanup:
                remove_container(repo, rubric, owner)

    return StreamingResponse(generate(), media_type="text/plain")


@api_router.get("/rubrics/guide")
async def get_rubric_guide():
    guide_path = Path("rubrics/RUBRIC_AUTHORING_GUIDE.md")
    if guide_path.exists():
        return JSONResponse(content={"title": "RUBRIC_AUTHORING_GUIDE.md", "content": guide_path.read_text(encoding="utf-8")})
    return JSONResponse(content={"title": "Rubric Guide", "content": "# Rubric Authoring Guide\n\nGuide file not found on disk."})


@api_router.get("/ledger")
async def get_ledger_paginated(repo: str, rubric: str, offset: int = 0, limit: int = 100, owner: str = None):
    available_repos = get_available_repos()
    if not repo or repo not in available_repos:
        return JSONResponse(content=[])
    
    if not owner:
        db_paths = glob.glob(f"data/*/{repo}/db/{repo}.db")
        owner = Path(db_paths[0]).parts[1] if db_paths else None
        
    ledger = fetch_ledger(repo, rubric, owner)
    paginated_chunk = ledger[offset : offset + limit]
    return JSONResponse(content=paginated_chunk)


