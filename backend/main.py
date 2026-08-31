import os
import time
import logging
import litellm
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import glob
from pathlib import Path
from backend.controllers.api import api_router
from backend.services.ledger_reader import fetch_ledger
from backend.services.db.reader import get_repos_grouped_by_org

def get_available_rubrics():
    rubrics = [Path(p).stem for p in glob.glob("rubrics/*.md")]
    return sorted([r for r in rubrics if r.upper() not in ("RUBRIC_AUTHORING_GUIDE", "README")])

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
async def index(request: Request, owner: str = None, repo: str = None, rubric: str = None):
    grouped = get_repos_grouped_by_org()
    available_rubrics = get_available_rubrics()
    ts = int(time.time())

    # 1. System Empty State (No DBs or Rubrics found)
    if not grouped or not available_rubrics:
        return templates.TemplateResponse(request=request, name="matrix.html", context={
            "repo": "system-setup", "chart_data": [], "table_data": [], "system_empty": True, "invalid_repo": False, "invalid_rubric": False,
            "time_autoclose": int(os.environ.get("MATRIX_TIME_AUTOCLOSE", "5")), "ts": ts
        })

    # Extract valid owners and repositories from the structured grouped dict
    organizations = grouped.get("organizations", [])
    owner_repo_map = {o["org"]: o["repos"] for o in organizations}
    available_owners = sorted(owner_repo_map.keys())
    
    # 1. Start with alphabetical defaults
    first_owner = available_owners[0] if available_owners else "unknown"
    first_repo = sorted(owner_repo_map[first_owner])[0] if available_owners and owner_repo_map[first_owner] else "unknown"
    first_rubric = available_rubrics[0] if available_rubrics else "unknown"

    # 2. Upgrade defaults to the first combo that actually has a scanned ledger
    import os
    found_scanned = False
    for o in available_owners:
        for r in sorted(owner_repo_map[o]):
            for rub in available_rubrics:
                if os.path.exists(f"data/{r}/db/{r}_ledger_{rub}.csv"):
                    first_owner, first_repo, first_rubric = o, r, rub
                    found_scanned = True
                    break
            if found_scanned: break
        if found_scanned: break

    def is_repo_valid(r_target, o_target):
        return r_target in owner_repo_map.get(o_target, [])

    # Auto-redirect to enforce ?owner=...&repo=...&rubric=... natively
    if not owner or not repo or not rubric:
        from fastapi.responses import RedirectResponse
        target_owner = owner if owner and owner in available_owners else first_owner
        
        # If owner is valid but requested repo isn't in that owner, fallback to owner's first repo
        target_repo = repo if repo and is_repo_valid(repo, target_owner) else (sorted(owner_repo_map[target_owner])[0] if target_owner in owner_repo_map and owner_repo_map[target_owner] else first_repo)
        target_rubric = rubric if rubric and rubric in available_rubrics else first_rubric
        
        return RedirectResponse(url=f"/?owner={target_owner}&repo={target_repo}&rubric={target_rubric}")

    invalid_owner = owner not in available_owners
    invalid_repo = not invalid_owner and not is_repo_valid(repo, owner)
    invalid_rubric = rubric not in available_rubrics

    # 2. Invalid Owner/Repo/Rubric in URL
    if invalid_owner or invalid_repo or invalid_rubric:
        return templates.TemplateResponse(request=request, name="matrix.html", context={
            "repo": repo, "chart_data": [], "table_data": [], "system_empty": False, "invalid_owner": invalid_owner, "invalid_repo": invalid_repo, "invalid_rubric": invalid_rubric,
            "time_autoclose": int(os.environ.get("MATRIX_TIME_AUTOCLOSE", "5")), "ts": ts
        })

    # 3. Normal Load
    ledger = fetch_ledger(repo, rubric=rubric)
    chart_data = [{k: v for k, v in c.items() if k not in ('s', 'h')} for c in ledger]
    table_data = ledger[:100]

    return templates.TemplateResponse(request=request, name="matrix.html", context={
        "repo": repo, "chart_data": chart_data, "table_data": table_data, "system_empty": False, "invalid_repo": False,
        "time_autoclose": int(os.environ.get("MATRIX_TIME_AUTOCLOSE", "5")), "ts": ts
    })
