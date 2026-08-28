import os
from backend.utils.git_ops import get_commits, get_commit_diff, extract_org_from_remote_url

QUEUE_ORDER = os.environ.get("MATRIX_QUEUE_ORDER", "retrospective").strip().lower()

def build_topo_index(repo_path):
    topo = {}
    log_output = get_commits(repo_path)
    lines = [line for line in log_output.strip().split('\n') if '|' in line]
    lines.reverse()
    for idx, line in enumerate(lines, start=1):
        hash_full = line.split('|')[0].strip()
        topo[hash_full[:7]] = idx
    return topo

def discover_unscanned_commits(repo_path, existing_hashes):
    log_output = get_commits(repo_path)
    lines = log_output.strip().split('\n')

    commits = []
    seen_unscanned = set()
    i = 0
    while i < len(lines):
        if '|' in lines[i]:
            parts = lines[i].split('|')
            hash_full = parts[0]
            hash_short = hash_full[:7]

            if hash_short not in existing_hashes and hash_short not in seen_unscanned:
                seen_unscanned.add(hash_short)
                diff = get_commit_diff(hash_full, repo_path)
                commits.append((hash_full, parts[1], parts[2], parts[3], diff))
            i += 1
        else:
            i += 1

    return commits

def build_commit_queue(repo_path, existing_hashes):
    topo_map = build_topo_index(repo_path)
    commits = discover_unscanned_commits(repo_path, existing_hashes)

    commits_with_ids = []
    for commit in commits:
        hash_full = commit[0]
        hash_short = hash_full[:7]
        topo_id = topo_map.get(hash_short)
        if topo_id is None:
            continue
        commits_with_ids.append((topo_id, commit))

    total_found = len(commits_with_ids)
    max_commits = int(os.environ.get('MATRIX_MAX_COMMITS', '0'))

    if QUEUE_ORDER == "chronological":
        commits_with_ids.sort(key=lambda x: x[0])
    elif QUEUE_ORDER == "retrospective":
        commits_with_ids.sort(key=lambda x: x[0], reverse=True)
    else:
        raise ValueError(f"Unsupported MATRIX_QUEUE_ORDER={QUEUE_ORDER!r}; expected 'chronological' or 'retrospective'")

    previous_tail = None
    try:
        from backend.services.db.reader import read_scan_range
        from backend.services.architecture.arch_storage import repo_id_from_path
        _repo_label = repo_id_from_path(repo_path)
        scan_range = read_scan_range(_repo_label)
        if scan_range:
            previous_tail = scan_range.get("scan_tail_topo")
    except Exception:
        pass

    if max_commits > 0 and len(commits_with_ids) > max_commits:
        limited = commits_with_ids[:max_commits]

        if previous_tail is not None and QUEUE_ORDER == "retrospective" and limited:
            last_topo = limited[-1][0]
            if last_topo > previous_tail:
                gap = last_topo - previous_tail
                grace_window = 5
                if 0 < gap <= grace_window:
                    extended = [c for c in commits_with_ids[max_commits:]
                                if c[0] >= previous_tail]
                    limited.extend(extended)

        commits_with_ids = limited

    return {
        "commits_with_ids": commits_with_ids,
        "total_found": total_found,
        "max_commits": max_commits,
        "total_unscanned": len(commits_with_ids),
        "previous_tail_topo": previous_tail,
    }

def bootstrap_repo_metadata(db_path: str, repo_path: str):
    """Extracts directory-agnostic metadata (like namespace/org) and syncs to DB."""
    import sqlite3
    import re
    
    try:
        with sqlite3.connect(db_path) as meta_conn:
            meta_conn.execute(
                "CREATE TABLE IF NOT EXISTS repo_metadata (key TEXT PRIMARY KEY, value TEXT, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
            )
            org_name = "Unknown"
            conf_path = os.path.join(repo_path, ".git", "config")

            if os.path.exists(conf_path):
                with open(conf_path, "r", errors="ignore") as f:
                    m = re.search(r'url\s*=\s*(.+)', f.read())
                    if m:
                        org_name = extract_org_from_remote_url(m.group(1).strip())

            meta_conn.execute("INSERT OR IGNORE INTO repo_metadata (key, value) VALUES ('org_name', ?)", (org_name,))
            if org_name != "Unknown":
                meta_conn.execute("UPDATE repo_metadata SET value = ? WHERE key = 'org_name'", (org_name,))
    except Exception as e:
        print(f"⚠️ Metadata extraction failed: {e}", flush=True)
