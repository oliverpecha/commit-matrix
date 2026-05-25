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
parser.add_argument("--rubric", type=str, default=os.path.join(os.getcwd(), "rubrics", "cirsd.md"), help="Path to the scoring rubric file")
args = parser.parse_args()

model_env = os.environ.get("MODEL_NAME")
if not model_env:
    print("\n❌ FATAL ERROR: MODEL_NAME environment variable is missing. Strict configuration enforcement active.\nAborting.", flush=True)
    import sys
    sys.exit(1)
MODEL_NAME = model_env
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

IDENTIFIER = os.environ.get("HOST_REPO_NAME", os.path.basename(REPO_PATH))
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
        response = completion(model=MODEL_NAME, messages=[{"role": "user", "content": prompt}], temperature=0.0)
        arch_content = response.choices[0].message.content
        with open(ARCH_PATH, "w", encoding="utf-8") as f: f.write(arch_content)
        return arch_content
    finally:
        spinner.stop()

if __name__ == "__main__":
    import csv
    if not os.path.exists(os.path.join(REPO_PATH, ".git")): print(f"❌ Error: {REPO_PATH} is not a valid git repository."); sys.exit(1)
    
    # --- ARCHITECTURE MAPPING (Only runs once per repository) ---
    if args.remap or not os.path.exists(ARCH_PATH): 
        arch_context = auto_map_architecture()
    else:
        print(f"⚡ Loading cached architecture map for [{IDENTIFIER}].\n\n", flush=True)
        with open(ARCH_PATH, "r", encoding="utf-8") as f: arch_context = f.read()

    # Get a list of ALL commits in chronological order (oldest first)
    log_output = run_cmd(["git", "log", "--reverse", "--format=%H|%h|%cI|%s"])
    if not log_output: print("❌ No commits found in this repository."); sys.exit(1)
    
    commits = log_output.strip().split('\n')

    # 1. Pre-load the existing ledger to cross-reference
    existing_hashes = set()
    if os.path.exists(CSV_PATH):
        with open(CSV_PATH, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None) # Skip header
            for row in reader:
                if len(row) > 1: existing_hashes.add(row[1])

    # 2. Filter out EVERYTHING that has already been scanned instantly
    unscanned_commits = []
    for commit_line in commits:
        parts = commit_line.split('|', 3)
        if len(parts) == 4 and parts[1] not in existing_hashes:
            unscanned_commits.append(parts)

    total_unscanned = len(unscanned_commits)

    if total_unscanned == 0:
        print("✅ Matrix is fully up to date. No new commits to analyze.\n\n", flush=True)
        sys.exit(0)

    print(f"📦 Discovered {total_unscanned} unscanned commit(s) ready for analysis.\n\n", flush=True)

    # 3. The Orchestrator & AIMD Worker Pool Setup
    import threading, time
    from concurrent.futures import ThreadPoolExecutor, as_completed

    MAX_CONCURRENT_WORKERS = int(os.environ.get("MATRIX_MAX_WORKERS", 32))
    file_exists = os.path.exists(CSV_PATH)
    MAX_RETRIES = 6

    class AIMDController:
        def __init__(self, initial=2, max_workers=8):
            self.limit = initial
            self.max_workers = max_workers
            self.active = 0
            self.lock = threading.Lock()
            self.cond = threading.Condition(self.lock)
            self.successes = 0

        def wait_and_acquire(self):
            with self.cond:
                while self.active >= int(self.limit):
                    self.cond.wait()
                self.active += 1

        def release(self, success=True):
            with self.cond:
                self.active -= 1
                if success:
                    self.successes += 1
                    if self.successes >= 4 and self.limit < self.max_workers:
                        self.limit += 1
                        self.successes = 0
                else:
                    self.limit = max(1, int(self.limit / 2))
                    self.successes = 0
                self.cond.notify_all()

    aimd = AIMDController(initial=2, max_workers=MAX_CONCURRENT_WORKERS)

    def process_commit(i, parts, total_unscanned, arch_context):
        hash_long, hash_short, author_date, subject = parts
        diff = run_cmd(["git", "diff", f"{hash_long}~1", hash_long])
        if not diff.strip(): diff = run_cmd(["git", "diff", "4b825dc642cb6eb9a060e54bf8d69288fbee4904", hash_long])
        if not diff.strip(): return i, None

        retries = MAX_RETRIES
        while retries > 0:
            aimd.wait_and_acquire()
            try:
                with open(args.rubric, "r", encoding="utf-8") as f: rubric_rules = f.read()
                sys_prompt = f"{rubric_rules}"
                usr_prompt = f"ARCHITECTURE CONTEXT:\n{arch_context}\n\nGIT DIFF:\n{diff}"
                
                response = completion(model=MODEL_NAME, messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": usr_prompt}], temperature=0.0)
                aimd.release(success=True)
                
                raw_text = response.choices[0].message.content
                json_str = raw_text.strip()
                t3 = chr(96) * 3
                if json_str.startswith(t3 + "json"): json_str = json_str.split(t3 + "json", 1)[1].strip()
                elif json_str.startswith(t3): json_str = json_str.split(t3, 1)[1].strip()
                if json_str.endswith(t3): json_str = json_str.rsplit(t3, 1)[0].strip()
                scores = json.loads(json_str)
                
                headers = ["hash_long", "hash_short", "subject", "author_date", "lines_added", "lines_deleted"] + list(scores.keys())
                added = max(0, diff.count("\n+") - diff.count("\n+++"))
                deleted = max(0, diff.count("\n-") - diff.count("\n---"))
                row = [hash_long, hash_short, subject, author_date, added, deleted] + [scores.get(k, "") for k in scores.keys()]
                
                tier = scores.get('tier', 'Routine').upper()
                tot_score = scores.get('tot', sum([int(scores.get(k,0)) for k in ['C','I','R','S','D'] if str(scores.get(k,0)).isdigit()]))
                touches = [k.replace('touches_', '') for k, v in scores.items() if k.startswith('touches_') and v is True]
                t_str = ", ".join(touches) if touches else "None"
                traffic_light = "🟢" if tier == "ROUTINE" else "🟡" if tier == "SIGNIFICANT" else "🔴"
                
                try: 
                    dt_obj = datetime.fromisoformat(author_date.replace("Z", "+00:00"))
                    formatted_date = dt_obj.strftime('%b %d, %Y')
                except: 
                    formatted_date = author_date.split("T")[0] if "T" in author_date else author_date
                
                subject_display = f"📝 Subject: {subject[:60]}..." if len(subject) > 60 else f"📝 Subject: {subject}"
                ui_block = (
                    f"┌─────────────────────────────────────────────────────────────────────────┐\n"
                    f"│ 🚀 TELEMETRY {i} out of {total_unscanned}: {hash_short}\n"
                    f"├─────────────────────────────────────────────────────────────────────────┤\n"
                    f"│ 📅 Date:   {formatted_date}\n"
                    f"│ {subject_display}\n"
                    f"│ {traffic_light} Tier:   {tier} (Score: {tot_score})\n"
                    f"│ 🛠️  Scope:  {t_str}\n"
                    f"└─────────────────────────────────────────────────────────────────────────┘\n\n"
                )
                
                return i, (headers, row, hash_short, ui_block)

            except Exception as e:
                error_str = str(e)
                if 'monthly spending cap' in error_str.lower() or 'billing' in error_str.lower():
                    print('\n❌ FATAL ERROR: Google API Billing Cap Exceeded. Check https://ai.studio/spend.\nAborting.', flush=True)
                    import sys
                    sys.exit(1)
                err_str = str(e)
                aimd.release(success=False)
                
                if "429" in err_str or "spending cap" in err_str.lower() or "quota" in err_str.lower():
                    retries -= 1
                    if retries > 0:
                        backoff = 15 * (6 - retries)
                        import traceback; traceback.print_exc(); print(f"⚠️ [Worker] API Rate Limit hit on {hash_short}. Pausing {backoff}s... ", end="", flush=True)
                        time.sleep(backoff)
                        print("Resuming.\n", flush=True)
                    else:
                        print(f"🛑 CRITICAL: API Rate Limit hard-failed {MAX_RETRIES} times on {hash_short}. Aborting.\n\n", flush=True)
                        import os; os._exit(1)
                else:
                    return i, f"❌ Error scoring commit {hash_short}: {err_str}\n\n"

    # 4. The Orchestrator Loop (Sliding Window Dispatcher)
    print(f"⚡ Initializing AIMD Engine (Sliding Window, Dynamic Max: {MAX_CONCURRENT_WORKERS})", end="", flush=True)
    is_first_output = True
    
    error_count = 0
    success_count = 0
    error_count = 0
    success_count = 0
    pending_results = {}
    next_to_write = 1
    window_size = MAX_CONCURRENT_WORKERS + 4 # The maximum lookahead buffer
    
    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_WORKERS) as executor:
        from concurrent.futures import wait, FIRST_COMPLETED
        active_futures = {}
        commit_iterator = iter(enumerate(unscanned_commits, 1))
        
        # 1. Fill the initial queue window
        for _ in range(window_size):
            try:
                i, parts = next(commit_iterator)
                active_futures[executor.submit(process_commit, i, parts, total_unscanned, arch_context)] = i
            except StopIteration:
                break
                
        # 2. Process completions and slide the window forward
        while active_futures:
            done, _ = wait(active_futures.keys(), timeout=1.5, return_when=FIRST_COMPLETED)
            if not done:
                print(".", end="", flush=True)
                continue
            if is_first_output:
                print("\n\n", flush=True)
                is_first_output = False
            
            for future in done:
                idx = active_futures.pop(future)
                idx_ret, result = future.result()
                pending_results[idx_ret] = result
                
                if result and not isinstance(result, str):
                    print(f"⚙️  [Worker] Scored {result[2]} -> Queued for ledger flush...\n", flush=True)
                    
                # Slide the window: Queue one new task for every completed task
                try:
                    next_i, next_parts = next(commit_iterator)
                    active_futures[executor.submit(process_commit, next_i, next_parts, total_unscanned, arch_context)] = next_i
                except StopIteration:
                    pass
                    
                # Flush the chronological backlog instantly
                while next_to_write in pending_results:
                    res = pending_results.pop(next_to_write)
                    if res:
                        if isinstance(res, str): 
                            error_count += 1
                            error_count += 1
                            print(res, flush=True)
                        else:
                            headers, row, hash_short, ui_block = res
                            success_count += 1
                            success_count += 1
                            with open(CSV_PATH, "a", newline='', encoding='utf-8') as f:
                                writer = csv.writer(f)
                                if next_to_write == 1 and not file_exists:
                                    writer.writerow(headers)
                                    file_exists = True
                                writer.writerow(row)
                                existing_hashes.add(hash_short)
                            print(ui_block, flush=True)
                    
                    next_to_write += 1

    if error_count > 0:
        print(f'⚠️ PROCESS_COMPLETE_WITH_ERRORS: {error_count} failed, {success_count} succeeded.\n\n', flush=True)
    else:
        print('🤝 PROCESS_COMPLETE\n\n', flush=True)
