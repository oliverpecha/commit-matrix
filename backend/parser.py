import os, sys, json, argparse, subprocess, csv
from datetime import datetime
from litellm import completion

parser = argparse.ArgumentParser(description="CommitMatrix LLM Parser")
parser.add_argument("--repo", type=str, default=os.getcwd(), help="Absolute path to the target git repository")
parser.add_argument("--remap", action="store_true", help="Force a repository architecture re-map")
parser.add_argument("--rubric", type=str, default=os.path.join(os.getcwd(), "backend", "rubrics", "cirsd.md"), help="Path to the scoring rubric file")
args = parser.parse_args()

MODEL_NAME = "gemini/gemini-3.1-pro"
REPO_PATH = os.path.abspath(args.repo)

def run_cmd(cmd):
    try: return subprocess.run(cmd, cwd=REPO_PATH, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True).stdout.strip()
    except subprocess.CalledProcessError: return ""

def get_project_identifier():
    remote = run_cmd(["git", "config", "--get", "remote.origin.url"])
    if remote:
        clean = remote.split(":")[-1].replace(".git", "").replace("/", "_")
        return clean if clean else os.path.basename(REPO_PATH)
    return os.path.basename(REPO_PATH)

IDENTIFIER = get_project_identifier()
RUBRIC_NAME = "".join(e for e in os.path.splitext(os.path.basename(args.rubric))[0].lower() if e.isalnum())
DATA_DIR = os.path.join(os.getcwd(), "data", IDENTIFIER)
CSV_PATH = os.path.join(DATA_DIR, f"{IDENTIFIER}_ledger_{RUBRIC_NAME}.csv")
LOG_PATH = os.path.join(DATA_DIR, f"{IDENTIFIER}_llm_logs.txt")
ARCH_PATH = os.path.join(DATA_DIR, f"{IDENTIFIER}_architecture.md")

os.makedirs(DATA_DIR, exist_ok=True)

def write_log(event_type, content):
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [{event_type}]\n{content}\n{'-'*60}\n")

def auto_map_architecture():
    print(f"🧠 Mapping architecture for {IDENTIFIER}...")
    tree_str = []
    for root, dirs, files in os.walk(REPO_PATH):
        dirs[:] = [d for d in dirs if d not in [".git", "node_modules", "venv", "__pycache__", "data"]]
        level = root.replace(REPO_PATH, "").count(os.sep)
        tree_str.append(f"{' ' * 4 * level}{os.path.basename(root)}/")
        for f in files: tree_str.append(f"{' ' * 4 * (level + 1)}{f}")
    repo_tree = "\n".join(tree_str)
    
    prompt = f"You are an expert Systems Architect. Analyze the following repository structure and output a concise 'architecture.md' file. Define the core modules, their architectural coupling, and their systemic blast radius. Do not output anything other than the raw markdown text.\n\nRepository Tree:\n{repo_tree}"
    response = completion(model=MODEL_NAME, messages=[{"role": "user", "content": prompt}])
    arch_content = response.choices[0].message.content
    with open(ARCH_PATH, "w", encoding="utf-8") as f: f.write(arch_content)
    write_log("ARCHITECTURE_MAP_GENERATED", f"Map rebuilt.\n\n{arch_content}")
    print(f"✅ Architecture map saved to {ARCH_PATH}")
    return arch_content

if __name__ == "__main__":
    if not os.path.exists(os.path.join(REPO_PATH, ".git")): print(f"❌ Error: {REPO_PATH} is not a valid git repository."); sys.exit(1)
    
    hash_long = run_cmd(["git", "log", "-1", "--format=%H"])
    hash_short = run_cmd(["git", "log", "-1", "--format=%h"])
    subject = run_cmd(["git", "log", "-1", "--format=%s"])
    author_date = run_cmd(["git", "log", "-1", "--format=%cI"])
    
    if not hash_long: print("❌ No commits found in this repository."); sys.exit(1)

    has_structural = any(line.startswith(("A", "D", "R")) for line in run_cmd(["git", "diff", "HEAD~1", "HEAD", "--name-status"]).split("\n"))
    
    if args.remap or not os.path.exists(ARCH_PATH) or has_structural: arch_context = auto_map_architecture()
    else:
        print("⚡ No structural changes detected. Loading cached architecture map.")
        with open(ARCH_PATH, "r", encoding="utf-8") as f: arch_context = f.read()

    diff = run_cmd(["git", "diff", "HEAD~1", "HEAD"])
    if not diff.strip(): print("⚠️ Diff is empty. Nothing to score."); sys.exit(0)

    try:
        with open(args.rubric, "r", encoding="utf-8") as f: rubric_rules = f.read()
        print("🔍 Analyzing diff and applying rubric...")
        sys_prompt = f"{rubric_rules}"
        usr_prompt = f"ARCHITECTURE CONTEXT:\n{arch_context}\n\nGIT DIFF:\n{diff}"
        response = completion(model=MODEL_NAME, messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": usr_prompt}], response_format={ "type": "json_object" })
        scores = json.loads(response.choices[0].message.content.strip())
        write_log(f"LLM_SCORING_PAYLOAD | {hash_short}", f"--- SYSTEM ---\n{sys_prompt}\n\n--- USER ---\n{usr_prompt}\n\n--- RESPONSE ---\n{json.dumps(scores)}")
        
        print(f"💾 Appending to {IDENTIFIER}_ledger_{RUBRIC_NAME}.csv...")
        file_exists = os.path.exists(CSV_PATH)
        headers = ["hash_long", "hash_short", "subject", "author_date", "lines_added", "lines_deleted"] + list(scores.keys())
        row = [hash_long, hash_short, subject, author_date, diff.count("\n+") - diff.count("\n+++"), diff.count("\n-") - diff.count("\n---")] + [scores[k] for k in scores.keys()]
        
        with open(CSV_PATH, "a", newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists: writer.writerow(headers)
            writer.writerow(row)
            
        print(f"🚀 Telemetry captured for {hash_short}: {json.dumps(scores)}") 
    except Exception as e: print(f"❌ Failed to parse commit: {e}")
