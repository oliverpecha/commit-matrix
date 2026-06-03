"""Git repository operations."""
import subprocess

def run_cmd(cmd, cwd=None):
    """Run shell command and return output."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)
    return result.stdout.strip()

def get_commits(repo_path):
    """Get all commits with full details."""
    cmd = 'git log --all --pretty=format:"%H|%ad|%an|%s" --date=format:"%b %d, \'%y" --numstat'
    return run_cmd(cmd, cwd=repo_path)

def get_commit_diff(commit_hash, repo_path):
    """Get diff for a specific commit."""
    cmd = f'git show {commit_hash} --pretty="" --unified=0'
    return run_cmd(cmd, cwd=repo_path)

def get_architecture_context(repo_path):
    """Load architecture context for scoring.

    Priority:
    1. Use the stored architecture blueprint (architecture.md) if available.
    2. Fall back to a flat git tree listing if no blueprint exists yet.
    """
    import os
    from pathlib import Path as _Path

    repo_name = os.environ.get("HOST_REPO_NAME") or _Path(repo_path).name or "repo"
    blueprint_path = _Path("/app/data") / repo_name / f"{repo_name}_architecture.md"

    # Primary: architecture blueprint managed by architecture_generator
    if blueprint_path.exists():
        try:
            content = blueprint_path.read_text(encoding="utf-8").strip()
            if content:
                return content
        except Exception:
            pass

    # Fallback: flat git tree (legacy behavior)
    tree = run_cmd('git ls-tree -r --name-only HEAD', cwd=repo_path)
    file_list = tree.split('\n')[:50]
    context = "# Project Structure (fallback)\n"
    for f in file_list:
        if any(f.endswith(ext) for ext in ['.py', '.js', '.json', '.md', '.html', '.css']):
            context += f"- {f}\n"
    return context
