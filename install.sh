#!/bin/bash
trap 'printf "[r"; echo ""; echo "🛑 CommitMatrix engine gracefully halted."; exit 130' EXIT INT TERM
set -e
if [ ! -f .env ]; then echo "❌ Error: .env file missing."; exit 1; fi

source .env
APP_VERSION=$(cat /root/commit-matrix/VERSION 2>/dev/null || echo "0.1.20")

echo "🐳 Building Docker environment..."
docker compose build --no-cache --quiet --no-cache && docker compose down || true
docker compose up -d

# --- 1. ENGINE COMMAND ---
cat << 'WRAPPER' > /tmp/commit-matrix
#!/bin/bash
set -o pipefail

TARGET_REPO=$(cd "${1:-.}" && pwd)

if [[ "$1" == "--help" || "$1" == "-h" ]]; then
    # Pointing to the newly consolidated folder
    RUBRICS_DIR="/root/commit-matrix/rubrics"
    AVAILABLE_RUBRICS=""
    
    if [ -d "$RUBRICS_DIR" ]; then
        for f in "$RUBRICS_DIR"/*.md; do
            if [ -f "$f" ] && [[ $(basename "$f") != "RUBRIC_AUTHORING_GUIDE.md" ]]; then
                name=$(basename "$f" .md | tr '[:lower:]' '[:upper:]')
                profile=$(grep '^# Profile:' "$f" | sed 's/^# Profile:[[:space:]]*//')
                # Extract the words from the markdown headers (e.g., "### [G] Guard")
                acronym=$(grep -E '^### \[[A-Z]\]' "$f" | sed -n 's/^### \[[A-Z]\] \([a-zA-Z]*\).*/\1/p' | paste -sd ", " -)
                
                if [ -n "$acronym" ]; then
                    AVAILABLE_RUBRICS+="    - $(printf "%-5s" "$name") ($acronym)\n      ↳ $profile\n\n"
                else
                    AVAILABLE_RUBRICS+="    - $(printf "%-5s" "$name")\n      ↳ $profile\n\n"
                fi
            fi
        done
    else
        AVAILABLE_RUBRICS="    (Directory not found)"
    fi
    if [ -z "$AVAILABLE_RUBRICS" ]; then AVAILABLE_RUBRICS="    (No .md files found)"; fi

    echo "==============================================================================="
    echo " 🧬 CommitMatrix v$APP_VERSION"
    echo "==============================================================================="
    echo "An AI-powered architectural telemetry engine. It parses Git history, uses an"
    echo "LLM to score commits against custom rubrics, and generates an interactive"
    echo "dashboard to visualize repository fragility, churn, and blast radius."
    echo ""
    echo "USAGE:"
    echo "  commit-matrix [TARGET_DIR]"
    echo ""
    echo "ARGUMENTS:"
    echo "  TARGET_DIR          Path to the local Git repository you want to analyze."
    echo "                      If omitted, it defaults to the current directory (pwd)."
    echo ""
    echo "EXAMPLES:"
    echo "  commit-matrix .                  # Analyze the repo in the current folder"
    echo "  commit-matrix /var/www/my-app    # Analyze a specific project folder"
    echo ""
    echo "RUBRICS:"
    echo "  The engine evaluates commits based on markdown files located in:"
    echo "  ~/commit-matrix/rubrics/"
    echo ""
    echo "  Available Profiles:"
    printf "%b" "$AVAILABLE_RUBRICS"
    echo "OUTPUT:"
    echo "  - Generates SQLite database and ledgers in ~/commit-matrix/data/<repo_name>/db/"
    echo "  - Hosts a live dashboard. To view it, open this URL in your browser:"
    echo "    http://localhost:8000/?repo=<REPOSITORY_NAME>&token=$MATRIX_TOKEN"
    echo "==============================================================================="
    exit 0
elif [[ "$1" == "--version" || "$1" == "-v" ]]; then
    echo "CommitMatrix v$APP_VERSION"
    exit 0
fi

if [ ! -d "$TARGET_REPO/.git" ]; then echo "❌ Error: $TARGET_REPO is not a valid Git repository."; exit 1; fi

HOST_REPO_NAME=$(basename "$TARGET_REPO")
HOST_REPO_OWNER=$(cd "$TARGET_REPO" && git config --get remote.origin.url 2>/dev/null | python3 -c 'import sys,re; u=sys.stdin.read().strip(); u=re.sub(r"\.git$","",u); u=re.sub(r"^.*?://","",u); u=re.sub(r"^.*?@","",u); p=re.split(r"[:/]",u); print(p[-2] if len(p)>=2 and not p[-2].isdigit() else (p[-3] if len(p)>=3 else "local"))' 2>/dev/null)
[ -z "$HOST_REPO_OWNER" ] && HOST_REPO_OWNER="local"

