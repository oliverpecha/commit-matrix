import os, sys, json, argparse, subprocess, csv, logging, threading, time
from datetime import datetime
import warnings

# Silence LiteLLM Warnings
warnings.filterwarnings('ignore', module='litellm')
logging.getLogger('LiteLLM').setLevel(logging.ERROR)

from litellm import completion

parser = argparse.ArgumentParser(description="CommitMatrix LLM Parser")
parser.add_argument("--repo", type=str, default=os.getcwd(), help="Absolute path to the target git repository")
parser.add_argument("--remap", action="store_true", help="Force a repository architecture re-map")
parser.add_argument("--rubric", type=str, default=os.path.join(os.getcwd(), "backend", "rubrics", "cirsd.md"), help="Path to the scoring rubric file")
args = parser.parse_args()

MODEL_NAME = "gemini/gemini-3.1-pro-preview"
REPO_PATH = os.path.abspath(args.repo)

# --- DAEMON SPINNER ---
class Spinner:
    def __init__(self, message):
        self.message = message
        self.running = False
        self.thread = None
    def spin(self):
        sys.stdout.write(f"{self.message} ")
        sys.stdout.flush()
        while self.running:
            sys.stdout.write(".")
            sys.stdout.flush()
            time.sleep(1.0)
    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self.spin)
        self.thread.daemon = True # Kills the spinner instantly if main thread crashes
        self.thread.start()
    def stop(self):
        self.running = False
        if self.thread: self.thread.join()
        sys.stdout.write(" [DONE]\n")
        sys.stdout.flush()

# --- GIT & PATH CONFIG ---
def run_cmd(cmd):
    try: return subprocess.run(cmd, cwd=REPO_PATH, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True).stdout.strip()
    except subprocess.CalledProcessError: return ""

def get_project_identifier():
    remote = run_cmd(["git", "config", "--get", "remote.origin.url"])
    if remote:
        clean = remote.split(":")[-1].replace(".git", "").replace("/", "_")
        if clean: return clean
    return os.environ.get("HOST_REPO_NAME", os.path.basename(REPO_PATH))

IDENTIFIER = get_project_identifier()
RUBRIC_NAME = "".join(e for e in os.path.splitext(os.path.basename(args.rubric))[0].lower() if e.isalnum())
DATA_DIR = os.path.join(os.environ.get("MATRIX_DATA_DIR", "/app/data"), IDENTIFIER)
CSV_PATH = os.path.join(DATA_DIR, f"{IDENTIFIER}_ledger_{RUBRIC_NAME}.csv")
ARCH_PATH = os.path.join(DATA_DIR, f"{IDENTIFIER}_architecture.md")

os.makedirs(DATA_DIR, exist_ok=True)

# --- LLM CORE ---
def auto_map_architecture():
    tree_str = []
    for root, dirs, files in os.walk(REPO_PATH):
        dirs[:] = [d for d in dirs if d not in [".git", "node_modules", "venv", "__pycache__", "data"]]
        level = root.replace(REPO_PATH, "").count(os.sep)
        tree_str.append(f"{' ' * 4 * level}{os.path.basename(root)}/")
        for f in files: tree_str.append(f"{' ' * 4 * (level + 1)}{f}")
    repo_tree = "\n".join(tree_str)
    
    prompt = f"You are an expert Systems Architect. Analyze the following repository structure and output a concise 'architecture.md' file. Define the core modules, their architectural coupling, and their systemic blast radius. Do not output anything other than the raw markdown text.\n\nRepository Tree:\n{repo_tree}"
    
    spinner = Spinner(f"🧠 Mapping architecture for [{IDENTIFIER}]")
    try:
        spinner.start()
        response = completion(model=MODEL_NAME, messages=[{"role": "user", "content": prompt}], temperature=0.0, num_retries=3)
        arch_content = response.choices[0].message.content
        with open(ARCH_PATH, "w", encoding="utf-8") as f: f.write(arch_content)
        return arch_content
    finally:
        spinner.stop()

