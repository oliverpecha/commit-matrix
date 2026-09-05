__version__ = "0.1.2"
import os
from backend.utils.git_ops import get_commits, get_commit_diff, extract_owner_from_remote_url

QUEUE_ORDER = os.environ.get("MATRIX_QUEUE_ORDER", "retrospective").strip().lower()

def get_locked_branch(repo_path, repo_name):
    import sqlite3, subprocess, os
    registry_db = "/app/data/registry.db" if os.path.exists("/.dockerenv") else "data/registry.db" 
    try:
        with sqlite3.connect(registry_db) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS repositories (repo_name TEXT PRIMARY KEY, owner TEXT, remote_url TEXT, target_branch TEXT, repo_path TEXT, root_commit TEXT, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
            row = conn.execute("SELECT target_branch FROM repositories WHERE repo_name=?", (repo_name,)).fetchone()
            if row and row[0]:
                return row[0]
            
            if subprocess.run("git show-ref --verify refs/heads/main", shell=True, cwd=repo_path, capture_output=True).returncode == 0:
                branch = "main"
            elif subprocess.run("git show-ref --verify refs/heads/master", shell=True, cwd=repo_path, capture_output=True).returncode == 0:
                branch = "master"
            else:
                branch = subprocess.run("git rev-parse --abbrev-ref HEAD", shell=True, cwd=repo_path, capture_output=True, text=True).stdout.strip() or "HEAD"
            
            conn.execute("INSERT OR IGNORE INTO repositories (repo_name) VALUES (?)", (repo_name,))
            conn.execute("UPDATE repositories SET target_branch=? WHERE repo_name=?", (branch, repo_name))
            return branch
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as e:
        print(f"⚠️ Registry branch resolution failed: {e}", flush=True)
    return "HEAD"

def build_topo_index(repo_path):
    topo = {}
    repo_name = os.environ.get("HOST_REPO_NAME", os.path.basename(repo_path))
    locked_branch = get_locked_branch(repo_path, repo_name)
    log_output = get_commits(repo_path, locked_branch)
    lines = [line for line in log_output.strip().split('\n') if '|' in line]
    lines.reverse()
    for idx, line in enumerate(lines, start=1):
        hash_full = line.split('|')[0].strip()
        topo[hash_full[:7]] = idx
    return topo

def discover_unscanned_commits(repo_path, existing_hashes):
    repo_name = os.environ.get("HOST_REPO_NAME", os.path.basename(repo_path))
    locked_branch = get_locked_branch(repo_path, repo_name)
    log_output = get_commits(repo_path, locked_branch)
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
    except (KeyboardInterrupt, SystemExit):
        raise
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

def sync_central_registry(db_path: str, repo_path: str):
    """Extracts repository identity and syncs it to the Central Registry."""
    import sqlite3, re, subprocess, os
    try:
        repo_name = os.environ.get("HOST_REPO_NAME", os.path.basename(repo_path))
        registry_db = "/app/data/registry.db" if os.path.exists("/.dockerenv") else "data/registry.db" 
        owner_name, raw_url = "Unknown", "Unknown"
        
        conf_path = os.path.join(repo_path, ".git", "config")
        if os.path.exists(conf_path):
            with open(conf_path, "r", errors="ignore") as f:
                m = re.search(r'url\s*=\s*(.+)', f.read())
                if m:
                    raw_url = m.group(1).strip()
                    owner_name = extract_owner_from_remote_url(raw_url)

        actual_host_path = os.environ.get("HOST_REPO_PATH", str(os.path.abspath(repo_path)))
        root_commit = subprocess.run("git rev-list --max-parents=0 HEAD", shell=True, cwd=repo_path, capture_output=True, text=True).stdout.strip().split('\n')[0]
        
        with sqlite3.connect(registry_db) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS repositories (repo_name TEXT PRIMARY KEY, owner TEXT, remote_url TEXT, target_branch TEXT, repo_path TEXT, root_commit TEXT, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
            conn.execute("INSERT OR IGNORE INTO repositories (repo_name) VALUES (?)", (repo_name,))
            conn.execute(
                "UPDATE repositories SET owner=?, remote_url=?, repo_path=?, root_commit=?, updated_at=CURRENT_TIMESTAMP WHERE repo_name=?",
                (owner_name, raw_url, actual_host_path, root_commit, repo_name)
            )
            
        get_locked_branch(repo_path, repo_name)
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as e:
        print(f"⚠️ Registry sync failed: {e}", flush=True)