SERVER_IP=$(hostname -I | awk '{print $1}')
if [ -z "$SERVER_IP" ]; then SERVER_IP="localhost"; fi
source /root/commit-matrix/.env 2>/dev/null || true

# --- FIXED HEADER MAGIC ---

# --------------------------
mkdir -p "/root/commit-matrix/data/$HOST_REPO_OWNER/$HOST_REPO_NAME/pipeline_runs"
LOG_DIR="/root/commit-matrix/data/$HOST_REPO_OWNER/$HOST_REPO_NAME/pipeline_runs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/run_$(date -u +%Y%m%d_%H%M%S)_UTC.log"

S_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
if [ -z "$S_IP" ]; then S_IP="localhost"; fi
export SERVER_IP=$S_IP

C_NAME="commit-matrix-core-$$-$RANDOM"

docker run --rm --name "$C_NAME" \
  -v "$TARGET_REPO:/$HOST_REPO_NAME" \
  -v "/root/commit-matrix/data:/app/data" \
  -v "/root/commit-matrix/rubrics:/app/rubrics" \
  --env-file "/root/commit-matrix/.env" \
  -e HOST_REPO_NAME="$HOST_REPO_NAME" \
  -e HOST_REPO_OWNER="$HOST_REPO_OWNER" \
  -e EXEC_MODE="native" \
  commit-matrix-core:latest \
  python -u -m backend.commit_pipeline --repo "/$HOST_REPO_NAME" 2>&1 \
  | python3 /root/commit-matrix/backend/services/pipeline/stream_filter.py "$LOG_FILE" &
FILTER_PID=$!

if [ -t 0 ]; then
    while kill -0 "$FILTER_PID" 2>/dev/null; do
        if read -r -t 1 -n 1 key; then
            case "$key" in
                "")
                    kill -USR1 "$FILTER_PID" 2>/dev/null
                    wait "$FILTER_PID" 2>/dev/null
                    break
                    ;;
                q|Q)
                    echo -e "\n🛑 Stopping engine at your request...\n"
                    # Gracefully stop the docker container so analysis halts immediately
                    docker stop -t 2 "$C_NAME" >/dev/null 2>&1 || docker kill "$C_NAME" >/dev/null 2>&1
                    kill -INT "$FILTER_PID" 2>/dev/null
                    wait "$FILTER_PID" 2>/dev/null
                    
                    SCORED_COUNT=$(grep -c "scored -> Queued" "$LOG_FILE" 2>/dev/null || echo 0)
                    
                    # Ensure .env is loaded to resolve dashboard tokens in the bash context
                    [ -f "/root/commit-matrix/.env" ] && source "/root/commit-matrix/.env"
                    
                    echo "⏸️  Stopped early. $SCORED_COUNT commit(s) were already scored and saved"
                    echo -e "   to the ledger — nothing is lost.\n"
                    echo "Visit the dashboard to see progress:"
                    echo " 🏠 Local:  http://localhost:8000/?owner=$HOST_REPO_OWNER&repo=$HOST_REPO_NAME&token=$MATRIX_TOKEN"
                    echo " ☁️  Server: http://$SERVER_IP:8000/?owner=$HOST_REPO_OWNER&repo=$HOST_REPO_NAME&token=$MATRIX_TOKEN"
                    exit 130
                    ;;
            esac
        fi
    done
fi

wait "$FILTER_PID" 2>/dev/null
_CMD_EXIT=$?

if [ $_CMD_EXIT -eq 0 ]; then
    echo -e "\n🤝 Telemetry synchronized. Pipeline finished."
elif [ "$_CMD_EXIT" = "130" ] || [ "$_CMD_EXIT" = "137" ] || [ "$_CMD_EXIT" = "143" ]; then
    echo -e "\n🛑 CommitMatrix engine gracefully halted."
    SCORED_COUNT=$(grep -c "scored -> Queued" "$LOG_FILE" 2>/dev/null || echo 0)
    [ -f "/root/commit-matrix/.env" ] && source "/root/commit-matrix/.env"
    echo "⏸️  $SCORED_COUNT commit(s) were successfully scored and saved to the ledger."
    echo "   Visit the dashboard to review the progress:"
    echo " 🏠 Local:  http://localhost:8000/?owner=$HOST_REPO_OWNER&repo=$HOST_REPO_NAME&token=$MATRIX_TOKEN"
    echo " ☁️  Server: http://$SERVER_IP:8000/?owner=$HOST_REPO_OWNER&repo=$HOST_REPO_NAME&token=$MATRIX_TOKEN
elif [ "$_CMD_EXIT" != "0" ]; then
    echo -e "\n❌ Error: The CommitMatrix engine failed unexpectedly. (Exit Code: $_CMD_EXIT)"
fi
exit $_CMD_EXIT