if __name__ == "__main__":
    if not os.path.exists(os.path.join(REPO_PATH, ".git")): print(f"❌ Error: {REPO_PATH} is not a valid git repository."); sys.exit(1)
    
    hash_long = run_cmd(["git", "log", "-1", "--format=%H"])
    hash_short = run_cmd(["git", "log", "-1", "--format=%h"])
    subject = run_cmd(["git", "log", "-1", "--format=%s"])
    author_date = run_cmd(["git", "log", "-1", "--format=%cI"])
    if not hash_long: print("❌ No commits found in this repository."); sys.exit(1)

    # --- IDEMPOTENCY CHECK ---
    # Prevents duplicate entries in the database
    if os.path.exists(CSV_PATH):
        with open(CSV_PATH, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) > 1 and row[1] == hash_short:
                    print(f"\n✅ Commit [{hash_short}] already exists in ledger. Skipping analysis.\n")
                    sys.exit(0)

    # --- ARCHITECTURE MAPPING ---
    if args.remap or not os.path.exists(ARCH_PATH): 
        arch_context = auto_map_architecture()
    else:
        print(f"⚡ Loading cached architecture map for [{IDENTIFIER}].")
        with open(ARCH_PATH, "r", encoding="utf-8") as f: arch_context = f.read()

    # --- DIFF & SCORING ---
    diff = run_cmd(["git", "diff", "HEAD~1", "HEAD"])
    if not diff.strip(): print("⚠️ Diff is empty. Nothing to score."); sys.exit(0)

    try:
        with open(args.rubric, "r", encoding="utf-8") as f: rubric_rules = f.read()
        sys_prompt = f"{rubric_rules}"
        usr_prompt = f"ARCHITECTURE CONTEXT:\n{arch_context}\n\nGIT DIFF:\n{diff}"
        
        spinner = Spinner(f"🔍 Analyzing diff and applying [{RUBRIC_NAME.upper()}] rubric")
        try:
            spinner.start()
            # Added num_retries=3 to handle temporary 503 Google errors
            response = completion(model=MODEL_NAME, messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": usr_prompt}], response_format={ "type": "json_object" }, temperature=0.0, num_retries=3)
        finally:
            spinner.stop()
            
        scores = json.loads(response.choices[0].message.content.strip())
        
        file_exists = os.path.exists(CSV_PATH)
        headers = ["hash_long", "hash_short", "subject", "author_date", "lines_added", "lines_deleted"] + list(scores.keys())
        row = [hash_long, hash_short, subject, author_date, diff.count("\n+") - diff.count("\n+++"), diff.count("\n-") - diff.count("\n---")] + [scores[k] for k in scores.keys()]
        
        with open(CSV_PATH, "a", newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists: writer.writerow(headers)
            writer.writerow(row)

        c_dim, c_rst = "\033[2m", "\033[0m"
        c_grn, c_ylw, c_red, c_cyn = "\033[92m", "\033[93m", "\033[91m", "\033[96m"

        tier = scores.get('tier', 'Routine').upper()
        t_color = c_red if tier == 'CRITICAL' else (c_ylw if tier == 'SIGNIFICANT' else c_grn)
        tot_score = scores.get('tot', sum([scores.get(k,0) for k in ['C','I','R','S','D']]))
        touches = [k.replace('touches_', '') for k, v in scores.items() if k.startswith('touches_') and v is True]
        t_str = ", ".join(touches) if touches else "None"

        print(f"\n{c_dim}┌─────────────────────────────────────────────────────────────────────────┐{c_rst}")
        print(f"{c_dim}│{c_rst} 🚀 TELEMETRY: {c_cyn}{hash_short}{c_rst}")
        print(f"{c_dim}├─────────────────────────────────────────────────────────────────────────┤{c_rst}")
        print(f"{c_dim}│{c_rst} 🏆 Tier:   {t_color}{tier}{c_rst} (Score: {tot_score})")
        print(f"{c_dim}│{c_rst} 📊 Matrix: │  C:{scores.get('C',0)}  │  I:{scores.get('I',0)}  │  R:{scores.get('R',0)}  │  S:{scores.get('S',0)}  │  D:{scores.get('D',0)}  │")
        print(f"{c_dim}│{c_rst} 🛠️  Scope:  {t_str}")
        print(f"{c_dim}└─────────────────────────────────────────────────────────────────────────┘{c_rst}\n")

    except Exception as e: print(f"\n❌ Failed to parse commit: {e}")
