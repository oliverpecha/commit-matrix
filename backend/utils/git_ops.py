"""Git repository operations."""
import subprocess

def run_cmd(cmd, cwd=None):
    """Run shell command and return output."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)
    return result.stdout.strip()

def get_commits(repo_path, target_branch="HEAD"):
    """Get commits strictly from the DB-locked branch."""
    cmd = f'git log {target_branch} --pretty=format:"%H|%ad|%an|%s" --date=format:"%b %d, \'%y" --numstat'
    return run_cmd(cmd, cwd=repo_path)

def get_commit_diff(commit_hash, repo_path):
    """Get diff for a specific commit."""
    cmd = f'git show {commit_hash} --pretty="" --unified=0'
    return run_cmd(cmd, cwd=repo_path)

EXCLUDED_FILE_PATTERNS = [
    r'package-lock\.json$', r'yarn\.lock$', r'pnpm-lock\.yaml$',
    r'Cargo\.lock$', r'poetry\.lock$', r'Pipfile\.lock$',
    r'vendor/', r'node_modules/', r'\.min\.(js|css)$',
    r'\.map$', r'\.svg$', r'\.png$', r'\.jpg$'
]

def score_file_risk(filename: str) -> int:
    fn = filename.lower()
    if any(k in fn for k in ["migration", "schema", "auth", "security", "permission", "deploy", "ci", ".github/workflows"]):
        return 100
    if any(fn.endswith(ext) for ext in [".py", ".ts", ".js", ".go", ".rs", ".sql"]):
        return 50
    if any(k in fn for k in ["test", "spec", "fixture", "mock"]):
        return 20
    if any(fn.endswith(ext) for ext in [".md", ".txt", ".rst", ".doc"]):
        return 10
    return 30

def parse_diff_files(diff_text: str):
    raw_files = diff_text.split("diff --git ")
    parsed = []
    for chunk in raw_files:
        if not chunk.strip():
            continue
        lines = chunk.splitlines()
        first_line = lines[0]
        pts = first_line.split(" ")
        raw_name = pts[-1] if len(pts) >= 2 else "unknown"
        filename = raw_name[2:] if raw_name.startswith("b/") else raw_name
        parsed.append({"filename": filename, "content": "diff --git " + chunk})
    return parsed

def budget_commit_diff(diff_text: str, max_chars: int = 8000) -> tuple[str, dict]:
    """B3/B4/B5 Diff budgeter prioritizing high-risk hunks and emitting coverage manifest."""
    files = parse_diff_files(diff_text)
    if not files:
        return diff_text[:max_chars], {"included_files": [], "excluded_files": [], "truncated_files": []}

    included = []
    excluded = []
    truncated = []

    eligible = []
    for f in files:
        fn = f["filename"]
        if any(re.search(pat, fn, re.IGNORECASE) for pat in EXCLUDED_FILE_PATTERNS):
            excluded.append(fn)
        else:
            eligible.append(f)

    # Sort files by risk score descending
    eligible.sort(key=lambda x: score_file_risk(x["filename"]), reverse=True)

    result_chunks = []
    current_len = 0
    trunc_marker = chr(10) * 2 + "... [TRUNCATED HUNKS RETAINED HEAD+TAIL] ..." + chr(10) * 2

    for f in eligible:
        fn = f["filename"]
        content = f["content"]
        if current_len + len(content) <= max_chars:
            result_chunks.append(content)
            current_len += len(content)
            included.append(fn)
        else:
            remaining = max_chars - current_len
            if remaining > 300:
                half = remaining // 2
                head = content[:half]
                tail = content[-half:]
                hunk = head + trunc_marker + tail
                result_chunks.append(hunk)
                current_len += len(hunk)
                truncated.append(fn)
            else:
                excluded.append(fn)

    manifest = {
        "included_files": included,
        "excluded_files": excluded,
        "truncated_files": truncated
    }
    return chr(10).join(result_chunks), manifest

def sanitize_injection_delimiters(val: str) -> str:
    """B8 Prompt injection defense: sanitize raw text boundary markers."""
    if not val:
        return ""
    markers = [
        "=== COMMIT_DATA_START ===", "=== COMMIT_DATA_END ===",
        "=== SYSTEM_INSTRUCTION_OVERRIDE ===", "<|im_start|>", "<|im_end|>"
    ]
    cleaned = str(val)
    for m in markers:
        cleaned = cleaned.replace(m, f"[ESCAPED_TOKEN:{m}]")
    return cleaned

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
import os

_FLAT_HOSTS = {
    'github.com', 'bitbucket.org', 'gitea.com', 'codeberg.org',
    'git.sr.ht', 'sr.ht', 'sourceforge.net', 'launchpad.net', 'gitlab.com'
}

_INFRA_SUBS = {
    'git', 'cgit', 'code', 'gitlab', 'gitea', 'src', 'dev', 'svn', 'vcs',
    'source', 'gitbox', 'cvsweb', 'anongit', 'invent', 'salsa', 'www',
}

_AZURE_VISUALSTUDIO = re.compile(r'^([\w-]+)\.visualstudio\.com$', re.I)
_IPV4 = re.compile(r'^\d{1,3}(\.\d{1,3}){3}$')

_SUFFIXES = set()
def _load_suffixes():
    if _SUFFIXES: return
    p = os.path.join(os.path.dirname(__file__), "public_suffix_list.txt")
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                l = line.split("//")[0].strip()
                if l and not l.startswith("!") and not l.startswith("*"):
                    _SUFFIXES.add(l.lower())

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

    # 1. SSH Alias Block
    if ':' in u and '/' not in u.split(':', 1)[0]:
        host = u.split(':', 1)[0]
        if '.' not in host and host != 'localhost':
            return host

    if ':' in u.split('/', 1)[0]:
        host, _, rest = u.partition(':')
        if re.match(r'^\d{1,5}$', rest.split('/', 1)[0]):
            u = _strip_port(host + ':' + rest)
        else:
            u = host + '/' + rest
    else:
        u = _strip_port(u)

    pts = [p for p in u.split('/') if p]
    if not pts: return "Unknown"
    host = pts[0].lower()

    # 2. Cloud Signatures (AWS, GCP, Azure)
    if host.endswith('.amazonaws.com') and host.startswith('git-codecommit'):
        return 'aws'
    if host == 'source.developers.google.com' and len(pts) >= 3 and pts[1] == 'p':
        return pts[2]
    if host == 'dev.azure.com' and len(pts) >= 2:
        return pts[1]
    if host in ('vs-ssh.visualstudio.com', 'ssh.dev.azure.com') and 'v3' in pts:
        idx = pts.index('v3')
        if idx + 1 < len(pts):
            return pts[idx + 1]
    m = _AZURE_VISUALSTUDIO.match(host)
    if m: return m.group(1)

    # 3. Flat Host Path Resolution
    if host in _FLAT_HOSTS:
        return pts[1] if len(pts) > 1 else host

    # 4. Native Domain Parsing with Suffix List
    if '.' in host and not _IPV4.match(host):
        dom_parts = host.split('.')
        
        # Scrub infrastructure left-side logic
        while len(dom_parts) > 2 and dom_parts[0] in _INFRA_SUBS:
            dom_parts.pop(0)

        _load_suffixes()
        if _SUFFIXES:
            for i in range(len(dom_parts)):
                if ".".join(dom_parts[i:]) in _SUFFIXES:
                    return dom_parts[i-1] if i > 0 else dom_parts[0]

        # Ultimate fail-safe if txt file is missing
        if len(dom_parts) >= 2:
            return dom_parts[-2]

    return pts[0]
