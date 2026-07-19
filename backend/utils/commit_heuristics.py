from typing import Dict, Any

def extract_heuristics(subject: str, diff: str) -> Dict[str, Any]:
    commit_type, commit_scope = "commit", ""
    if subject.startswith("feat"):
        commit_type = "feat"
        commit_scope = subject.split("(")[1].split(")")[0] if "(" in subject else "core"
    elif subject.startswith("fix"):
        commit_type = "fix"
        commit_scope = subject.split("(")[1].split(")")[0] if "(" in subject else "core"
    elif subject.startswith("chore"):
        commit_type = "chore"
        commit_scope = subject.split("(")[1].split(")")[0] if "(" in subject else ""

    additions = diff.count("\n+") - diff.count("\n+++")
    deletions = diff.count("\n-") - diff.count("\n---")

    diff_lower = diff.lower()
    scope_tags = []
    if any(x in diff_lower for x in ("backend/parser.py", "backend/main.py", "dockerfile")): scope_tags.append("scripts")
    if ".json" in diff_lower or "config" in diff_lower: scope_tags.append("config")
    if "dashboard" in diff_lower or "index.html" in diff_lower: scope_tags.append("dashboard")
    if "readme" in diff_lower or ".md" in diff_lower: scope_tags.append("docs")
    if "metrics" in diff_lower: scope_tags.append("metrics")

    return {
        "type": commit_type,
        "scope": commit_scope,
        "tags": ", ".join(scope_tags) if scope_tags else "None",
        "additions": f"+{additions}",
        "deletions": f"-{deletions}"
    }
