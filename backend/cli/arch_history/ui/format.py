import re
from backend.services.architecture.taxonomy import get_shape_metadata

SUBJECT_LIMIT = len("sync live stream sorting contract between backend timestamps and frontend UI mode")
COMPACT_SUBJECT_LIMIT = SUBJECT_LIMIT
COMPACT_OMISSION_LIMIT = 56

def truncate_subject(subject: str, limit: int = SUBJECT_LIMIT) -> str:
    subject = (subject or "").strip()
    if not subject:
        return "no subject"
    if len(subject) <= limit:
        return subject
    return subject[: max(0, limit - 3)].rstrip() + "..."

def fmt_subject(raw: str, limit: int = SUBJECT_LIMIT) -> str:
    s = (raw or "").strip()
    # Isolate only the primary row of hybrid commits to protect terminal layout borders
    s = s.splitlines()[0] if s else ""
    s = re.sub(r"^(?:[a-z]+\([^)]*\):\s*|[a-z]+:\s*)", "", s, count=1)
    return truncate_subject(s, limit=limit) if s else "no subject"

def _format_lifespan_date_span(first_date: str, last_date: str) -> str:
    first_date = (first_date or "").strip()
    last_date = (last_date or "").strip()
    if not first_date:
        return last_date or "unknown"
    if not last_date or last_date == first_date:
        return first_date
    return f"{first_date}–{last_date}"

def shape_icon(shape: str) -> str:
    return get_shape_metadata(shape)["icon"]

def _shape_icon_fallback(shape: str) -> str:
    return get_shape_metadata(shape)["icon"]

def _operational_kind(subject: str) -> str:
    s = (subject or "").strip()
    if s.startswith("index on "):
        return "stash/index"
    if s.startswith("WIP on "):
        return "stash/wip"
    if "RECOVERY BASELINE" in s:
        return "recovery"
    if s.startswith("On ") and ": " in s:
        return "operational"
    return ""

def _is_operational_ref(ref) -> bool:
    s = (ref.subject or "").strip()
    return bool(
        s.startswith("index on ")
        or s.startswith("WIP on ")
        or ("RECOVERY BASELINE" in s)
        or (s.startswith("On ") and ": " in s)
    )
