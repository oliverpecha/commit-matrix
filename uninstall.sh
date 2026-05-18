#!/bin/bash
echo "🗑️ Uninstalling CommitMatrix..."
docker compose down
sudo rm -f /usr/local/bin/commit-matrix
echo "✅ Uninstall Complete. Data in ./data/ has been preserved."
