#!/bin/bash
echo "🗑️  Uninstalling CommitMatrix..."
docker compose down --rmi all
sudo rm -f /usr/local/bin/commit-matrix
sudo rm -f /usr/local/bin/calibrate-matrix
sudo rm -f /usr/local/bin/arch-history
sudo rm -f /usr/local/bin/matrix-health
echo "✅ Uninstallation Complete."
