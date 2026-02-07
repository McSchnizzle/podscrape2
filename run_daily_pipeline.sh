#!/bin/bash
# Daily podcast pipeline wrapper
# Runs the full pipeline orchestrator with proper environment and logging

set -e

# Change to project directory
cd /srv/projects/podcast-pipeline

# Log start time
echo "========================================"
echo "Podcast Pipeline Started: $(date)"
echo "========================================"

# Activate virtual environment and run orchestrator
source .venv/bin/activate

# Run with timeout to prevent runaway processes
timeout 15m python3 run_full_pipeline_orchestrator.py --verbose --days-back 5 --limit 10

# Log completion
echo "========================================"
echo "Podcast Pipeline Completed: $(date)"
echo "========================================"
