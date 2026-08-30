import os
import time
import logging
import litellm
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from backend.controllers.api import api_router
from backend.services.ledger_reader import fetch_ledger
from backend.services.db.reader import get_available_repos

# --- LITELM LOGGING SWITCH ---
if str(os.environ.get("MATRIX_DEBUG", "false")).strip().lower() in ("1", "true", "yes", "on"):
    litellm.suppress_debug_info = False
    logging.getLogger("LiteLLM").setLevel(logging.DEBUG)
else:
    litellm.suppress_debug_info = True
    logging.getLogger("LiteLLM").setLevel(logging.ERROR)

app = FastAPI(title="CommitMatrix Core Engine")

# Static assets & Templates
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")
templates = Jinja2Templates(directory="frontend/templates")

# Register Dedicated API Router
app.include_router(api_router)


@app.middleware("http")
async def prevent_browser_caching(request: Request, call_next):
    response = await call_next(request)
    if "static" not in request.url.path:
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


@app.get("/")
async def index(request: Request, repo: str = None):
    available_repos = get_available_repos()
    ts = int(time.time())

    # 1. System Empty State (No DBs at all)
    if not available_repos:
        return templates.TemplateResponse(request=request, name="matrix.html", context={
            "repo": "system-setup", "chart_data": [], "table_data": [], "system_empty": True, "invalid_repo": False,
            "time_autoclose": int(os.environ.get("MATRIX_TIME_AUTOCLOSE", "5")), "ts": ts
        })

    # 2. Invalid or Missing Repo in URL
    if not repo or repo not in available_repos:
        return templates.TemplateResponse(request=request, name="matrix.html", context={
            "repo": repo if repo else "", "chart_data": [], "table_data": [], "system_empty": False, "invalid_repo": True,
            "time_autoclose": int(os.environ.get("MATRIX_TIME_AUTOCLOSE", "5")), "ts": ts
        })

    # 3. Normal Load
    ledger = fetch_ledger(repo)
    chart_data = [{k: v for k, v in c.items() if k not in ('s', 'h')} for c in ledger]
    table_data = ledger[:100]

    return templates.TemplateResponse(request=request, name="matrix.html", context={
        "repo": repo, "chart_data": chart_data, "table_data": table_data, "system_empty": False, "invalid_repo": False,
        "time_autoclose": int(os.environ.get("MATRIX_TIME_AUTOCLOSE", "5")), "ts": ts
    })
