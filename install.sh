#!/bin/bash
if [ ! -f .env ]; then echo "❌ Error: .env file missing."; exit 1; fi

# Extract the token securely from the .env file
source .env

echo "🐳 Building Docker environment..."
docker compose build --quiet && docker compose up -d

# --- 1. ENGINE COMMAND ---
cat << 'WRAPPER' > /tmp/commit-matrix
#!/bin/bash
TARGET_REPO="${1:-$(pwd)}"
if [ ! -d "$TARGET_REPO/.git" ]; then echo "❌ Error: $TARGET_REPO is not a valid Git repository."; exit 1; fi

HOST_REPO_NAME=$(basename "$TARGET_REPO")

echo "==========================================================================="
echo " 🧬 MATRIX ENGINE: Analyzing [$HOST_REPO_NAME]"
echo "==========================================================================="

docker run --rm \
  -v "$TARGET_REPO:/target_repo" \
  -v "/root/commit-matrix/data:/app/data" \
  -v "/root/commit-matrix/backend/rubrics:/app/backend/rubrics" \
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
  -v "$(pwd)/backend/rubrics:/app/backend/rubrics" \
  --env-file .env \
  -e LITELLM_LOG=ERROR \
  -e SUPPRESS_LITELLM_WARNINGS=True \
  commit-matrix-core:latest \
  python -u /app/calibration/calibrate.py "$@"
CALIBRATE_WRAPPER

# Inject the variable dynamically
sed -i "s/\$MATRIX_TOKEN/$MATRIX_TOKEN/g" /tmp/commit-matrix

sudo mv /tmp/commit-matrix /usr/local/bin/commit-matrix
sudo chmod +x /usr/local/bin/commit-matrix

sudo mv /tmp/calibrate-matrix /usr/local/bin/calibrate-matrix
sudo chmod +x /usr/local/bin/calibrate-matrix

echo "✅ Installation Complete! Commands available: commit-matrix, calibrate-matrix"
