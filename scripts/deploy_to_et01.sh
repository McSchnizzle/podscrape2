#!/bin/bash
# Deploy podcast-pipeline to et01
# Usage: ./scripts/deploy_to_et01.sh

set -e

echo "Deploying podcast-pipeline to et01..."

rsync -avz --delete \
  --exclude '.venv' --exclude 'node_modules' --exclude '.git' \
  --exclude 'data/' --exclude 'logs/' --exclude '.env' \
  --exclude '__pycache__' --exclude '.next' --exclude '.claude' \
  --exclude 'ui-tests/' --exclude '.agents/' \
  ./ et01:/srv/projects/podcast-pipeline/

echo "Deploy complete."
echo ""
echo "Verify with:"
echo "  ssh et01 'cd /srv/projects/podcast-pipeline && source .venv/bin/activate && python3 -c \"from src.topic_tracking.digest_arc_reconciler import DigestArcReconciler; print(\\\"OK\\\")\"'"
