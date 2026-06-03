"""Git repository operations."""
import subprocess

def run_cmd(cmd, cwd=None):
    """Run shell command and return output."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)
    return result.stdout.strip()

def get_commits(repo_path):
    """Get all commits with full details (default git order: newest -> oldest)."""
    cmd = 'git log --all --pretty=format:"%H|%ad|%an|%s" --date=format:"%b %d, \'%y" --numstat'
    return run_cmd(cmd, cwd=repo_path)

def get_commits_oldest_first(repo_path):
    """Get all commits with full details in oldest -> newest order."""
    cmd = 'git log --all --reverse --pretty=format:"%H|%ad|%an|%s" --date=format:"%b %d, \'%y" --numstat'
    return run_cmd(cmd, cwd=repo_path)

def get_commit_diff(commit_hash, repo_path):
    """Get diff for a specific commit."""
    cmd = f'git show {commit_hash} --pretty="" --unified=0'
    return run_cmd(cmd, cwd=repo_path)

def get_commit_meta(repo_path, commit_sha):
    """Get authored date, author, and subject for one commit."""
    cmd = f'git show -s --format="%H|%ad|%an|%s" --date=format:"%b %d, \'%y" {commit_sha}'
    out = run_cmd(cmd, cwd=repo_path)
    if not out or "|" not in out:
        return None
    parts = out.split("|", 3)
    if len(parts) != 4:
        return None
    return {
        "sha": parts[0].strip(),
        "date": parts[1].strip(),
        "author": parts[2].strip(),
        "subject": parts[3].strip(),
    }

def list_tree_files_at_commit(repo_path, commit_sha):
    """List tracked file paths at a historical commit via git plumbing."""
    cmd = f'git ls-tree -r --name-only {commit_sha}'
    out = run_cmd(cmd, cwd=repo_path)
    return [line.strip() for line in out.splitlines() if line.strip()]

def list_top_level_dirs_at_commit(repo_path, commit_sha):
    """List top-level directories at a historical commit via git plumbing."""
    cmd = f'git ls-tree --name-only -d {commit_sha}'
    out = run_cmd(cmd, cwd=repo_path)
    return sorted([line.strip() for line in out.splitlines() if line.strip()])

def read_file_at_commit(repo_path, commit_sha, rel_path):
    """Read a file's contents at a historical commit via git plumbing."""
    safe_rel = rel_path.replace('"', '\"')
    cmd = f'git show {commit_sha}:"{safe_rel}"'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=repo_path)
    if result.returncode != 0:
        return ""
    return result.stdout

def get_architecture_context(repo_path):
    """Load architecture context for scoring.

    Priority:
    1. Use the stored architecture blueprint (architecture.md) if available.
    2. Fall back to a flat git tree listing if no blueprint exists yet.
    """
    import os
    from pathlib import Path as _Path

    repo_name = os.environ.get("HOST_REPO_NAME") or _Path(repo_path).name or "repo"
    blueprint_path = _Path("/app/data") / repo_name / f"{repo_name}_arch_blueprint.md"

    if blueprint_path.exists():
        try:
            content = blueprint_path.read_text(encoding="utf-8").strip()
            if content:
                return content
        except Exception:
            pass

    tree = run_cmd('git ls-tree -r --name-only HEAD', cwd=repo_path)
    file_list = tree.split('\n')[:50]
    context = "# Project Structure (fallback)\n"
    for f in file_list:
        if any(f.endswith(ext) for ext in ['.py', '.js', '.json', '.md', '.html', '.css']):
            context += f"- {f}\n"
    return context

def get_architecture_context_for_commit(repo_path, commit_sha):
    """Build a fallback architecture context directly from a historical commit tree."""
    files = list_tree_files_at_commit(repo_path, commit_sha)[:50]
    context = f"# Project Structure at {commit_sha[:12]} (fallback)\n"
    for f in files:
        if any(f.endswith(ext) for ext in ['.py', '.js', '.json', '.md', '.html', '.css', '.yml', '.yaml', '.toml']):
            context += f"- {f}\n"
    return context
