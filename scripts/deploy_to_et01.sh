#!/bin/bash
# Deploy podcast-pipeline to et01
# Usage: ./scripts/deploy_to_et01.sh
#
# Excludes:
#   - Standard: .venv, node_modules, .git, data/, .env, __pycache__, .next, .claude, .agents, ui-tests
#   - et01-specific: Files in .rsync-exclude-et01 (edit to add/remove protected files)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
EXCLUDE_FILE="$SCRIPT_DIR/.rsync-exclude-et01"

cd "$PROJECT_DIR"

echo "Deploying podcast-pipeline to et01..."

rsync -avz --delete \
  --exclude '.venv' --exclude 'node_modules' --exclude '.git' \
  --exclude 'data/' --exclude 'logs/' --exclude '.env' \
  --exclude '__pycache__' --exclude '.next' --exclude '.claude' \
  --exclude 'ui-tests/' --exclude '.agents/' \
  --exclude-from="$EXCLUDE_FILE" \
  ./ et01:/srv/projects/podcast-pipeline/

echo "Deploy complete."
echo ""
echo "Verify with:"
echo "  ssh et01 'cd /srv/projects/podcast-pipeline && . .venv/bin/activate && python3 -c \"import src; print(\\\"OK\\\")\"'"
