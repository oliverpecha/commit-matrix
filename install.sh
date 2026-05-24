#!/bin/bash
if [ ! -f .env ]; then echo "❌ Error: .env file missing."; exit 1; fi

source .env
APP_VERSION=$(cat /root/commit-matrix/VERSION 2>/dev/null || echo "0.1.0")

echo "🐳 Building Docker environment..."
docker compose build --quiet && docker compose up -d

# --- 1. ENGINE COMMAND ---
cat << 'WRAPPER' > /tmp/commit-matrix
#!/bin/bash
TARGET_REPO="${1:-$(pwd)}"

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
    echo "  - Generates a compiled ledger in ~/commit-matrix/data/<repo_name>/"
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

echo "==========================================================================="
echo " 🧬 MATRIX ENGINE: Analyzing [$HOST_REPO_NAME]"
echo "==========================================================================="

docker run --rm \
  -v "$TARGET_REPO:/target_repo" \
  -v "/root/commit-matrix/data:/app/data" \
  -v "/root/commit-matrix/rubrics:/app/rubrics" \
  --env-file "/root/commit-matrix/.env" \
  -e HOST_REPO_NAME="$HOST_REPO_NAME" \
  commit-matrix-core:latest \
  python -u /app/backend/parser.py --repo /target_repo

if [ $? -eq 0 ]; then
    SERVER_IP=$(hostname -I | awk '{print $1}')
    if [ -z "$SERVER_IP" ]; then SERVER_IP="localhost"; fi

    echo "🤝 Telemetry synchronized."
    echo "📊 View Dashboard:"
    echo "   Local:  http://localhost:8000/?repo=$HOST_REPO_NAME&token=$MATRIX_TOKEN"
    echo "   Server: http://$SERVER_IP:8000/?repo=$HOST_REPO_NAME&token=$MATRIX_TOKEN"
    echo "==========================================================================="
else
    echo "❌ Error: The CommitMatrix engine failed to parse the commit."
    exit 1
fi
WRAPPER

# --- 2. CALIBRATION COMMAND ---
cat << 'CALIBRATE_WRAPPER' > /tmp/calibrate-matrix
#!/bin/bash
cd /root/commit-matrix || { echo "❌ Error: Could not locate /root/commit-matrix"; exit 1; }

docker run --rm \
  -v "$(pwd)/calibration:/app/calibration" \
  -v "$(pwd)/rubrics:/app/rubrics" \
  --env-file .env \
  -e LITELLM_LOG=ERROR \
  -e SUPPRESS_LITELLM_WARNINGS=True \
  commit-matrix-core:latest \
  python -u /app/calibration/calibrate.py "$@"
CALIBRATE_WRAPPER

sed -i "s/\$MATRIX_TOKEN/$MATRIX_TOKEN/g" /tmp/commit-matrix
sed -i "s/\$APP_VERSION/$APP_VERSION/g" /tmp/commit-matrix

sudo mv /tmp/commit-matrix /usr/local/bin/commit-matrix
sudo chmod +x /usr/local/bin/commit-matrix

sudo mv /tmp/calibrate-matrix /usr/local/bin/calibrate-matrix
sudo chmod +x /usr/local/bin/calibrate-matrix

echo "✅ Installation Complete! v$APP_VERSION is now active."
