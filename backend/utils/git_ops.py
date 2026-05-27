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
    """Generate repository architecture context."""
    tree = run_cmd('git ls-tree -r --name-only HEAD', cwd=repo_path)
    file_list = tree.split('\n')[:50]  # Limit to 50 files
    
    context = "# Project Structure\n"
    for f in file_list:
        if any(f.endswith(ext) for ext in ['.py', '.js', '.json', '.md', '.html', '.css']):
            context += f"- {f}\n"
    
    return context
