import os

from utils.git_ops import get_commits, get_commit_diff


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
    seen_topo = set()
    for commit in commits:
        hash_full = commit[0]
        hash_short = hash_full[:7]
        topo_id = topo_map.get(hash_short)
        if topo_id is None or topo_id in seen_topo:
            continue
        seen_topo.add(topo_id)
        commits_with_ids.append((topo_id, commit))

    commits_with_ids.sort(key=lambda x: x[0], reverse=True)

    total_found = len(commits_with_ids)
    max_commits = int(os.environ.get('MATRIX_MAX_COMMITS', '0'))
    if max_commits > 0 and len(commits_with_ids) > max_commits:
        commits_with_ids = commits_with_ids[:max_commits]

    return {
        "commits_with_ids": commits_with_ids,
        "total_found": total_found,
        "max_commits": max_commits,
        "total_unscanned": len(commits_with_ids),
    }
