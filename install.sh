#!/bin/bash
echo "📦 Installing CommitMatrix..."
if [ ! -f .env ]; then echo "❌ Error: .env file missing."; exit 1; fi
MATRIX_DIR=$(pwd)

echo "🐳 Building Docker environment..."
docker compose build --quiet && docker compose up -d

echo "🔗 Linking global 'commit-matrix' command..."
cat << 'WRAPPER' > /tmp/commit-matrix
#!/bin/bash
TARGET_REPO="${1:-$(pwd)}"
if [ ! -d "$TARGET_REPO/.git" ]; then echo "❌ Error: $TARGET_REPO is not a valid Git repository."; exit 1; fi
REPO_NAME=$(basename "$TARGET_REPO")
echo "🚀 Analyzing: $REPO_NAME"

docker run --rm \
  -v "$TARGET_REPO:/target_repo" \
  -v "/root/commit-matrix/data:/app/data" \
  -v "/root/commit-matrix/backend/rubrics:/app/backend/rubrics" \
  --env-file "/root/commit-matrix/.env" \
  commit-matrix-core:latest \
  python /app/backend/parser.py --repo /target_repo
echo "✅ Telemetry saved. View dashboard at: http://localhost:8000/?repo=$REPO_NAME"
WRAPPER

sudo mv /tmp/commit-matrix /usr/local/bin/commit-matrix
sudo chmod +x /usr/local/bin/commit-matrix
echo "✅ Installation Complete!"
