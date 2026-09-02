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
    import subprocess
    safe_rel = rel_path.replace('"', '\"')
    cmd = f'git show {commit_sha}:"{safe_rel}"'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=repo_path)
    if result.returncode != 0:
        return ""
    return result.stdout

# --- Git remote URL -> human-readable Organization/Entity/Namespace heuristic ---
import re

_AZURE_VISUALSTUDIO = re.compile(r'^([\w-]+)\.visualstudio\.com$', re.I)
_IPV4 = re.compile(r'^\d{1,3}(\.\d{1,3}){3}$')

_FLAT_HOSTS = {
    'github.com', 'bitbucket.org', 'gitea.com', 'codeberg.org',
    'git.sr.ht', 'sr.ht', 'sourceforge.net', 'launchpad.net',
}

_INFRA_SUBS = {
    'git', 'cgit', 'code', 'gitlab', 'gitea', 'src', 'dev', 'svn', 'vcs',
    'source', 'gitbox', 'cvsweb', 'anongit', 'invent', 'salsa', 'www',
}

_NOISE = {'git', 'src', 'tree', 'blob', 'repos', 'pub', 'scm'}


def _strip_port(host_and_rest: str) -> str:
    m = re.match(r'^([^/:]+):(\d{1,5})(/.*|$)', host_and_rest)
    return (m.group(1) + m.group(3)) if m else host_and_rest


def extract_owner_from_remote_url(url: str) -> str:
    """Extract a human-readable org/entity/namespace name from a git remote URL."""
    u = url.strip()
    u = re.sub(r'[?#].*$', '', u)
    u = re.sub(r'^(?:https?://|ssh://|git://|file://)?(?:[^@\s/]+@)?', '', u)
    u = re.sub(r'\.git/?$', '', u)
    u = u.rstrip('/')

    if ':' in u.split('/', 1)[0]:
        host, _, rest = u.partition(':')
        if re.match(r'^\d{1,5}$', rest.split('/', 1)[0]):
            u = _strip_port(host + ':' + rest)
        else:
            u = host + '/' + rest
    else:
        u = _strip_port(u)

    pts = [p for p in u.split('/') if p]
    if not pts:
        return "Unknown"

    host = pts[0].lower()

    if host in ('vs-ssh.visualstudio.com', 'ssh.dev.azure.com') and 'v3' in pts:
        idx = pts.index('v3')
        if idx + 1 < len(pts):
            return pts[idx + 1]

    m = _AZURE_VISUALSTUDIO.match(host)
    if m:
        return m.group(1)

    if '_git' in pts:
        idx = pts.index('_git')
        if idx >= 2:
            return pts[idx - 2]

    owner_name = None
    if len(pts) >= 3:
        if host in _FLAT_HOSTS:
            owner_name = pts[-2]
        else:
            offset = 2
            while offset < len(pts) and pts[-offset] in _NOISE:
                offset += 1
            owner_name = pts[-offset] if offset < len(pts) else host
    else:
        owner_name = pts[0]

    if '.' in owner_name:
        if _IPV4.match(owner_name):
            return owner_name
        dom_parts = owner_name.split('.')
        while len(dom_parts) > 1 and dom_parts[0].lower() in _INFRA_SUBS:
            dom_parts = dom_parts[1:]
        owner_name = dom_parts[0] if dom_parts else owner_name

    return owner_name
