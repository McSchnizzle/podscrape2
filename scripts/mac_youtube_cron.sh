#!/bin/bash
# Mac-side YouTube transcript fetcher - runs from cron/launchd
# Fetches up to 5 pending YouTube transcripts with escalating delays
#
# Install as launchd job (runs daily at 10 AM):
#   cp scripts/com.podcast.youtube-fetch.plist ~/Library/LaunchAgents/
#   launchctl load ~/Library/LaunchAgents/com.podcast.youtube-fetch.plist
#
# Or add to crontab (runs daily at 10 AM):
#   crontab -e
#   0 10 * * * /Users/paulbrown/Desktop/coding-projects/podcast/scripts/mac_youtube_cron.sh

set -e

PROJECT_DIR="/Users/paulbrown/Desktop/coding-projects/podcast"
LOG_FILE="$PROJECT_DIR/data/logs/youtube_fetch_$(date +%Y%m%d).log"

mkdir -p "$(dirname "$LOG_FILE")"

echo "=== YouTube Fetch $(date) ===" >> "$LOG_FILE"

cd "$PROJECT_DIR"
source .venv/bin/activate
python3 scripts/fetch_youtube_transcripts.py -n 5 >> "$LOG_FILE" 2>&1

echo "=== Done $(date) ===" >> "$LOG_FILE"
